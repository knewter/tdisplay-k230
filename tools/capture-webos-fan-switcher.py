#!/usr/bin/env python3
"""Capture the webOS-fan card overview under dark and light themes, exercising
scroll, close and open through the real touch pipeline.

Evidence for the user's chosen direction over
`the-shell-behaves-as-one-coherent-system` slice A ("widen peek"): a
horizontal row with 2-3 small cards visible at once, each with a resolved
.desktop icon and Name= above it, scrolled/closed/opened by touch.

Reuses the same headless-QEMU Sway + card-appearance-socket path as
tools/capture-bare-app-cards.py and tests/test_card_shell_appearance_runtime.py:
real cross-built riscv64 Sway under qemu-riscv64-static user-mode emulation,
the real card_shell IPC command, the real card_shell test-touch injection
path (SWAY_K230_CARD_TEST_INPUT), and the real appearance protocol. This is
headless-QEMU proof, not board/panel/touch proof.

Usage:
  python3 tools/capture-webos-fan-switcher.py --sway <unwrapped riscv64 sway>
      --client <card-composition-probe-client> --icon-roots <dir with
      share/{applications,icons}> --output /tmp/k230-fs-N

--sway: nix-store -qR the .#card-shell closure for a
  */sway-unwrapped-riscv64.../bin/sway path.
--client: a HOST-architecture build of
  nix/card-composition-probe-client (Wayland is a local socket; the client
  need not be cross-built).
--icon-roots: a directory whose share/{applications,icons} trees make the
  real k230-terminal/k230-monitor/nnn-equivalent .desktop identities and
  their real (foot/htop/Yaru folder) icons resolvable -- see this repo's
  nix/handheld-desktop-entries.nix and nix/handheld-theme-icons for the
  real shell's own equivalent.
"""
import argparse
import json
import os
import pathlib
import socket
import struct
import subprocess
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ID = '20f2d477bb758593d831e427'
LIGHT_ID = '111111111111111111111111'

# Fixed by card-composition-probe-client's own --app-id enum; matched here to
# real .desktop identities (Name=/Icon=) via StartupWMClass, mirroring
# nix/handheld-desktop-entries.nix's real k230-terminal/k230-monitor/nnn
# entries and their real (foot/htop/folder) icons.
APPS = [
    ('k230.card.one', 'Terminal', 'foot'),
    ('k230.card.two', 'Monitor', 'htop'),
    ('k230.card.three', 'Files', 'folder'),
]


def write_desktop_fixtures(directory):
    apps_dir = directory / 'share/applications'
    apps_dir.mkdir(parents=True)
    for app_id, name, icon in APPS:
        (apps_dir / f'{app_id}.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=%s\nExec=/bin/true\n'
            'Icon=%s\nTerminal=false\nStartupWMClass=%s\n' % (name, icon, app_id))


def light_theme_payloads():
    report = json.loads((REPO / 'nix/handheld-theme-default/default-report.json').read_text())
    report['generation'] = LIGHT_ID
    report['palette'] = dict(report['palette'])
    report['palette'].update({
        'mode': 'light', 'background': '#eff1f5', 'dark_background': '#e6e9ef',
        'lighter_background': '#dce0e8', 'darker_background': '#dce0e8',
        'foreground': '#4c4f69', 'bright_foreground': '#4c4f69',
        'dark_foreground': '#6c6f85', 'light_foreground': '#4c4f69',
        'accent': '#1e66f5', 'selection': '#ccd0da',
    })
    appearance = json.loads((REPO / 'nix/handheld-theme-default/default-appearance.json').read_text())
    appearance['generation'] = LIGHT_ID
    return report, appearance


