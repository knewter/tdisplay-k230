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
import threading
import time
from card_virtual_keyboard import Keyboard
from PIL import Image, ImageChops
import shlex

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
    ap.add_argument('--native-touch',action='store_true')
    ap.add_argument('--delayed-touch',action='store_true',help='test source cadence independently of dispatch delay')
    ap.add_argument('--scaled-cache',action='store_true',help='enable bounded opaque RGB565 cache')
    ap.add_argument('--rgb565',action='store_true',help='request the RGB565 headless render format')
    ap.add_argument('--touch-first',action='store_true',help='exercise opt-in deck-to-drawer route')
    ap.add_argument('--two-axis',action='store_true',help='measure same-contact app entry and quick switch')
    ap.add_argument('--reveal-stream',action='store_true',help='capture persistent drawer/shade progress IPC')
    ap.add_argument('--rust-reveal-client',help='run the actual RISC-V Rust reveal receiver')
    ap.add_argument('--drawer-layer-client',help='native mapped layer-shell fixture for touch-first route')
    args=ap.parse_args()
    if args.delayed_touch and not args.native_touch:
        ap.error('--delayed-touch requires --native-touch')
    if args.reveal_stream and not args.touch_first:
        ap.error('--reveal-stream requires --touch-first')
    if args.rust_reveal_client and (not args.touch_first or args.reveal_stream):
        ap.error('--rust-reveal-client requires --touch-first and excludes --reveal-stream')
    if args.two_axis and (not args.touch_first or not args.native_touch):
        ap.error('--two-axis requires --touch-first and --native-touch')
    runtime=args.output or Path(tempfile.mkdtemp(prefix='k230-card-headless-'))
    if args.output and runtime.exists() and any(runtime.iterdir()):
        ap.error('--output must be a new or empty directory')
    runtime.mkdir(parents=True,exist_ok=True); runtime.chmod(0o700)
    print(f'Headless evidence: {runtime}',flush=True)
    config=runtime/'config'
    ordinary = ('for_window [app_id="^k230.card."] card_shell ordinary, floating enable, border none, resize set 100 ppt 100 ppt, move position 0 0\n'
                if args.two_axis else
                'for_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48\n')
    config.write_text('output HEADLESS-1 mode 568x1232' + (' render_bit_depth 6' if args.rgb565 else '') + '\nseat seat0 fallback true\nfocus_follows_mouse no\n' + ordinary)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_SHELL='0' if args.disabled else '1')
    env['SWAY_K230_CARD_SCALED_CACHE'] = '1' if args.scaled_cache else '0'
    reveal_messages=[]
    reveal_listener=None
    if args.reveal_stream:
        reveal_listener=socket.socket(socket.AF_UNIX)
        reveal_path=runtime/'k230-shell-rust.sock'
        reveal_listener.bind(str(reveal_path))
        reveal_path.chmod(0o600)
        reveal_listener.listen(3)
        env['SWAY_K230_CARD_REVEAL_STREAM']='1'
        env['SWAY_K230_CARD_SURFACE_SOCKET']=str(reveal_path)
        def collect_reveal():
            for _ in range(3):
                client,_=reveal_listener.accept()
                with client, client.makefile('rb') as lines:
                    for line in lines:
                        reveal_messages.append(json.loads(line))
        threading.Thread(target=collect_reveal,daemon=True).start()
    if args.rust_reveal_client:
        env['SWAY_K230_CARD_REVEAL_STREAM']='1'
        env['SWAY_K230_CARD_SURFACE_SOCKET']=str(runtime/'k230-shell-rust.sock')
    if args.touch_first:
        helper=runtime/'drawer-helper'
        helper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$XDG_RUNTIME_DIR/drawer-request"\n')
        helper.chmod(0o700)
        env['SWAY_K230_CARD_TOUCH_FIRST']='1'
        env['SWAY_K230_CARD_DRAWER_HELPER']=str(helper)
    if args.native_touch: env['SWAY_K230_CARD_TEST_INPUT']='1'
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
    def command(s):
        if args.native_touch and s.split()[0] in ('down','motion','up','cancel'): s='test-touch '+s
        return ipc('card_shell '+s)
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
        if args.rust_reveal_client:
            rust_log=(runtime/'rust-receiver.log').open('w')
            rust=subprocess.Popen([args.qemu,args.rust_reveal_client,'--serve'],env=env,
                                  stdout=rust_log,stderr=rust_log)
            processes.append(rust)
            wait_for(lambda:'ready-idle' in (runtime/'rust-receiver.log').read_text())
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
        if args.native_touch: command('test-touch init')
        time.sleep(.4)
        ipc('[app_id="k230.card.one"] focus')
        wait_for(lambda:focused()=='k230.card.one')
        time.sleep(.15)  # Let the focused floating scene reach the headless output.
        subprocess.run(['grim',str(runtime/'first-focused.png')],env=env,check=True)
        if args.two_axis:
            def capture(name):
                subprocess.run(['grim',str(runtime/name)],env=env,check=True)
                with Image.open(runtime/name) as image:
                    return image.convert('RGB')
            def color_box(frame,which):
                px=frame.load(); xs=[];ys=[]
                for y in range(0,frame.height,2):
                    for x in range(0,frame.width,2):
                        red,green,blue=px[x,y]
                        matching=(red<55 and green>35 and blue>green*1.3) if which=='blue' else \
                            (red>62 and blue>48 and green<red*.55 and blue>green*1.4)
                        if matching: xs.append(x);ys.append(y)
                assert len(xs)>200,(which,len(xs))
                return min(xs),min(ys),max(xs),max(ys)
            def near(actual,expected,tolerance=8):
                assert abs(actual-expected)<=tolerance,(actual,expected,tolerance)
            def client_blue_box(frame):
                # Exact public fixture stripe, excluding themed deck chrome.
                px=frame.load();xs=[];ys=[]
                for y in range(0,frame.height,2):
                    for x in range(0,frame.width,2):
                        red,green,blue=px[x,y]
                        if abs(red-32)<=3 and abs(green-112)<=3 and abs(blue-176)<=3:
                            xs.append(x);ys.append(y)
                assert len(xs)>200,len(xs)
                return min(xs),min(ys),max(xs),max(ys)
            original=capture('two-axis-origin.png')
            origin=color_box(original,'blue')
            command('down 70 284 1200')
            start=capture('two-axis-start.png')
            command('motion 70 284 1100')
            vertical=capture('two-axis-up.png')
            vb=color_box(vertical,'blue')
            assert vb[1]>origin[1] and vb[3]<origin[3],(origin,vb)
            # The grabbed point follows 100 px; the extreme lower pixel
            # travels farther as the full-panel view scales toward a card.
            near(vb[3]-origin[3],-100,30)
            command('motion 70 283 1100')
            bent=capture('two-axis-bend.png')
            bb=color_box(bent,'blue')
            near(bb[2]-vb[2],-1,4)
            near(bb[1],vb[1],4)
            near(bb[3],vb[3],4)
            command('motion 70 150 1100')
            lateral=capture('two-axis-left.png')
            lb=color_box(lateral,'blue')
            near(lb[2]-vb[2],-134,7)
            near(lb[1],vb[1],4)
            near(lb[3],vb[3],4)
            time.sleep(.12)
            held=capture('two-axis-held.png')
            hb=color_box(held,'blue')
            near(hb[2],lb[2],4);near(hb[1],lb[1],4);near(hb[3],lb[3],4)
            command('motion 70 284 1185')
            reversed_frame=capture('two-axis-reversed.png')
            rb=color_box(reversed_frame,'blue')
            assert rb[2]>lb[2] and rb[1]<lb[1],(lb,rb)
            command('up 70')
            wait_for(lambda:'restored focus=' in logs())
            assert focused()=='k230.card.one'
            before=logs().count('restored focus=')
            command('down 71 284 1200')
            command('motion 71 284 1100')
            command('motion 71 150 1100')
            command('up 71')
            wait_for(lambda:logs().count('restored focus=')>before)
            assert focused()=='k230.card.two'
            second=capture('two-axis-second-focused.png')
            assert second.getpixel((284,700))[0]>70
            full_red=color_box(second,'red')
            before=logs().count('restored focus=')
            command('down 72 284 1200')
            command('motion 72 384 1200')
            quick=capture('two-axis-quick-held.png')
            qb=color_box(quick,'red')
            near(qb[0]-full_red[0],100,7)
            near(qb[1],full_red[1],4);near(qb[3],full_red[3],4)
            time.sleep(.12)
            paused=capture('two-axis-quick-paused.png')
            near(color_box(paused,'red')[0],qb[0],4)
            command('motion 72 344 1200')
            reversed_quick=capture('two-axis-quick-reversed.png')
            near(color_box(reversed_quick,'red')[0],qb[0]-40,7)
            command('motion 72 420 1200')
            command('up 72')
            time.sleep(.04)
            releasing=capture('two-axis-quick-releasing.png')
            # Both sources stay at full vertical extent while the horizontal
            # carousel coasts. A forced overview would shrink these boxes.
            red_release=color_box(releasing,'red')
            assert red_release[3]-red_release[1]>950,red_release
            blue_release=color_box(releasing,'blue')
            assert blue_release[3]-blue_release[1]>850,blue_release
            wait_for(lambda:logs().count('restored focus=')>before)
            assert focused()=='k230.card.one'
            again=capture('two-axis-opposite-return.png')
            assert again.getpixel((284,700))[0]<60
            command('down 75 284 1200')
            command('motion 75 284 1100')
            home_held=capture('two-axis-home-held.png')
            home_box=client_blue_box(home_held)
            command('up 75')
            time.sleep(.04)
            home_coast=capture('two-axis-home-coasting.png')
            coast_box=client_blue_box(home_coast)
            assert coast_box[2]-coast_box[0]<home_box[2]-home_box[0],(home_box,coast_box)
            time.sleep(.30)
            home_deck=capture('two-axis-home-settled.png')
            deck_box=client_blue_box(home_deck)
            assert deck_box[2]-deck_box[0]<coast_box[2]-coast_box[0],(coast_box,deck_box)
            ipc('card_shell back')
            wait_for(lambda:focused()=='k230.card.one')
            ipc('[app_id="k230.card.two"] mark --add k230_card_private')
            command('down 73 284 1200')
            command('motion 73 150 1200')
            private=capture('two-axis-private-neighbor.png')
            # The private neighbor's purple client pixels must not appear in
            # the exposed right edge; only its neutral placeholder may show.
            right=private.crop((420,250,568,850))
            assert not any(color_box_pixel[0]>62 and color_box_pixel[2]>48 and
                           color_box_pixel[1]<color_box_pixel[0]*.55
                           for color_box_pixel in right.get_flattened_data())
            before=logs().count('restored focus=')
            command('up 73')
            wait_for(lambda:logs().count('restored focus=')>before)
            assert focused()=='k230.card.two'
            ipc('[app_id="k230.card.two"] unmark k230_card_private')
            ipc('[app_id="k230.card.one"] focus')
            wait_for(lambda:focused()=='k230.card.one')
            command('down 74 284 1200')
            command('motion 74 150 1200')
            two.terminate();two.wait(timeout=10)
            wait_for(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two')
                                for n in tree_nodes(ipc('',4)))==1)
            command('up 74')
            wait_for(lambda:focused()=='k230.card.one')
            print('PASS two-axis app entry: native QEMU pixels, held/reversed quick switch, direct release, vertical Home settlement, privacy and exit; no physical touch',flush=True)
            return
        if args.benchmark:
            command('benchmark injected'); time.sleep(3.1)
        command('enter')
        if args.touch_first:
            wait_for(lambda:'K230_CARD_SHELL mirror id=' in logs())
            if args.rust_reveal_client:
                def capture(name):
                    subprocess.run(['grim',str(runtime/name)],env=env,check=True)
                    return Image.open(runtime/name).convert('RGB')
                def receiver_logs(): return (runtime/'rust-receiver.log').read_text()
                deck=capture('rust-deck.png')
                command('down 80 284 1200')
                wait_for(lambda:'map-request' in receiver_logs())
                wait_for(lambda:'configure 568x1232' in receiver_logs())
                command('motion 80 284 900')
                wait_for(lambda:receiver_logs().count('commit')>=2)
                time.sleep(.1)
                mid=capture('rust-drawer-mid.png')
                command('motion 80 284 1180')
                wait_for(lambda:receiver_logs().count('commit')>=3)
                time.sleep(.1)
                reversed_frame=capture('rust-drawer-reversed.png')
                command('up 80')
                wait_for(lambda:'unmap' in receiver_logs())
                assert mid.getpixel((10,1000))!=deck.getpixel((10,1000))
                assert reversed_frame.getpixel((10,1000))==deck.getpixel((10,1000))
                assert 'touch-down 80' not in receiver_logs()
                command('down 81 284 1200')
                command('motion 81 284 400')
                command('up 81')
                wait_for(lambda:'map-request' in receiver_logs())
                time.sleep(.5)
                opened=capture('rust-drawer-open.png')
                assert opened.getpixel((10,1000))!=deck.getpixel((10,1000))
                command('down 82 284 1000')
                wait_for(lambda:'touch-down 82' in receiver_logs())
                command('up 82')
                subprocess.run([args.qemu,args.rust_reveal_client,'--surface','hide'],env=env,check=True)
                wait_for(lambda:receiver_logs().count('unmap')>=2)
                command('down 83 284 10')
                command('motion 83 284 300')
                time.sleep(.15)
                shade=capture('rust-shade-mid.png')
                command('up 83')
                assert shade.getpixel((10,100))!=deck.getpixel((10,100))
                print('PASS Rust reveal receiver: actual QEMU pixels, reversal, settle and input routing; no physical touch',flush=True)
                return
            if args.reveal_stream:
                command('down 80 284 1200')
                wait_for(lambda:any(row['phase']=='begin' for row in reveal_messages))
                if args.drawer_layer_client:
                    layer_log=(runtime/'drawer.log').open('w')
                    drawer=subprocess.Popen([args.drawer_layer_client],env=env,
                                            stdout=layer_log,stderr=layer_log)
                    processes.append(drawer)
                    wait_for(lambda:'drawer mapped' in (runtime/'drawer.log').read_text())
                    subprocess.run(['grim',str(runtime/'reveal-layer.png')],env=env,check=True)
                    assert Image.open(runtime/'reveal-layer.png').convert('RGB').getpixel((284,1000))==(255,0,255)
                command('motion 80 284 1100')
                command('motion 80 284 1120')
                command('up 80')
                wait_for(lambda:any(row['phase']=='finish' for row in reveal_messages))
                if args.drawer_layer_client:
                    drawer.terminate();drawer.wait(timeout=10);layer_log.close()
                command('down 81 284 10')
                command('motion 81 284 100')
                command('motion 81 284 40')
                command('up 81')
                wait_for(lambda:sum(row['phase']=='finish' for row in reveal_messages)==2)
                command('down 82 284 10')
                command('down 83 284 20')
                command('up 83')
                command('up 82')
                wait_for(lambda:any(row['phase']=='cancel' for row in reveal_messages))
                groups={}
                for row in reveal_messages:
                    groups.setdefault(row['seq'],[]).append(row)
                assert len(groups)==3,groups
                drawer_rows,shade_rows,cancel_rows=list(groups.values())
                assert drawer_rows[0]['surface']=='drawer' and drawer_rows[0]['phase']=='begin'
                assert drawer_rows[-1]['phase']=='finish' and drawer_rows[-1]['progress']==1000
                updates=[row['progress'] for row in drawer_rows if row['phase']=='update']
                assert len(updates)>=2 and updates[-2]>updates[-1]>0,updates
                assert shade_rows[0]['surface']=='shade' and shade_rows[-1]['progress']==0
                assert cancel_rows[-1]['phase']=='cancel'
                assert not (runtime/'drawer-request').exists()
                assert 'restored focus=' not in logs()
                print('PASS continuous reveal IPC: QEMU Sway and mapped overlay; no Rust pixels/physical touch',flush=True)
                return
            command('down 90 284 10')
            command('motion 90 284 110')
            command('up 90')
            request=runtime/'drawer-request'
            wait_for(request.exists)
            assert request.read_text().splitlines()==['--surface','shade']
            request.unlink()
            # This was the legacy Back button. A touch-first deck must not
            # restore the app or consume it as a permanent control.
            command('down 81 500 80')
            command('up 81')
            command('next')
            assert 'restored focus=' not in logs()
            command('down 80 284 1200')
            command('motion 80 284 1100')
            command('up 80')
            wait_for(request.exists)
            assert request.read_text().splitlines()==['--surface','drawer']
            # The helper may exit without mapping; the deck remains usable.
            command('next')
            assert 'restored focus=' not in logs()
            if args.drawer_layer_client:
                subprocess.run(['grim',str(runtime/'before-drawer.png')],env=env,check=True)
                layer_log=(runtime/'drawer.log').open('w')
                drawer=subprocess.Popen([args.drawer_layer_client],env=env,
                                        stdout=layer_log,stderr=layer_log)
                processes.append(drawer)
                wait_for(lambda:'drawer mapped' in (runtime/'drawer.log').read_text())
                subprocess.run(['grim',str(runtime/'with-drawer.png')],env=env,check=True)
                before=Image.open(runtime/'before-drawer.png').convert('RGB')
                with_drawer=Image.open(runtime/'with-drawer.png').convert('RGB')
                assert before.getpixel((284,1000)) != (255,0,255)
                assert with_drawer.getpixel((284,1000)) == (255,0,255)
                blocked=ipc('card_shell down 85 284 450',check=False)
                assert not blocked[0]['success'],blocked
                drawer.terminate();drawer.wait(timeout=10);layer_log.close()
                command('next')
            before_restore=logs().count('restored focus=')
            subprocess.run(['grim',str(runtime/'before-expand.png')],env=env,check=True)
            command('down 87 284 450')
            command('up 87')
            time.sleep(.06)
            subprocess.run(['grim',str(runtime/'during-expand.png')],env=env,check=True)
            wait_for(lambda:logs().count('restored focus=')>before_restore)
            expand_before=Image.open(runtime/'before-expand.png').convert('RGB')
            expand_middle=Image.open(runtime/'during-expand.png').convert('RGB')
            assert ImageChops.difference(expand_before,expand_middle).getbbox()
            assert len(expand_middle.getcolors(1_000_000) or [])>5
            request.unlink()
            command('down 91 284 10')
            command('motion 91 284 110')
            command('up 91')
            wait_for(request.exists)
            assert request.read_text().splitlines()==['--surface','shade']
            before_restore=logs().count('restored focus=')
            command('down 92 284 1200')
            subprocess.run(['grim',str(runtime/'entry-start.png')],env=env,check=True)
            command('motion 92 284 1164')
            subprocess.run(['grim',str(runtime/'entry-middle.png')],env=env,check=True)
            command('motion 92 284 1120')
            subprocess.run(['grim',str(runtime/'entry-end.png')],env=env,check=True)
            start=Image.open(runtime/'entry-start.png').convert('RGB')
            middle=Image.open(runtime/'entry-middle.png').convert('RGB')
            end=Image.open(runtime/'entry-end.png').convert('RGB')
            assert ImageChops.difference(start,middle).getbbox()
            assert ImageChops.difference(middle,end).getbbox()
            assert all(len(image.getcolors(1_000_000) or [])>5 for image in (start,middle,end))
            command('motion 92 284 1198')
            command('up 92')
            wait_for(lambda:logs().count('restored focus=')>before_restore)
            print('PASS touch-first drawer route: actual cross-built Sway under QEMU; no physical touch',flush=True)
            return
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
        time.sleep(.15)
        subprocess.run(['grim',str(runtime/'second-focused.png')],env=env,check=True)
        first_pixel=Image.open(runtime/'first-focused.png').convert('RGB').getpixel((284,700))
        second_pixel=Image.open(runtime/'second-focused.png').convert('RGB').getpixel((284,700))
        # These synthetic clients are blue and purple respectively. The
        # keyboard-focus assertion alone missed a lower, obscured floater.
        assert first_pixel[0]<60 and second_pixel[0]>60,(first_pixel,second_pixel)
        keyboard.press(); wait_for(lambda:keys('k230.card.two')==1)
        if args.benchmark:
            time.sleep(3.1);command('benchmark-stop')
        command('enter'); command('previous')
        if args.delayed_touch:
            # Identical geometry with independently controlled event time.
            # Native wlroots -> cursor -> seat routing remains in use.
            mask=(1<<32)-1
            def stamp(value): return value & mask
            def close_count(): return logs().count('K230_CARD_SHELL close-request')
            for contact,slow,paused in ((38,True,False),(39,False,True)):
                before=close_count(); base=int(time.monotonic()*1000)-3000
                command(f'down {contact} 284 500 {stamp(base)}')
                command(f'motion {contact} 284 420 {stamp(base+100)}')
                final=base+(1100 if slow else 120)
                command(f'motion {contact} 284 300 {stamp(final)}')
                command(f'up {contact} {stamp(final+(200 if paused else 10))}')
                time.sleep(.2)
                assert close_count()==before, 'slow or paused source must not become a throw'
                command('back');ipc('[app_id="k230.card.one"] focus');command('enter')
            before=close_count();base=int(time.monotonic()*1000)-3000
            command(f'down 40 284 500 {stamp(base)}')
            command(f'motion 40 284 420 {stamp(base+100)}')
            time.sleep(.45)  # dispatch says too slow; source reports a fast throw
            command(f'motion 40 284 300 {stamp(base+120)}')
            requested_at=time.monotonic()
            command(f'up 40 {stamp(base+130)}')
            wait_for(lambda:close_count()==before+1)
            wait_for(lambda:'message=6' in logs())
            assert time.monotonic()-requested_at>=1.3, 'timeout must start at close dispatch'
            for contact,duplicate in ((42,False),(43,True)):
                command('back');ipc('[app_id="k230.card.one"] focus');command('enter')
                before=close_count();base=int(time.monotonic()*1000)-3000
                timeouts=logs().count('message=6')
                command(f'down {contact} 284 500 {stamp(base)}')
                command(f'motion {contact} 284 400 {stamp(base+100)}')
                command(f'motion {contact} 284 350 {stamp(base+120)}')
                command(f'motion {contact} 284 {350 if duplicate else 325} {stamp(base+120)}')
                command(f'up {contact} {stamp(base+121)}')
                wait_for(lambda:close_count()==before+1)
                wait_for(lambda:logs().count('message=6')>timeouts)
            for contact,reversal in ((44,True),(45,False)):
                command('back');ipc('[app_id="k230.card.one"] focus');command('enter')
                before=close_count();base=int(time.monotonic()*1000)-3000
                command(f'down {contact} 284 500 {stamp(base)}')
                command(f'motion {contact} 284 325 {stamp(base+100)}')
                command(f'motion {contact} 284 {350 if reversal else 325} {stamp(base+100)}')
                command(f'up {contact} {stamp(base+(101 if reversal else 251))}')
                time.sleep(.2)
                assert close_count()==before, 'repeated timestamp must not turn reversal or held release into close'
        else:
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
        # A real XDG popup is outside the mirrored view tree. A new popup
        # must restore normal mode before rendering, and block deck reentry.
        xml=Path('/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml')
        if not xml.exists(): raise RuntimeError('native wayland-protocols XDG XML is required')
        subprocess.run(['wayland-scanner','client-header',str(xml),str(runtime/'xdg-shell-client-protocol.h')],check=True)
        subprocess.run(['wayland-scanner','private-code',str(xml),str(runtime/'xdg-shell-protocol.c')],check=True)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-I'+str(runtime),str(Path(__file__).with_name('card_popup_client.c')),str(runtime/'xdg-shell-protocol.c'),'-o',str(runtime/'popup-client')]+flags,check=True)
        popup_log=(runtime/'popup.txt').open('w')
        popup=subprocess.Popen([str(runtime/'popup-client')],stdin=subprocess.PIPE,stdout=popup_log,stderr=popup_log,env=env)
        processes.append(popup)
        wait_for(lambda:any(n.get('app_id')=='k230.card.popup' for n in tree_nodes(ipc('',4))))
        ipc('[app_id="k230.card.popup"] mark --add k230_card_private')
        command('enter');before_restore=logs().count('restored focus=')
        popup.stdin.write(b'x');popup.stdin.flush()
        wait_for(lambda:'popup' in (runtime/'popup.txt').read_text())
        wait_for(lambda:logs().count('restored focus=')>before_restore)
        assert not ipc('card_shell enter',check=False)[0]['success']
        popup.terminate();popup.wait();popup_log.close()
        wait_for(lambda:all(n.get('app_id')!='k230.card.popup' for n in tree_nodes(ipc('',4))))
        command('enter');command('back')
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
        if args.scaled_cache:
            cache = re.findall(r'K230_CARD_SHELL scaled-cache hits=(\d+) misses=(\d+) fallbacks=(\d+) bytes=(\d+)', logs())
            assert cache and all(int(value) > 0 for value in cache[-1][:3]), 'cache hit, rebuild, and fallback paths were not exercised on RGB565'
            assert any(int(row[3]) > 0 for row in cache), 'cache never held scaled pixels'
            assert int(cache[-1][3]) == 0, 'cached pixels survived normal shell restore'
        results={'evidence_class':'headless-qemu-injected-input',
          'source_time_checks': ['slow-source-no-close','paused-source-no-close','delayed-fast-source-close','full-dispatch-timeout',
                                 'same-ms-motion-close','same-ms-duplicate-close','same-ms-reversal-no-close','same-ms-held-no-close'] if args.delayed_touch else [],
          'passed':['horizontal-live-deck','expand-focus-keyboard','close-timeout-retains','close-exit','private-placeholder','unavailable-placeholder','live-privacy-transition','three-dynamic-views','popup-normal-fallback','topbar-restores-normal','cancel-no-up-return','multi-contact-drain','output-loss-restores','upward-throw-close','global-edge-entry','persistent-button'],
          'limits':['no physical touch or panel proof','no on-board cost acceptance']}
    finally:
        if reveal_listener: reveal_listener.close()
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
    results['input_route']='wlroots-touch-device-through-cursor-and-seat' if args.native_touch else 'direct-card-ipc'
    (runtime/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results),flush=True)
if __name__=='__main__': main()
