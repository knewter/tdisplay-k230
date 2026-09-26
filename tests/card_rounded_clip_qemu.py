#!/usr/bin/env python3
"""Native scene/Pixman rounded-corner evidence in headless RISC-V user QEMU.

Uses real scene visibility, source mirrors and injected touch; never claims
physical panel, finger feel, or board performance. Input clients are synthetic.
"""
import argparse
import json
import hashlib
import re
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ('sway', 'client', 'swaybg', 'output'):
        ap.add_argument('--' + field, required=True)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    ap.add_argument('--cache', choices=('0', '1'), default='1')
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(mode=0o700)
    generation = out / 'theme/generations/20f2d477bb758593d831e427'
    generation.mkdir(parents=True)
    report = json.loads((ROOT / 'nix/handheld-theme-default/default-report.json').read_text())
    appearance = json.loads((ROOT / 'nix/handheld-theme-default/default-appearance.json').read_text())
    appearance['background'] = 'background'
    appearance['sections'].get('card', {}).pop('canvas', None)
    (generation / 'report.json').write_text(json.dumps(report))
    (generation / 'appearance.json').write_text(json.dumps(appearance))
    # An authored synthetic wallpaper, not a screenshot or private photo.
    wallpaper = Image.new('RGB', (568, 1232))
    wallpaper.putdata([(32 + (x * 3 + y // 13) % 170,
                        35 + (y // 4 + x // 11) % 170,
                        40 + ((x // 24 ^ y // 24) & 1) * 150)
                       for y in range(1232) for x in range(568)])
    wallpaper.save(out / 'wallpaper.png')
    config = out / 'sway.conf'
    config.write_text('output HEADLESS-1 mode 568x1232\n'
        'output HEADLESS-1 render_bit_depth 6\nseat seat0 fallback true\n'
        'focus_follows_mouse no\n'
        'for_window [app_id="^k230.card."] floating enable, border none, '
        'resize set 100 ppt 100 ppt, move position 0 0, card_shell ordinary\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS='headless',
        WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
        SWAY_K230_CARD_TOUCH_FIRST='1', SWAY_K230_CARD_TEST_INPUT='1',
        SWAY_K230_CARD_SCALED_CACHE=args.cache,
        SWAY_K230_CARD_APPEARANCE_SOCKET=str(out / 'appearance.sock'),
        SWAY_K230_CARD_THEME_DEFAULT=str(generation),
        SWAY_K230_CARD_THEME_STATE_ROOT=str(out / 'state'))
    procs, logs = [], []
    def spawn(name, cmd):
        log = (out / (name + '.log')).open('w')
        logs.append(log)
        process = subprocess.Popen(cmd, env=env, stdout=log, stderr=log)
        procs.append(process)
        return process
    def wait(predicate, seconds=30):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(.05)
        raise AssertionError('timeout: ' + (out / 'sway.log').read_text()[-2000:])
    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(10)
            sock.connect(str(next(out.glob('sway-ipc.*.sock'))))
            data = command.encode()
            sock.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)
            def read(count):
                data = b''
                while len(data) < count:
                    chunk = sock.recv(count - len(data))
                    assert chunk
                    data += chunk
                return data
            length, _ = struct.unpack('=II', read(14)[6:])
            result = json.loads(read(length))
            if kind == 0:
                assert all(r['success'] for r in result), (command, result)
            return result
    def capture(name):
        subprocess.run(['grim', str(out / (name + '.png'))], env=env, check=True)
        return Image.open(out / (name + '.png')).convert('RGB')
    def touch(*parts):
        ipc('card_shell test-touch ' + ' '.join(map(str, parts)))
    try:
        spawn('sway', [args.qemu, args.sway, '-c', str(config), '-d'])
        wait(lambda: 'Running compositor on wayland display' in (out / 'sway.log').read_text(), 60)
        env['WAYLAND_DISPLAY'] = next(p.name for p in out.glob('wayland-*') if not p.name.endswith('.lock'))
        spawn('wallpaper', [args.qemu, args.swaybg, '-i', str(out / 'wallpaper.png'), '-m', 'stretch'])
        time.sleep(1)
        baseline = capture('baseline')
        apps = ['k230.card.one', 'k230.card.two', 'k230.card.three']
        for app in apps:
            spawn(app, [args.client, '--app-id', app])
            wait(lambda: app in json.dumps(ipc('', 4)))
            time.sleep(.2)
        wait(lambda: all(app in json.dumps(ipc('', 4)) for app in apps))
        for app in apps:
            ipc('[app_id="' + app + '"] focus')
            time.sleep(.4)
        ipc('[app_id="k230.card.two"] focus')
        time.sleep(.4)
        touch('init')
        ipc('card_shell enter')
        time.sleep(1)
        overview = capture('overview')
        # Geometry comes from current 80% policy at this exact output, with
        # no reserved layer zone: selected (57,159), 454x986; neighboring
        # right edge at x=46 and left edge at x=521. Include cropped peers.
        points = [(58, 160), (509, 160), (58, 1143), (509, 1143),
                  (45, 160), (45, 1143), (522, 160), (522, 1143)]
        for point in points:
            assert overview.getpixel(point) == baseline.getpixel(point), (
                'wallpaper hidden at rounded corner', point,
                overview.getpixel(point), baseline.getpixel(point))
        for point in ((284, 500), (20, 500), (548, 500)):
            assert overview.getpixel(point) != baseline.getpixel(point), ('missing live card at', point)
        time.sleep(.3)
        live = capture('live-update')
        assert live.crop((100, 220, 480, 1000)).tobytes() != overview.crop((100, 220, 480, 1000)).tobytes()
        touch('down', 1, 380, 550, 1000)
        touch('motion', 1, 230, 550, 1120)
        time.sleep(.1)
        capture('drag-held')
        touch('up', 1, 1140)
        time.sleep(1.2)
        capture('settled')
        touch('down', 2, 284, 450, 3000)
        touch('up', 2, 3020)
        time.sleep(1)
        capture('opened')
        touch('down', 3, 284, 1218, 5000)
        touch('motion', 3, 160, 1182, 5120)
        time.sleep(.15)
        capture('direct-switch-held')
        touch('up', 3, 5150)
        time.sleep(1)
        capture('direct-switch-settled')
        touch('down', 4, 284, 1218, 7000)
        touch('motion', 4, 284, 1040, 7120)
        time.sleep(.15)
        capture('entry-held')
        touch('motion', 4, 284, 1218, 7300)
        touch('up', 4, 7310)
        time.sleep(.8)
        capture('entry-reversed')
        # Full-size source has square corners and reaches both screen edges.
        assert 'render_format: RG16' in (out / 'sway.log').read_text()
        statistics = re.findall(r'scaled-cache hits=(\d+) misses=(\d+) fallbacks=(\d+) bytes=(\d+)',
            (out / 'sway.log').read_text())
        result = {'result': 'PASS',
            'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'fixture_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'client_sha256': hashlib.sha256(Path(args.client).read_bytes()).hexdigest(),
            'render_format': 'RG16',
            'cache_samples': [dict(zip(('hits', 'misses', 'fallbacks', 'bytes'), map(int, row))) for row in statistics], 'evidence_class': 'headless-riscv64-qemu',
            'sway': args.sway, 'swaybg': args.swaybg, 'scaled_cache': args.cache,
            'wallpaper_corner_points': points, 'live_pixels_changed': True,
            'captures': ['baseline', 'overview', 'live-update', 'drag-held', 'settled', 'opened',
                         'direct-switch-held', 'direct-switch-settled', 'entry-held', 'entry-reversed'],
            'limits': 'Synthetic clients and injected touch; no physical panel or performance claim.'}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
    finally:
        for process in reversed(procs):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()

if __name__ == '__main__':
    main()
