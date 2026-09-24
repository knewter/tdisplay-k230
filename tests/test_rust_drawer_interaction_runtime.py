#!/usr/bin/env python3
"""Headless QEMU proof of real Rust drawer scroll, launch handoff, and dismiss.

Synthetic touch and a private desktop catalog; never physical panel evidence.
"""
import argparse
import json, os, pathlib, socket, struct, subprocess, time
from PIL import Image, ImageChops

parser=argparse.ArgumentParser(description=__doc__)
for field in ('sway','swaymsg','rust','client','output'):
    parser.add_argument('--'+field,required=True)
parser.add_argument('--qemu',default='/usr/bin/qemu-riscv64-static')
args=parser.parse_args()
out=pathlib.Path(args.output)
out.mkdir(mode=0o700,exist_ok=False)
qemu=args.qemu
sway=args.sway
swaymsg=args.swaymsg
rust=args.rust
client=args.client
config=out/'sway.conf'
config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\nfor_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48\n')
binpath=out/'swaymsg'; binpath.write_text(f'#!/bin/sh\nexec {qemu} {swaymsg} "$@"\n');binpath.chmod(0o700)
apps=out/'data/applications';apps.mkdir(parents=True)
marker=out/'launch-marker'
launch=out/'launch';launch.write_text('#!/bin/sh\nprintf "%s\\n" "$1" >> "$XDG_RUNTIME_DIR/launch-marker"\n');launch.chmod(0o700)
for i in range(20):
    (apps/f'k230-fixture-{i:02}.desktop').write_text('[Desktop Entry]\nType=Application\nName=Fixture %02d\nExec=%s %02d\n' % (i,launch,i))
env=dict(os.environ,XDG_RUNTIME_DIR=str(out),XDG_DATA_HOME=str(out/'data'),XDG_DATA_DIRS=str(out/'data'),
         WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',
         SWAY_K230_CARD_SHELL='1',SWAY_K230_CARD_TOUCH_FIRST='1',SWAY_K230_CARD_TEST_INPUT='1',
         SWAY_K230_CARD_REVEAL_STREAM='1',SWAY_K230_CARD_SURFACE_SOCKET=str(out/'k230-shell-rust.sock'),
         K230_SWAYMSG=str(binpath))
logs={}; processes=[]
def spawn(name,argv):
    log=(out/(name+'.log')).open('w');logs[name]=log
    p=subprocess.Popen(argv,env=env,stdout=log,stderr=log)
    processes.append(p);return p
def text(name): return (out/(name+'.log')).read_text()
def wait(predicate,seconds=20):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=predicate()
        if value:return value
        time.sleep(.05)
    raise AssertionError('timeout')
def ipc(command,kind=0):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(5);s.connect(str(next(out.glob('sway-ipc.*.sock'))))
        data=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(data),kind)+data)
        def read(n):
            data=b''
            while len(data)<n:
                chunk=s.recv(n-len(data));assert chunk,'IPC closed';data+=chunk
            return data
        header=read(14);n,_=struct.unpack('=II',header[6:]);result=json.loads(read(n))
        if kind==0:assert all(r['success'] for r in result),(command,result)
        return result
def touch(action): return ipc('card_shell test-touch '+action)
def capture(name):
    subprocess.run(['grim',str(out/name)],env=env,check=True)
    return Image.open(out/name).convert('RGB')
try:
    spawn('sway',[qemu,sway,'-c',str(config),'-d'])
    wait(lambda:'Running compositor on wayland display' in text('sway'),60)
    env['WAYLAND_DISPLAY']=next(p.name for p in out.glob('wayland-*') if not p.name.endswith('.lock'))
    env['SWAYSOCK']=str(next(out.glob('sway-ipc.*.sock')))
    spawn('rust',[qemu,rust,'--serve'])
    wait(lambda:'ready-idle' in text('rust'))
    spawn('client',[client,'--app-id','k230.card.one'])
    wait(lambda:'k230.card.one' in json.dumps(ipc('',4)))
    ipc('card_shell test-touch init')
    ipc('card_shell enter')
    wait(lambda:'K230_CARD_SHELL mirror id=' in text('sway'))
    deck=capture('deck.png')
    touch('down 1 284 1200');touch('motion 1 284 400');touch('up 1')
    wait(lambda:'map-request' in text('rust') and text('rust').count('commit')>=2)
    time.sleep(.5)
    opened=capture('drawer-open.png')
    assert opened.getpixel((10,1000))!=deck.getpixel((10,1000))
    # The list has twenty rows, enough to scroll the 826-pixel viewport.
    touch('down 2 284 750');wait(lambda:'touch-down 2' in text('rust'))
    touch('motion 2 284 500');touch('up 2')
    wait(lambda:'touch-move 2' in text('rust'))
    time.sleep(.2)
    scrolled=capture('drawer-scrolled.png')
    delta=ImageChops.difference(opened.crop((40,380,528,1100)),scrolled.crop((40,380,528,1100)))
    assert delta.getbbox(), 'drawer pixels did not scroll'
    touch('down 3 284 450');wait(lambda:'touch-down 3' in text('rust'))
    touch('up 3')
    wait(lambda:'app-launch-requested' in text('rust') or 'app-launch-failed' in text('rust'),8)
    assert 'app-launch-requested' in text('rust'), text('rust')[-1000:]
    wait(lambda:marker.exists() and marker.read_text().strip())
    assert "Handling command 'card_shell back'" in text('sway')
    launched=marker.read_text().strip().splitlines()
    # Resume deck for a separate downward-close case.
    ipc('card_shell enter')
    touch('down 4 284 1200');touch('motion 4 284 400');touch('up 4')
    wait(lambda:text('rust').count('map-request')>=2 and text('rust').count('commit')>=4)
    time.sleep(.4)
    touch('down 5 284 350');wait(lambda:'touch-down 5' in text('rust'))
    touch('motion 5 284 510');touch('up 5')
    wait(lambda:text('rust').count('unmap')>=2)
    time.sleep(.15)
    dismissed=capture('drawer-dismissed.png')
    assert dismissed.getpixel((10,1000))==deck.getpixel((10,1000))
    assert marker.read_text().strip().splitlines()==launched
    result={'result':'PASS','class':'headless-qemu-native-touch','scroll_pixels_changed':True,
                      'launched':launched,'back_command':True,'dismiss_preserved_deck':True,
                      'sway':sway,'rust':rust}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
finally:
    for p in reversed(processes):
        if p.poll() is None:p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill()
    for log in logs.values():log.close()
