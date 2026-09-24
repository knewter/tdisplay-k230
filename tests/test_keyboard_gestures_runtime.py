#!/usr/bin/env python3
"""Real QEMU Sway/wvkbd two-contact geometry and pixel proof; no panel claim."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time
from PIL import Image, ImageChops


def wait_for(fn, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = fn()
        if result:
            return result
        time.sleep(.04)
    raise AssertionError('timed out waiting for native state')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('sway', 'client', 'keyboard', 'output'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    ap.add_argument('--fail-hide', action='store_true',
                    help='exercise bounded recovery when the trusted hide helper fails')
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    config = out / 'sway.conf'
    config.write_text('''output HEADLESS-1 mode 568x1232
seat seat0 fallback true
focus_follows_mouse no
floating_maximum_size -1 x -1
default_floating_border none
for_window [tiling app_id="^k230.card."] card_shell ordinary, floating enable, resize set 100 ppt 100 ppt, move position 0 0
''')
    helper = out / 'keyboard-signal'
    helper.write_text('''#!/bin/sh
set -eu
case "$1" in
 show) signal=USR2 ;;
 hide) signal=USR1 ;;
 *) exit 2 ;;
esac
printf '%s\\n' "$1" >> "$XDG_RUNTIME_DIR/keyboard-actions"
if [ "$1" = hide ] && [ "${K230_FIXTURE_FAIL_HIDE:-0}" = 1 ]; then exit 1; fi
kill -"$signal" "$(cat "$XDG_RUNTIME_DIR/keyboard.pid")"
''')
    helper.chmod(0o700)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
               SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TOUCH_FIRST='1',
               SWAY_K230_CARD_TEST_INPUT='1', SWAY_K230_KEYBOARD_GESTURES='1',
               SWAY_K230_KEYBOARD_HEIGHT='420', SWAY_K230_KEYBOARD_SIGNAL=str(helper))
    if args.fail_hide: env['K230_FIXTURE_FAIL_HIDE'] = '1'
    processes = []
    streams = []
    def launch(name, cmd):
        stream = (out / (name + '.log')).open('w')
        streams.append(stream)
        process = subprocess.Popen(cmd, env=env, stdout=stream, stderr=stream)
        processes.append(process)
        return process
    def ipc(command='', kind=0):
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(8)
        sock.connect(str(next(out.glob('sway-ipc.*.sock'))))
        data = command.encode()
        sock.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)
        def read(n):
            result = b''
            while len(result) < n:
                chunk = sock.recv(n-len(result))
                assert chunk, 'IPC closed'
                result += chunk
            return result
        header = read(14)
        length, _ = struct.unpack('=II', header[6:])
        reply = json.loads(read(length))
        sock.close()
        if kind == 0:
            assert all(row['success'] for row in reply), (command, reply)
        return reply
    def app_height():
        pending = [ipc('', 4)]
        while pending:
            node = pending.pop()
            pending.extend(node.get('nodes', []) + node.get('floating_nodes', []))
            if node.get('app_id') == 'k230.card.one':
                return node['rect']['height']
        return None
    def touch(kind, contact=None, x=None, y=None, stamp=None):
        words = ['card_shell', 'test-touch', kind]
        if contact is not None: words.append(str(contact))
        if x is not None: words.extend([str(x), str(y)])
        if stamp is not None: words.append(str(stamp))
        ipc(' '.join(words))
    def capture(name):
        subprocess.run(['grim', str(out/name)], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        with Image.open(out/name) as png:
            assert png.size == (568,1232), png.size
            return png.convert('RGB')
    def grip_edge(frame):
        # The compositor's translucent fallback grip brush paints a bounded
        # dark band; the live client underneath shifts its exact RGB slightly.
        for y in range(600, 1209):
            if all(23 <= frame.getpixel((500, row))[0] <= 28 and
                   33 <= frame.getpixel((500, row))[1] <= 43 and
                   46 <= frame.getpixel((500, row))[2] <= 59
                   for row in range(y, y+24)):
                return y
        raise AssertionError('painted grip edge absent')
    def key_presses():
        rows = [json.loads(row) for row in (out/'client.log').read_text().splitlines()
                if row.startswith('{')]
        return max((row.get('key_presses', 0) for row in rows), default=0)
    try:
        sway = launch('sway', [args.qemu, args.sway, '-c', str(config), '-d'])
        wait_for(lambda: next((p.name for p in out.glob('wayland-*') if p.is_socket()), None))
        wait_for(lambda: next((p.name for p in out.glob('sway-ipc.*.sock') if p.is_socket()), None))
        env['WAYLAND_DISPLAY'] = next(p.name for p in out.glob('wayland-*') if p.is_socket())
        client_cmd = ([args.qemu] if Path(args.client).read_bytes()[18:20] == b'\xf3\x00' else [])
        client = launch('client', client_cmd + [args.client, '--app-id', 'k230.card.one'])
        try:
            wait_for(lambda: app_height() == 1232)
        except AssertionError:
            (out/'startup-tree.json').write_text(json.dumps(ipc('',4),indent=2)+'\n')
            raise AssertionError(f'client startup geometry={app_height()} exit={client.poll()}')
        keyboard = launch('wvkbd', [args.qemu, args.keyboard, '-H', '420', '--hidden'])
        (out/'keyboard.pid').write_text(str(keyboard.pid))
        wait_for(lambda: 'Found 2 layers' in (out/'wvkbd.log').read_text())
        touch('init')
        baseline = capture('hidden.png')
        stamp = int(time.monotonic()*1000) & 0xffffffff
        touch('down', 1, 100, 1200, stamp)
        touch('down', 2, 190, 1200, stamp+30)
        assert not (out/'keyboard-actions').exists(), 'stationary chord showed keyboard'
        touch('motion', 1, 100, 1100, stamp+55)
        wait_for(lambda: (out/'keyboard-actions').exists() and
                 'show' in (out/'keyboard-actions').read_text())
        touch('motion', 2, 190, 1100, stamp+60)
        held_height = wait_for(lambda: app_height() if app_height() and app_height() < 1232 else None)
        assert 1130 <= held_height <= 1134, held_height
        held = capture('held.png')
        assert abs(grip_edge(held)-1132) <= 2, grip_edge(held)
        time.sleep(.35)
        paused = capture('paused.png')
        assert app_height() == held_height, (held_height, app_height())
        # The live client animates above the keyboard; only the revealed
        # keyboard/grip strip should be still while both contacts are held.
        strip = (0, held_height, 568, 1232)
        assert ImageChops.difference(held.crop(strip), paused.crop(strip)).getbbox() is None, \
            'held keyboard drifted'
        touch('motion', 1, 100, 1150, stamp+90)
        touch('motion', 2, 190, 1150, stamp+95)
        reverse_height = wait_for(lambda: app_height() if app_height() > held_height+30 else None)
        assert 1180 <= reverse_height <= 1184, reverse_height
        reverse = capture('reverse.png')
        assert abs(grip_edge(reverse)-1182) <= 2, grip_edge(reverse)
        assert ImageChops.difference(held, reverse).getbbox(), 'reverse pixels unchanged'
        touch('up', 1, stamp=stamp+400)
        touch('up', 2, stamp=stamp+401)
        wait_for(lambda: app_height() == 1232)
        wait_for(lambda: (out/'keyboard-actions').read_text().count('hide') >= 1)
        if args.fail_hide:
            wait_for(lambda: app_height() == 756, timeout=8)
            before_keys = key_presses()
            touch('down', 9, 142, 898, stamp+700)
            touch('up', 9, stamp=stamp+710)
            wait_for(lambda: key_presses() > before_keys)
            assert sway.poll() is None and keyboard.poll() is None
            (out/'result.json').write_text(json.dumps({
                'class':'headless-qemu-failed-hide-helper-recovery',
                'source_sway':args.sway, 'keyboard':args.keyboard,
                'recovered_usable_height':756,
                'key_presses_after_recovery':key_presses(),
                'physical_touch':False,'panel_capture':False},indent=2)+'\n')
            print('PASS failed hide helper recovers shown keyboard and ordinary keys; no physical proof')
            return
        hidden_again = capture('hidden-again.png')
        assert ImageChops.difference(held, hidden_again).getbbox(), 'keyboard not fully hidden'
        # A second chord reaches the shown endpoint and exposes a separate grip.
        stamp += 1000
        touch('down', 3, 100, 1200, stamp)
        touch('down', 4, 190, 1200, stamp+30)
        touch('motion', 3, 100, 1100, stamp+50)
        wait_for(lambda: (out/'keyboard-actions').read_text().count('show') >= 2)
        touch('motion', 3, 100, 780, stamp+70)
        touch('motion', 4, 190, 780, stamp+71)
        touch('up', 3, stamp=stamp+150)
        touch('up', 4, stamp=stamp+151)
        shown_height = wait_for(lambda: app_height() if app_height() == 756 else None)
        shown = capture('shown.png')
        assert abs(grip_edge(shown)-756) <= 2, grip_edge(shown)
        assert ImageChops.difference(baseline, shown).getbbox(), 'shown keyboard lacks pixels'
        # Cancel a partly dragged grip: the same live keyboard and app must
        # return to shown geometry, and a fresh ordinary key touch must work.
        touch('down', 5, 100, 780, stamp+500)
        touch('motion', 5, 100, 990, stamp+530)
        wait_for(lambda: app_height() == 966)
        touch('cancel')
        wait_for(lambda: app_height() == 756)
        before_keys = key_presses()
        touch('down', 6, 142, 898, stamp+700)
        touch('up', 6, stamp=stamp+710)
        wait_for(lambda: key_presses() > before_keys)
        touch('down', 7, 100, 780, stamp+800)
        touch('motion', 7, 100, 990, stamp+830)
        grip_height = wait_for(lambda: app_height() if app_height() > 900 else None)
        assert 964 <= grip_height <= 968, grip_height
        grip_frame = capture('grip-held.png')
        assert abs(grip_edge(grip_frame)-966) <= 2, grip_edge(grip_frame)
        # A stale release beyond the midpoint commits the hide; the 210px
        # capture above remains a held, one-to-one displacement check.
        touch('motion', 7, 100, 1080, stamp+850)
        touch('up', 7, stamp=stamp+1100)
        wait_for(lambda: app_height() == 1232)
        wait_for(lambda: (out/'keyboard-actions').read_text().count('hide') >= 2)
        assert client.poll() is None and sway.poll() is None
        result = {'class':'headless-qemu-native-sway-wvkbd-injected-touch',
                  'source_sway':args.sway, 'keyboard':args.keyboard,
                  'heights':{'hidden':1232,'show_held':held_height,'reversed':reverse_height,
                             'shown':shown_height,'grip_held':grip_height,'hidden_final':1232},
                  'actions':(out/'keyboard-actions').read_text().splitlines(),
                  'key_presses_after_cancel':key_presses(),
                  'screenshots':['hidden.png','held.png','paused.png','reverse.png',
                                 'hidden-again.png','shown.png','grip-held.png'],
                  'physical_touch':False,'panel_capture':False}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS native Sway/wvkbd chord, held/reversed pixels, grip and usable area; no physical proof')
    finally:
        for proc in reversed(processes):
            if proc.poll() is None: proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill()
        for stream in streams: stream.close()

if __name__ == '__main__': main()
