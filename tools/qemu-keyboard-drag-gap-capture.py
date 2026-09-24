#!/usr/bin/env python3
"""Reproduce the keyboard-drag exclusive-zone gap: start the app while the
keyboard is already shown (so the client's one-time buffer is drawn at the
SHRUNK size), then grip-drag the keyboard down without releasing. A client
that never redraws at the larger size leaves a real margin between its old
buffer and the moved keyboard; capture what's visible in that margin.
No physical/panel claim: headless QEMU with IPC-injected touch only.
"""
import argparse, json, os, socket, struct, subprocess, sys, time
from pathlib import Path
from PIL import Image


def wait_for(fn, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        r = fn()
        if r:
            return r
        time.sleep(.04)
    raise AssertionError('timed out waiting for native state')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('sway', 'client', 'keyboard', 'output'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
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
kill -"$signal" "$(cat "$XDG_RUNTIME_DIR/keyboard.pid")"
''')
    helper.chmod(0o700)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
               SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TOUCH_FIRST='1',
               SWAY_K230_CARD_TEST_INPUT='1', SWAY_K230_KEYBOARD_GESTURES='1',
               SWAY_K230_KEYBOARD_HEIGHT='420', SWAY_K230_KEYBOARD_SIGNAL=str(helper))
    processes, streams = [], []
    def launch(name, cmd):
        stream = (out / (name + '.log')).open('w')
        streams.append(stream)
        p = subprocess.Popen(cmd, env=env, stdout=stream, stderr=stream)
        processes.append(p)
        return p
    def ipc(command='', kind=0):
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(8)
        sock.connect(str(next(out.glob('sway-ipc.*.sock'))))
        data = command.encode()
        sock.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)
        def read(n):
            r = b''
            while len(r) < n:
                c = sock.recv(n - len(r))
                assert c
                r += c
            return r
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
        subprocess.run(['grim', str(out / name)], env=env, check=True, stdout=subprocess.DEVNULL)
        with Image.open(out / name) as png:
            assert png.size == (568, 1232), png.size
            return png.convert('RGB')
    try:
        sway = launch('sway', [args.qemu, args.sway, '-c', str(config), '-d'])
        wait_for(lambda: next((p.name for p in out.glob('wayland-*') if p.is_socket()), None))
        wait_for(lambda: next((p.name for p in out.glob('sway-ipc.*.sock') if p.is_socket()), None))
        env['WAYLAND_DISPLAY'] = next(p.name for p in out.glob('wayland-*') if p.is_socket())
        # Keyboard shown from boot (no --hidden): the app's first-ever
        # committed geometry is the SHRUNK 756px height, so its one-time
        # buffer is drawn that small.
        keyboard = launch('wvkbd', [args.qemu, args.keyboard, '-H', '420'])
        (out / 'keyboard.pid').write_text(str(keyboard.pid))
        wait_for(lambda: 'Found 2 layers' in (out / 'wvkbd.log').read_text())
        client_cmd = ([args.qemu] if Path(args.client).read_bytes()[18:20] == b'\xf3\x00' else [])
        client = launch('client', client_cmd + [args.client, '--app-id', 'k230.card.one',
                                                  '--stall-resize-ms', '4000'])
        wait_for(lambda: app_height() == 756)
        touch('init')
        before = capture('before-drag.png')
        # One-finger grip drag downward (hide), held mid-gesture without a
        # release: the compositor's usable_area grows continuously toward
        # 1232, but this client's buffer, drawn once at 756, never redraws.
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        touch('down', 20, 100, 780, stamp)
        touch('motion', 20, 100, 1050, stamp + 60)
        target = wait_for(lambda: app_height() if app_height() and app_height() > 900 else None)
        time.sleep(.2)  # give the client every chance to redraw if it were going to
        mid_drag = capture('mid-drag.png')
        gap_top = 756 + 6
        gap_bottom = min(target - 6, 1226)
        sample_y = (gap_top + gap_bottom) // 2
        gap_rgb = mid_drag.getpixel((284, sample_y))
        before_rgb = before.getpixel((284, 700))
        result = {
            'class': 'headless-qemu-injected-keyboard-drag-gap',
            'physical_touch': False, 'panel_capture': False,
            'app_height_before_drag': 756,
            'app_height_mid_drag_usable': target,
            'gap_sample_xy': [284, sample_y],
            'gap_sample_rgb': gap_rgb,
            'before_sample_rgb': before_rgb,
        }
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        touch('up', 20, stamp=stamp + 400)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        for s in streams:
            s.close()


if __name__ == '__main__':
    main()
