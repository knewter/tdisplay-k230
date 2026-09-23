#!/usr/bin/env python3
"""Exercise actual pinned Sway and Wayland clients under headless user emulation.

Never physical proof: input is injected through the opt-in probe IPC handler.
Pass the unwrapped RISC-V Sway executable and a native Wayland probe client.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time
from card_virtual_keyboard import Keyboard

def wait_for(predicate, timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=predicate()
        if value: return value
        time.sleep(.05)
    raise AssertionError('timed out waiting for test condition')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sway',required=True)
    ap.add_argument('--client',required=True)
    ap.add_argument('--qemu',default='/usr/bin/qemu-riscv64-static')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--disabled',action='store_true')
    args=ap.parse_args()
    runtime=args.output or Path(tempfile.mkdtemp(prefix='k230-card-headless-'))
    if args.output and runtime.exists() and any(runtime.iterdir()):
        ap.error('--output must be a new or empty directory')
    runtime.mkdir(parents=True,exist_ok=True); runtime.chmod(0o700)
    print(f'Headless evidence: {runtime}',flush=True)
    config=runtime/'config'
    config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\nfor_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48\n')
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_COMPOSITION_PROBE='0' if args.disabled else '1')
    processes=[]
    keyboard=None
    log=(runtime/'sway.log').open('w')
    sway=subprocess.Popen([args.qemu,args.sway,'-c',str(config),'-d'],env=env,stdout=log,stderr=log)
    processes.append(sway)
    def logs(): return (runtime/'sway.log').read_text()
    def ipc(command,kind=0,check=True):
        sock=socket.socket(socket.AF_UNIX)
        sock.settimeout(10)
        sock.connect(str(next(runtime.glob('sway-ipc.*.sock'))))
        payload=command.encode()
        sock.sendall(b'i3-ipc'+struct.pack('=II',len(payload),kind)+payload)
        def read(n):
            data=b''
            while len(data)<n:
                chunk=sock.recv(n-len(data)); assert chunk,'IPC closed'
                data+=chunk
            return data
        header=read(14); length,_=struct.unpack('=II',header[6:])
        result=json.loads(read(length)); sock.close()
        if kind==0 and check: assert all(r['success'] for r in result),(command,result)
        return result
    def command(s): return ipc('k230_card_probe '+s)
    def tree_nodes(tree):
        yield tree
        for node in tree.get('nodes',[])+tree.get('floating_nodes',[]): yield from tree_nodes(node)
    def focused():
        return next((n.get('app_id') for n in tree_nodes(ipc('',4)) if n.get('focused')),None)
    def start_client(app_id,refuse=False):
        path=runtime/(app_id+'.jsonl')
        f=path.open('a')
        prefix=[args.qemu] if Path(args.client).read_bytes()[18:20]==b'\xf3\x00' else []
        client=subprocess.Popen(prefix+[args.client,'--app-id',app_id]+(['--refuse-close'] if refuse else []),env=env,stdout=f,stderr=f)
        processes.append(client)
        return client
    def keys(app_id):
        lines=(runtime/(app_id+'.jsonl')).read_text().splitlines()
        return max((json.loads(line).get('key_presses',0) for line in lines if line.startswith('{')),default=0)
    def frames(app_id):
        path=runtime/(app_id+'.jsonl')
        records=[json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
        last=records[-1] if records else {}
        return [last.get("frames",0),last.get("child_frames",0)]
    try:
        wait_for(lambda:'Running compositor on wayland display' in logs(),60)
        env['WAYLAND_DISPLAY']=next(p.name for p in runtime.glob('wayland-*') if not p.name.endswith('.lock'))
        one=start_client('k230.card.one',True)
        two=start_client('k230.card.two')
        if args.disabled:
            wait_for(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two') for n in tree_nodes(ipc('',4)))==2)
            failed=ipc('k230_card_probe enter',check=False)
            assert not failed[0]['success'] and 'disabled' in failed[0]['error']
            assert 'K230_CARD ' not in logs()
            print('PASS actual Sway exact disabled environment with two live apps',flush=True)
            return
        wait_for(lambda:'map card=0' in logs() and 'map card=1' in logs())
        keyboard=Keyboard(runtime/env['WAYLAND_DISPLAY'])
        time.sleep(.4)
        command('fail-mirror 2')
        failed=ipc('k230_card_probe enter',check=False)
        assert not failed[0]['success']
        wait_for(lambda:'restored reason=scene-setup' in logs())
        assert focused() in ('k230.card.one','k230.card.two')
        command('enter')
        wait_for(lambda:'attached cards=2' in logs())
        before=[frames('k230.card.one'),frames('k230.card.two')]
        time.sleep(2)
        after=[frames('k230.card.one'),frames('k230.card.two')]
        assert all(a>b for apps in zip(after,before) for a,b in zip(*apps)),('client frame starvation',before,after)
        if subprocess.run(['sh','-c','command -v grim'],stdout=subprocess.DEVNULL).returncode==0:
            subprocess.run(['grim',str(runtime/'cards.png')],env=env,check=True)
        command('down 10 284 200'); command('down 11 284 700')
        wait_for(lambda:'restored reason=second-contact' in logs())
        command('up 10'); command('up 11')
        command('enter'); command('cancel')
        wait_for(lambda:'restored reason=touch-cancel' in logs())
        command('enter')
        command('down 1 284 700')
        for y in range(700,740,5): command(f'motion 1 284 {y}')
        command('up 1')
        command('down 2 284 700'); command('up 2')
        wait_for(lambda:focused()=='k230.card.two')
        keyboard.press(); wait_for(lambda:keys('k230.card.two')==1)
        command('enter')
        command('down 3 284 200'); command('motion 3 284 50'); command('up 3')
        wait_for(lambda:'close-refused card=0' in logs())
        assert one.poll() is None
        keyboard.press(); wait_for(lambda:keys('k230.card.two')==2)
        command('enter')
        command('down 4 284 700'); command('motion 4 284 500'); command('up 4')
        wait_for(lambda:two.poll() is not None)
        wait_for(lambda:'app-exit card=1' in logs())
        assert focused()=='k230.card.one'
        keyboard.press(); wait_for(lambda:keys('k230.card.one')==1)
        two=start_client('k230.card.two')
        wait_for(lambda:sum('map card=1' in line for line in logs().splitlines())>=2)
        time.sleep(.4); command('enter'); command('down 5 284 200')
        one.terminate(); wait_for(lambda:one.poll() is not None)
        wait_for(lambda:'restored reason=unmap' in logs())
        command('up 5')
        assert focused()=='k230.card.two'
        one=start_client('k230.card.one',True)
        wait_for(lambda:sum('map card=0' in line for line in logs().splitlines())>=2)
        time.sleep(.4); command('enter')
        ipc('output HEADLESS-1 disable')
        wait_for(lambda:'restored reason=unsafe-scene-or-allocation' in logs())
        ipc('output HEADLESS-1 enable')
        assert sway.poll() is None
        results={'evidence_class':'headless-qemu-injected-input','before_frames':before,'after_frames':after,
          'passed':['atomic-allocation-fallback','two-live-apps','second-contact-cancel','touch-cancel','continuous-motion','select-focus','close-refused','close-exit','unmap-during-drag','focus-fallback','virtual-keyboard-return','output-disable-fallback'],
          'limits':['no physical touch or panel proof','virtual keyboard only; physical OSK remains unverified','headless output presentation only']}
        (runtime/'result.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results),flush=True)
    finally:
        if keyboard: keyboard.close()
        for proc in reversed(processes):
            if proc.poll() is None: proc.terminate()
        for proc in processes:
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()
if __name__=='__main__': main()
