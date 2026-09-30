#!/usr/bin/env python3
"""Audit the installed shell through standard Sway pointer dispatch.

Reserve the board externally before using --serial. Raw console data and
captures stay in a mode-0700 output directory: Home/Wi-Fi frames can contain
private information. Only result.json is eligible for public evidence after
review. Synthetic pointer input is never labeled physical finger acceptance.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial', default='/dev/ttyACM0')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--width', type=int, default=1080)
    ap.add_argument('--height', type=int, default=1920)
    ap.add_argument('--calculator-x', type=int, default=870,
                    help='Calculator icon in the actual installed desktop-entry grid; verify before running')
    ap.add_argument('--calculator-y', type=int, default=160)
    ap.add_argument('--capture', action='store_true', help='collect private native captures for manual review')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(args.output, 0o700)
    rows, counter = [], 0
    env = 'export XDG_RUNTIME_DIR=/run/shell SWAYSOCK=/run/shell/sway-ipc.sock; '

    def execute(command):
        nonlocal counter
        counter += 1
        # Markers must be whole lines; echoed command strings are not replies.
        wrapped = env + 'echo K230_AUDIT_BEGIN; ' + command + '; echo K230_AUDIT_END'
        run = subprocess.run([sys.executable, str(ROOT / 'tools/console.py'), args.serial,
                              '--wait=4', wrapped], capture_output=True, check=True, text=True)
        path = args.output / f'{counter:02d}.private.log'
        path.write_text(run.stdout + run.stderr)
        path.chmod(0o600)
        match = re.search(r'^K230_AUDIT_BEGIN\s*\n(.*?)\nK230_AUDIT_END\s*$',
                          run.stdout, re.M | re.S)
        if not match: raise AssertionError('serial command did not complete; inspect private log')
        return match.group(1).strip()

    def ipc(command):
        # Shell quote independent of JSON escaping.
        quoted = "'" + command.replace("'", "'\\''") + "'"
        return 'swaymsg -r ' + quoted

    def scene():
        response = json.loads(execute(ipc('card_shell debug-scene')))
        if not response[0]['success']: raise AssertionError('debug-scene failed')
        text = response[0]['error']
        return {k: int(v) for k, v in re.findall(
            r'\b(home_selected|home_enabled|mode|drawer_mapped)=([0-9]+)', text)}

    def tree():
        value = json.loads(execute('swaymsg -r -t get_tree'))
        def walk(node):
            yield node
            for child in node.get('nodes', []) + node.get('floating_nodes', []): yield from walk(child)
        return list(walk(value))

    def app_ids(): return {n['id'] for n in tree() if n.get('app_id')}
    def focus_is(name): return any(n.get('app_id') == name and n.get('focused') for n in tree())
    def pointer_state():
        text = execute("journalctl -u shell-ui -n 80 --no-pager -o cat | sed -n '/pointer-state /p' | tail -n 1")
        return dict(re.findall(r'\b(route|wifi|themes|drawer_scroll|notification_scroll|wifi_scroll|theme_position|background_position)=([A-Za-z0-9.-]+)', text))

    def click(x, y):
        execute(ipc(f'seat seat0 cursor set {x} {y}; seat seat0 cursor press button1; '
                    'seat seat0 cursor release button1') + '; sleep 0.6')

    def drag(x, y, end_x, end_y):
        # Different event-loop turns guarantee the press owns the full stream.
        execute(ipc(f'seat seat0 cursor set {x} {y}; seat seat0 cursor press button1') + '; sleep 0.08; '
                + ipc(f'seat seat0 cursor set {end_x} {end_y}; seat seat0 cursor release button1') + '; sleep 0.8')

    def capture(label):
        if not args.capture: return None
        body = execute('for socket in /run/shell/wayland-*; do if test -S "$socket"; then '
                       'export WAYLAND_DISPLAY="${socket##*/}"; break; fi; done; '
                       'grim -t jpeg -q 60 /root/tmp/k230-deployment/navigation-audit.jpg >/dev/null 2>&1 && '
                       'base64 /root/tmp/k230-deployment/navigation-audit.jpg')
        data = base64.b64decode(body, validate=False)
        if not data.startswith(b'\xff\xd8'): raise AssertionError('capture was not a complete JPEG')
        path = args.output / f'{label}.private.jpg'
        path.write_bytes(data); path.chmod(0o600)
        return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'public': False}

    def record(label, condition, **details):
        if not condition: raise AssertionError(f'{label} failed; inspect private output')
        row = {'check': label, 'passed': True, **details}
        rows.append(row)
        print('PASS ' + label, flush=True)

    w, h = args.width, args.height
    baseline = app_ids()
    execute('/run/current-system/sw/bin/k230-shell-rust --surface hide; ' + ipc('card_shell home') + '; sleep 0.8')
    record('home setup', scene().get('home_selected') == 1)
    drag(w // 2, h - 2, w // 2, h - 420)
    record('Home bottom edge opens drawer', scene().get('drawer_mapped') == 1, capture=capture('drawer'))
    click(args.calculator_x, args.calculator_y)
    launch_scene = scene()
    record('drawer icon opens visible Calculator', focus_is('galculator') and
           launch_scene.get('home_selected') == 0 and launch_scene.get('drawer_mapped') == 0)
    windows = app_ids()
    record('existing apps retained by launch', baseline <= windows)
    drag(w // 2, h - 2, w // 2, h - 420)
    record('app bottom mouse drag opens overview', scene().get('mode') == 1, capture=capture('overview'))
    click(w // 2, h - 30)
    record('overview footer click reaches Home without closing apps',
           scene().get('home_selected') == 1 and app_ids() == windows, capture=capture('home'))
    execute(ipc('card_shell enter') + '; sleep 0.5')
    centered = execute(ipc('card_shell debug-scene'))
    selected = re.search(r'selected_app_id=([^ \"\n]+)', centered).group(1)
    execute(ipc('card_shell activate') + '; sleep 0.8')
    record('spread command expands centered live window', focus_is(selected) and scene().get('mode') == 0)
    # Recheck Home's own drawer dismiss handle.
    execute(ipc('card_shell home') + '; sleep 0.5')
    drag(w // 2, h - 2, w // 2, h - 420)
    execute(ipc(f'seat seat0 cursor set {w//2} 500; seat seat0 cursor press button5') + '; sleep 0.4')
    click(w // 2, 42)
    record('drawer handle click dismisses', scene().get('drawer_mapped') == 0)
    drag(w // 2, 2, w // 2, 450)
    record('top edge mouse drag opens shade', scene().get('drawer_mapped') == 1, capture=capture('shade'))
    click(w - 100, 75)
    state = pointer_state()
    record('shade Settings click opens Settings', state.get('route') == 'Settings', capture=capture('settings'))
    # Settings rows use a centered, density-scaled design column.
    scale = max(1.0, min(2.0, w / 568.0, h / 1232.0))
    click(w // 2, round(240 * scale))
    state = pointer_state()
    record('Settings Wi-Fi row opens list', state.get('wifi') == 'List', capture=capture('wifi'))
    execute(ipc(f'seat seat0 cursor set {w//2} 500; seat seat0 cursor press button5') + '; sleep 0.4')
    click(80, 70)
    state = pointer_state()
    record('Wi-Fi Back returns to Settings', state.get('wifi') == 'Closed')
    click(w - 100, 132)
    state = pointer_state()
    record('Settings Themes click opens chooser', state.get('themes') == 'List', capture=capture('themes'))
    before_position = float(state.get('theme_position', '-1'))
    wheel = 'button4' if before_position > 0.5 else 'button5'
    execute(ipc(f'seat seat0 cursor set {w//2} 350; seat seat0 cursor press {wheel}') + '; sleep 0.8')
    state = pointer_state()
    after_position = float(state.get('theme_position', '-1'))
    record('theme wheel browses candidates', after_position >= 0 and abs(after_position - before_position) > 0.1,
           before_position=before_position, after_position=after_position)
    click(80, 70)
    state = pointer_state()
    record('theme Back returns to Settings', state.get('themes') == 'Controls')
    click(w - 80, 70)
    record('Settings Done dismisses', scene().get('drawer_mapped') == 0)
    execute(ipc('card_shell enter') + '; sleep 0.5')
    click(w // 2, round(h * .5))
    record('overview card click opens centered app', scene().get('mode') == 0)
    record('navigation audit keeps app windows open', app_ids() == windows)
    system = execute('readlink -f /run/current-system')
    result = {'schema': 1, 'evidence_class': 'physical-board-injected-standard-pointer',
              'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'installed_system': system, 'dimensions': [w, h], 'checks': rows,
              'limits': ['Physical finger recognition and perceived motion are not proven.',
                         'No credentials, SSIDs or private addresses are retained in this public result.',
                         'Wheel events over short lists establish bounded navigation, not overflowing-list movement.',
                         'Wi-Fi connect, theme apply, audio/power actions and destructive controls are not exercised.']}
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(rows)} navigation checks passed; physical finger acceptance remains open.')


if __name__ == '__main__': main()
