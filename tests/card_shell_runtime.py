#!/usr/bin/env python3
"""Exercise actual pinned Sway and Wayland clients under headless user emulation.

Never physical proof: input is injected through the opt-in product IPC handler.
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
from PIL import Image

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
    ap.add_argument('--benchmark',action='store_true')
    args=ap.parse_args()
    runtime=args.output or Path(tempfile.mkdtemp(prefix='k230-card-headless-'))
    if args.output and runtime.exists() and any(runtime.iterdir()):
        ap.error('--output must be a new or empty directory')
    runtime.mkdir(parents=True,exist_ok=True); runtime.chmod(0o700)
    print(f'Headless evidence: {runtime}',flush=True)
    config=runtime/'config'
    config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\nfor_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48\n')
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_SHELL='0' if args.disabled else '1')
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
    def command(s): return ipc('card_shell '+s)
    def tree_nodes(tree):
        yield tree
        for node in tree.get('nodes',[])+tree.get('floating_nodes',[]): yield from tree_nodes(node)
    def focused():
        return next((n.get('app_id') for n in tree_nodes(ipc('',4)) if n.get('focused')),None)
    def start_client(app_id,refuse=False,name=None):
        path=runtime/((name or app_id)+'.jsonl')
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
        wait_for(lambda:any(n.get('app_id')=='k230.card.one' for n in tree_nodes(ipc('',4))))
        two=start_client('k230.card.two')
        wait_for(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two') for n in tree_nodes(ipc('',4)))==2)
        if args.disabled:
            failed=ipc('card_shell enter',check=False)
            assert not failed[0]['success'] and 'disabled' in failed[0]['error']
            print('PASS disabled product adapter',flush=True)
            return
        keyboard=Keyboard(runtime/env['WAYLAND_DISPLAY'])
        time.sleep(.4)
        ipc('[app_id="k230.card.one"] focus')
        if args.benchmark:
            command('benchmark injected'); time.sleep(3.1)
        command('enter')
        # Halfway between cards makes both root/child surfaces visibly sampled.
        # A fully offscreen card correctly receives no frame callbacks.
        command('down 91 284 450');command('motion 91 114 450')
        before=[frames('k230.card.one'),frames('k230.card.two')]
        time.sleep(1)
        after=[frames('k230.card.one'),frames('k230.card.two')]
        assert all(all(b>a for a,b in zip(x,y)) for x,y in zip(before,after)), (before,after)
        subprocess.run(['grim',str(runtime/'two-live.png')],env=env,check=True)
        command('up 91');command('previous');time.sleep(.1)
        if args.benchmark:
            for gesture in range(20,23):
                command(f'down {gesture} 284 450')
                for step in range(30):
                    command(f'motion {gesture} {284-step*3} 450'); time.sleep(.03)
                command(f'up {gesture}')
        subprocess.run(['grim',str(runtime/'cards.png')],env=env,check=True)
        command('down 1 284 450')
        for x in range(284,34,-25):
            command(f'motion 1 {x} 450'); time.sleep(.02)
            if x==184:
                subprocess.run(['grim',str(runtime/'during-drag.png')],env=env,check=True)
                assert Image.open(runtime/'during-drag.png').getpixel((100,700)) != Image.open(runtime/'cards.png').getpixel((100,700))
        command('up 1')
        command('down 2 284 450'); command('up 2')
        wait_for(lambda:focused()=='k230.card.two')
        keyboard.press(); wait_for(lambda:keys('k230.card.two')==1)
        if args.benchmark:
            time.sleep(3.1);command('benchmark-stop')
        command('enter'); command('previous')
        command('down 40 284 500');time.sleep(.03);command('motion 40 284 420');time.sleep(.03);command('motion 40 284 300');command('up 40')
        wait_for(lambda:'message=6' in logs())
        assert one.poll() is None
        subprocess.run(['grim',str(runtime/'close-timeout.png')],env=env,check=True)
        command('next'); command('down 41 440 1200'); command('up 41')
        wait_for(lambda:two.poll() is not None)
        command('back'); wait_for(lambda:focused()=='k230.card.one')
        keyboard.press(); wait_for(lambda:keys('k230.card.one')==1)
        command('enter')
        ipc('[app_id="k230.card.one"] mark --add k230_card_private')
        time.sleep(.3)
        subprocess.run(['grim',str(runtime/'private.png')],env=env,check=True)
        # Actual denied pixels must be the uniform selected-card background.
        denied=Image.open(runtime/'private.png').convert('RGB').crop((150,350,410,750))
        assert len(denied.getcolors(denied.width*denied.height))==1
        ipc('[app_id="k230.card.one"] mark --add k230_card_unavailable')
        ipc('[app_id="k230.card.one"] unmark k230_card_private')
        time.sleep(.2)
        subprocess.run(['grim',str(runtime/'unavailable.png')],env=env,check=True)
        unavailable=Image.open(runtime/'unavailable.png').convert('RGB').crop((150,350,410,750))
        assert len(unavailable.getcolors(unavailable.width*unavailable.height))==1
        ipc('[app_id="k230.card.one"] unmark k230_card_unavailable')
        command('back')
        command('enter'); command('down 3 284 450'); command('cancel')
        command('down 4 284 450'); command('up 4')
        wait_for(lambda:focused()=='k230.card.one')
        command('enter');command('down 8 284 450');command('motion 8 220 450');command('down 9 350 450')
        command('up 8');command('up 9');command('enter');command('down 10 284 450');command('up 10')
        # Global edge entry reserves down and enters only after upward motion.
        command('down 5 284 1210'); command('motion 5 284 1100'); command('up 5')
        command('back')
        # Persistent button has release-on-same-target behavior.
        command('down 6 480 90'); command('up 6')
        command('down 7 480 90'); command('up 7')
        # Dynamic stable IDs enumerate three actual mapped views, including duplicate app IDs.
        extra=start_client('k230.card.one',name='extra-one')
        third=start_client('k230.card.two',name='third-two')
        wait_for(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two') for n in tree_nodes(ipc('',4)))==3)
        command('enter'); time.sleep(.3)
        assert re.search(r'state mode=1 .*cards=3',logs())
        command('next'); command('next'); command('back')
        extra.terminate();third.terminate();extra.wait();third.wait()
        wait_for(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two') for n in tree_nodes(ipc('',4)))==1)
        # Top bar is handed back to Sway after restoring normal mode.
        command('enter'); ipc('card_shell down 30 20 20',check=False)
        before_keys=keys('k230.card.one');keyboard.press();wait_for(lambda:keys('k230.card.one')>before_keys)
        command('enter');before_restore=logs().count('restored focus=');ipc('output HEADLESS-1 disable')
        wait_for(lambda:logs().count('restored focus=')>before_restore)
        ipc('output HEADLESS-1 enable');time.sleep(.3)
        before_keys=keys('k230.card.one');keyboard.press();wait_for(lambda:keys('k230.card.one')>before_keys)
        assert sway.poll() is None
        results={'evidence_class':'headless-qemu-injected-input',
          'passed':['horizontal-live-deck','expand-focus-keyboard','close-timeout-retains','close-exit','private-placeholder','unavailable-placeholder','live-privacy-transition','three-dynamic-views','topbar-restores-normal','cancel-no-up-return','multi-contact-drain','output-loss-restores','upward-throw-close','global-edge-entry','persistent-button'],
          'limits':['no physical touch or panel proof','no on-board cost acceptance']}
    finally:
        if keyboard: keyboard.close()
        for proc in reversed(processes):
            if proc.poll() is None: proc.terminate()
        for proc in processes:
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()
        assert sway.returncode == 0, ('compositor teardown', sway.returncode, logs()[-1500:])
        assert 'Segmentation fault' not in logs()
    results['passed'].append('clean-compositor-teardown')
    (runtime/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results),flush=True)
if __name__=='__main__': main()