def run_theme(args, name, theme):
    scenario_dir = args.output / name
    scenario_dir.mkdir(mode=0o700)
    default_gen = scenario_dir / 'default/generations' / DEFAULT_ID
    default_gen.mkdir(parents=True)
    import shutil
    shutil.copy(REPO / 'nix/handheld-theme-default/default-report.json', default_gen / 'report.json')
    shutil.copy(REPO / 'nix/handheld-theme-default/default-appearance.json', default_gen / 'appearance.json')
    state = scenario_dir / 'state'
    (state / 'generations').mkdir(parents=True)
    fixtures = scenario_dir / 'fixtures'
    write_desktop_fixtures(fixtures)
    config = scenario_dir / 'sway.conf'
    config.write_text(
        'output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n'
        'focus_follows_mouse no\n'
        'for_window [app_id="^k230.card."] floating enable, border none, '
        'resize set 520 1040, move position 24 48\n')
    xdg_data_dirs = ':'.join(str(p) for p in (fixtures / 'share', args.icon_roots / 'share'))
    env = dict(os.environ, XDG_RUNTIME_DIR=str(scenario_dir), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
               SWAY_K230_CARD_TOUCH_FIRST='1', SWAY_K230_CARD_TEST_INPUT='1',
               SWAY_K230_CARD_APPEARANCE_SOCKET=str(scenario_dir / 'card-appearance.sock'),
               SWAY_K230_CARD_THEME_STATE_ROOT=str(state),
               SWAY_K230_CARD_THEME_DEFAULT=str(default_gen),
               XDG_DATA_DIRS=xdg_data_dirs, K230_ICON_THEME='Yaru')
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

    def shot(label):
        png = scenario_dir / f'{label}.png'
        subprocess.run(['grim', str(png)], env=env, check=True)
        print('captured', png, flush=True)
        return png

    def touch(*args_):
        ipc('card_shell test-touch ' + ' '.join(str(a) for a in args_))

    try:
        wait(lambda: 'Running compositor on wayland display' in logs(), 60)
        env['WAYLAND_DISPLAY'] = next(p.name for p in scenario_dir.glob('wayland-*')
                                      if not p.name.endswith('.lock'))
        wait(lambda: (scenario_dir / 'card-appearance.sock').exists())
        for app_id, _, _ in APPS:
            f = (scenario_dir / (app_id + '.log')).open('w')
            procs.append(subprocess.Popen([args.client, '--app-id', app_id], env=env,
                                           stdout=f, stderr=f))

        def mapped():
            dump = json.dumps(ipc('', 4))
            return all(a in dump for a, _, _ in APPS)
        wait(mapped)
        # Focus the middle app before entering the overview so the captured
        # deck shows a peek on both sides (the representative "fan" case),
        # not the last-card edge case with only a left neighbour.
        ipc('[app_id="k230.card.two"] focus')
        if theme == 'light':
            report, appearance = light_theme_payloads()
            candidate = state / 'generations' / LIGHT_ID
            candidate.mkdir(parents=True)
            (candidate / 'report.json').write_text(json.dumps(report))
            (candidate / 'appearance.json').write_text(json.dumps(appearance))
            exchange('prepare', LIGHT_ID, candidate, previous_generation=None, previous_path=None)
            (state / 'active').symlink_to(candidate)
            exchange('commit', LIGHT_ID, candidate)
            time.sleep(.3)

        touch('init')
        ipc('card_shell enter')
        time.sleep(.5)
        shot('01-overview')

        # Scroll: a fast, real ~8ms-cadence horizontal drag on the card row,
        # well inside the momentum-page threshold, then let the release
        # coast settle (cs_tick-driven, not an instant snap).
        row_y = 550
        t0 = 1000
        touch('down', 1, 460, row_y, t0)
        for i in range(1, 9):
            touch('motion', 1, 460 - i * 22, row_y, t0 + i * 8)
        touch('up', 1, t0 + 9 * 8)
        time.sleep(.05)
        shot('02-scrolling')
        time.sleep(.4)  # let the momentum coast (<=240ms) settle
        shot('03-scrolled-settled')

        # Close: a flick-up throw on the now-selected card. Y coordinates
        # stay well inside the card's own vertical span (roughly 210-600 at
        # the real 568x1232 panel with this policy's current geometry) --
        # not the much taller pre-fan card the touch points originally
        # assumed.
        t1 = t0 + 2000
        touch('down', 2, 284, 450, t1)
        for i in range(1, 6):
            touch('motion', 2, 284, 450 - i * 40, t1 + i * 15)
        touch('up', 2, t1 + 6 * 15)
        time.sleep(1.8)  # close request -> client accepts -> card_shell reconciles
        shot('04-after-close')

        # Open: a plain tap on the remaining selected card.
        t2 = t1 + 3000
        touch('down', 3, 284, 450, t2)
        touch('up', 3, t2 + 20)
        time.sleep(2.5)  # tap-to-expand animation (160ms) + a generous settle margin
        shot('05-opened')
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
        log.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sway', required=True)
    ap.add_argument('--client', required=True)
    ap.add_argument('--icon-roots', required=True, type=pathlib.Path)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    ap.add_argument('--output', required=True, type=pathlib.Path)
    args = ap.parse_args()
    assert (REPO / 'nix/handheld-theme-default/default-report.json').exists()
    args.output.mkdir(parents=True, exist_ok=True)
    for theme in ('dark', 'light'):
        run_theme(args, theme, theme)
    print('done')


if __name__ == '__main__':
    main()
