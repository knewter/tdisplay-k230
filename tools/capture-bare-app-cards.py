#!/usr/bin/env python3
"""Capture the card overview with 1/2/3 apps under dark and light themes.

Evidence for the-shell-manages-apps-as-cards card-plate/letterbox fix: the
card must be the app's own live snapshot with a small rounded/bordered plate,
never a full-slot coloured plate behind a letterboxed snapshot.

Reuses the same headless-QEMU Sway + card-appearance-socket path as
tests/test_card_shell_appearance_runtime.py: real cross-built riscv64 Sway
under qemu-riscv64-static user-mode emulation, the real card_shell IPC
command, and the real appearance protocol (report.json/appearance.json,
'prepare'/'commit' exchange) -- never a string/pixel substitute. This is
headless-QEMU proof, not board/panel/touch proof.

Usage:
  python3 tools/capture-bare-app-cards.py --sway <unwrapped riscv64 sway>
      --client <card-composition-probe-client> --output /tmp/k230-bc-N

Find --sway from `nix build .#card-shell` (its .sway-wrapped names the exec
path) and --client from the native (host-arch) nix/card-composition-probe-client
derivation (`nix build --impure --expr '...callPackage .../nix/card-composition-probe-client {}'`).
"""
import argparse
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import time

ap = argparse.ArgumentParser(description=__doc__,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--sway', required=True)
ap.add_argument('--client', required=True)
ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
ap.add_argument('--output', required=True, type=pathlib.Path)
args = ap.parse_args()
REPO = pathlib.Path(__file__).resolve().parents[1]
assert (REPO / 'nix/handheld-theme-default/default-report.json').exists()

out = args.output
out.mkdir(parents=True, exist_ok=True)

DEFAULT_ID = '20f2d477bb758593d831e427'
LIGHT_ID = '111111111111111111111111'

# The bundled default generation (nix/handheld-theme-default) is Catppuccin
# Mocha (dark). There is no bundled light theme in-tree, so the light run
# authors a Catppuccin-Latte-like palette through the same real report.json
# palette-synthesis path (card-shell/appearance.c's load()/solid()) rather
# than faking pixels: only the palette hex values differ from a real theme.
_light_report = json.loads((REPO / 'nix/handheld-theme-default/default-report.json').read_text())
_light_report['generation'] = LIGHT_ID
_light_report['palette'] = dict(_light_report['palette'])
_light_report['palette'].update({
    'mode': 'light',
    'background': '#eff1f5',
    'dark_background': '#e6e9ef',
    'lighter_background': '#dce0e8',
    'darker_background': '#dce0e8',
    'foreground': '#4c4f69',
    'bright_foreground': '#4c4f69',
    'dark_foreground': '#6c6f85',
    'light_foreground': '#4c4f69',
    'accent': '#1e66f5',
    'selection': '#ccd0da',
})
_light_appearance = json.loads((REPO / 'nix/handheld-theme-default/default-appearance.json').read_text())
_light_appearance['generation'] = LIGHT_ID


def run_scenario(name, n_apps, theme):
    scenario_dir = out / name
    scenario_dir.mkdir(mode=0o700)
    default_gen = scenario_dir / 'default/generations' / DEFAULT_ID
    default_gen.mkdir(parents=True)
    shutil.copy(REPO / 'nix/handheld-theme-default/default-report.json', default_gen / 'report.json')
    shutil.copy(REPO / 'nix/handheld-theme-default/default-appearance.json', default_gen / 'appearance.json')
    state = scenario_dir / 'state'
    (state / 'generations').mkdir(parents=True)
    config = scenario_dir / 'sway.conf'
    config.write_text(
        'output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n'
        'focus_follows_mouse no\n'
        'for_window [app_id="^k230.card."] floating enable, border none, '
        'resize set 520 1040, move position 24 48\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(scenario_dir), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
               SWAY_K230_CARD_TOUCH_FIRST='1',
               SWAY_K230_CARD_APPEARANCE_SOCKET=str(scenario_dir / 'card-appearance.sock'),
               SWAY_K230_CARD_THEME_STATE_ROOT=str(state),
               SWAY_K230_CARD_THEME_DEFAULT=str(default_gen))
    procs = []
    log = (scenario_dir / 'sway.log').open('w')
    procs.append(subprocess.Popen([args.qemu, args.sway, '-c', str(config), '-d'], env=env,
                                   stdout=log, stderr=log))

    def logs():
        return (scenario_dir / 'sway.log').read_text()

    def wait(pred, seconds=30):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            v = pred()
            if v:
                return v
            time.sleep(.05)
        raise AssertionError('timeout: ' + logs()[-4000:])

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(8)
            s.connect(str(next(scenario_dir.glob('sway-ipc.*.sock'))))
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

    def exchange(phase, gen_id, path, **extra):
        request = {'protocol': 1, 'phase': phase, 'generation': gen_id,
                   'path': str(path) if path else None, **extra}
        with socket.socket(socket.AF_UNIX) as s:
            s.settimeout(6)
            s.connect(str(scenario_dir / 'card-appearance.sock'))
            s.sendall(json.dumps(request).encode() + b'\n')
            reply = b''
            while not reply.endswith(b'\n'):
                chunk = s.recv(256)
                assert chunk
                reply += chunk
            result = json.loads(reply)
            assert result['status'] == 'ok', (request, result)
            return result

    try:
        wait(lambda: 'Running compositor on wayland display' in logs(), 60)
        env['WAYLAND_DISPLAY'] = next(p.name for p in scenario_dir.glob('wayland-*')
                                      if not p.name.endswith('.lock'))
        wait(lambda: (scenario_dir / 'card-appearance.sock').exists())
        names = ['k230.card.one', 'k230.card.two', 'k230.card.three'][:n_apps]
        for app_id in names:
            f = (scenario_dir / (app_id + '.log')).open('w')
            procs.append(subprocess.Popen([args.client, '--app-id', app_id], env=env,
                                           stdout=f, stderr=f))

        def mapped():
            dump = json.dumps(ipc('', 4))
            return all(a in dump for a in names)
        wait(mapped)
        if theme == 'light':
            candidate = state / 'generations' / LIGHT_ID
            candidate.mkdir(parents=True)
            (candidate / 'report.json').write_text(json.dumps(_light_report))
            (candidate / 'appearance.json').write_text(json.dumps(_light_appearance))
            exchange('prepare', LIGHT_ID, candidate, previous_generation=None, previous_path=None)
            (state / 'active').symlink_to(candidate)
            exchange('commit', LIGHT_ID, candidate)
            time.sleep(.3)
        ipc('card_shell enter')
        time.sleep(.5)
        png = out / f'{name}.png'
        subprocess.run(['grim', str(png)], env=env, check=True)
        print('captured', png)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        log.close()


if __name__ == '__main__':
    for n in (1, 2, 3):
        for theme in ('dark', 'light'):
            run_scenario(f'{n}-apps-{theme}', n, theme)
    print('done')
