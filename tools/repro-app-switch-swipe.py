#!/usr/bin/env python3
"""Reproduce the reported app-switch swipe glitch under headless QEMU with
per-step compositor capture: two ordinary maximized apps, a bottom-edge
horizontal swipe from (420,1226) to (120,1226) via `card_shell test-touch`,
single-stepped so every capture corresponds to one injected touch event.
"""
import argparse, json, os, pathlib, socket, struct, subprocess, time

ap = argparse.ArgumentParser()
ap.add_argument('--sway', required=True)
ap.add_argument('--client', required=True)
ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
ap.add_argument('--output', required=True, type=pathlib.Path)
args = ap.parse_args()
out = args.output
out.mkdir(mode=0o700, parents=True)

config = out / 'sway.conf'
config.write_text(
    'output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n'
    'focus_follows_mouse no\n'
    'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
    'border none, resize set 100 ppt 100 ppt, move position 0 0\n')
env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS='headless',
           WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
           SWAY_K230_CARD_TOUCH_FIRST='1', SWAY_K230_CARD_TEST_INPUT='1')
procs = []
log = (out / 'sway.log').open('w')
procs.append(subprocess.Popen([args.qemu, args.sway, '-c', str(config), '-d'], env=env,
                               stdout=log, stderr=log))


def logs():
    return (out / 'sway.log').read_text()


def wait(pred, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(.03)
    raise AssertionError('timeout: ' + logs()[-4000:])


def ipc(command, kind=0):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(8)
        s.connect(str(next(out.glob('sway-ipc.*.sock'))))
        data = command.encode()
        s.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)

        def read(n):
            d = b''
            while len(d) < n:
                chunk = s.recv(n - len(d))
                assert chunk
                d += chunk
            return d
        header = read(14)
        n, _ = struct.unpack('=II', header[6:])
        result = json.loads(read(n))
        if kind == 0:
            assert all(r['success'] for r in result), (command, result)
        return result


def command(s):
    return ipc('card_shell ' + s)


frames = []


def capture(label):
    idx = len(frames)
    name = f'frame-{idx:03d}-{label}.png'
    subprocess.run(['grim', str(out / name)], env=env, check=True)
    frames.append((label, name))
    print('captured', name)


try:
    wait(lambda: 'Running compositor on wayland display' in logs(), 60)
    env['WAYLAND_DISPLAY'] = next(p.name for p in out.glob('wayland-*')
                                  if not p.name.endswith('.lock'))
    names = ['k230.card.one', 'k230.card.two']
    for app_id in names:
        f = (out / (app_id + '.log')).open('w')
        procs.append(subprocess.Popen([args.client, '--app-id', app_id], env=env,
                                       stdout=f, stderr=f))

    def mapped():
        dump = json.dumps(ipc('', 4))
        return all(a in dump for a in names)
    wait(mapped)

    def tree_nodes(t):
        yield t
        for c in t.get('nodes', []) + t.get('floating_nodes', []):
            yield from tree_nodes(c)
    # Diagnostic only, never gated on: docs/evidence/card-shell/
    # app-switch-swipe-frame-capture/README.md records runs where one of
    # these two "100 ppt" floating windows never reaches 568x1232 at all
    # (a resize-percentage race unrelated to card-shell's own geometry
    # code), so waiting for both to settle here would hang indefinitely.
    for n in tree_nodes(ipc('', 4)):
        if n.get('app_id') in names:
            print('mapped rect', n['app_id'], n.get('rect'))
    time.sleep(.3)
    command('test-touch init')
    ipc('[app_id="k230.card.one"] focus')

    def focused():
        def nodes(t):
            yield t
            for c in t.get('nodes', []) + t.get('floating_nodes', []):
                yield from nodes(c)
        return next((n.get('app_id') for n in nodes(ipc('', 4)) if n.get('focused')), None)
    wait(lambda: focused() == 'k230.card.one')
    time.sleep(.2)
    capture('00-baseline-one-focused')

    # Bottom-edge horizontal swipe: (420,1226) -> (120,1226), single-stepped.
    command('down 1 420 1226')
    capture('01-down')
    xs = list(range(420, 119, -20)) + [120]
    for i, x in enumerate(xs):
        command(f'motion 1 {x} 1226')
        capture(f'{i+2:02d}-motion-x{x}')
    command('up 1')
    capture('90-up')
    for i in range(6):
        time.sleep(.1)
        capture(f'9{i+1}-settle')
    print('final focus:', focused())
    print('log tail:')
    print('\n'.join(logs().splitlines()[-40:]))
finally:
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    log.close()
