#!/usr/bin/env python3
"""Headless QEMU regression for the cropped-neighbour / held-frame flicker
report: swiping between two ordinary maximized apps drew the incoming
neighbour only in a shrunken middle band, with wallpaper visible above and
below it (docs/evidence/card-shell/app-switch-neighbour-render/README.md).

Root cause: `card_clip_box()` (nix/card-shell/adapter.c) special-cased only
the outgoing `entry_id` card for the full-output clip box during CS_ENTERING;
every other card -- including the incoming neighbour that `sync_card`
deliberately renders at the same shared full-panel frame as the outgoing app
whenever both are `card_shell_ordinary_maximized` (`common_full_frame`) --
still got the small deck-viewport clip (`clip_box()`), so the neighbour's
live mirror was cropped to that shorter rect even though it was being drawn
full height. The fix adds a `struct card.full_clip` flag, set from the same
`common_full_frame` condition `sync_card` already computes, and
`card_clip_box()` now grants the full-output clip to any card carrying it,
not only the entry card.

This test replays the exact reported gesture -- a bottom-edge horizontal drag
held at constant y, matching the coordinator's board reproduction at
(420,1226) -> (280,1226) -- against two synthetic ordinary-maximized clients,
and checks, at native QEMU pixels:

  * the incoming neighbour's rect is entirely content, top to bottom: no
    backdrop-coloured (wallpaper) rows inside it;
  * two captures taken ~1.6s apart while genuinely held (no further input)
    classify every pixel identically content-vs-backdrop -- the animated
    client content is free to keep moving (that is real app liveness, not a
    shell bug), but the content/wallpaper boundary itself must not move.

Headless-QEMU-injected-input evidence only; no physical touch or panel proof.
"""
import itertools
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from card_shell_test_support import ROOT, binaries

FULL = {'x': 0, 'y': 0, 'width': 568, 'height': 1232}
PANEL_WIDTH, PANEL_HEIGHT = 568, 1232
# nix/card-shell/adapter.c: static const float backdrop[4] = {.067,.094,.153,1};
BACKDROP = (17, 24, 39)
SWAY_CONF = (
    'output HEADLESS-1 mode 568x1232\n'
    'seat seat0 fallback true\n'
    'focus_follows_mouse no\n'
    'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
    'border none, resize set 100 ppt 100 ppt, move position 0 0\n'
)


def is_backdrop(pixel, tolerance=12):
    return all(abs(c - b) <= tolerance for c, b in zip(pixel, BACKDROP))


class _Session:
    """Minimal headless Sway + injected-touch session, matching the plumbing
    proven in tools/repro-app-switch-swipe.py and
    tests/test_card_shell_ordinary_resize_race.py."""

    def __init__(self, sway, client, directory, qemu='/usr/bin/qemu-riscv64-static'):
        self.sway_bin = sway
        self.client_bin = client
        self.qemu = qemu
        self.dir = Path(directory)
        self.children = []
        self.streams = []
        self.log = None

    def __enter__(self):
        self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        config = self.dir / 'sway.conf'
        config.write_text(SWAY_CONF)
        self.env = dict(os.environ, XDG_RUNTIME_DIR=str(self.dir), WLR_BACKENDS='headless',
                         WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
                         SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TOUCH_FIRST='1',
                         SWAY_K230_CARD_TEST_INPUT='1')
        self.log = (self.dir / 'sway.log').open('w')
        self.sway = subprocess.Popen([self.qemu, self.sway_bin, '-c', str(config), '-d'],
                                      env=self.env, stdout=self.log, stderr=self.log)
        self.children.append(self.sway)
        self._wait(lambda: 'Running compositor on wayland display' in self._logs(), 60)
        self.env['WAYLAND_DISPLAY'] = next(
            p.name for p in self.dir.glob('wayland-*') if not p.name.endswith('.lock'))
        return self

    def __exit__(self, *exc):
        for process in reversed(self.children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if self.log:
            self.log.close()
        for stream in self.streams:
            stream.close()

    def _logs(self):
        return (self.dir / 'sway.log').read_text()

    def _wait(self, predicate, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(.03)
        raise AssertionError('timed out waiting for compositor state: ' + self._logs()[-4000:])

    def ipc(self, command, kind=0):
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(8)
            sock.connect(str(next(self.dir.glob('sway-ipc.*.sock'))))
            payload = command.encode()
            sock.sendall(b'i3-ipc' + struct.pack('=II', len(payload), kind) + payload)

            def read(n):
                data = b''
                while len(data) < n:
                    chunk = sock.recv(n - len(data))
                    assert chunk, 'IPC closed'
                    data += chunk
                return data
            header = read(14)
            length, _ = struct.unpack('=II', header[6:])
            result = json.loads(read(length))
            if kind == 0:
                assert all(row['success'] for row in result), (command, result)
            return result

    def command(self, s):
        return self.ipc('card_shell ' + s)

    def start_client(self, app_id):
        stream = (self.dir / (app_id + '.log')).open('a')
        self.streams.append(stream)
        process = subprocess.Popen([self.client_bin, '--app-id', app_id], env=self.env,
                                    stdout=stream, stderr=stream)
        self.children.append(process)
        return process

    def _nodes(self, tree):
        yield tree
        for node in tree.get('nodes', []) + tree.get('floating_nodes', []):
            yield from self._nodes(node)

    def rects(self, app_ids):
        tree = self.ipc('', 4)
        found = {}
        for node in self._nodes(tree):
            app_id = node.get('app_id')
            if app_id in app_ids:
                found[app_id] = node.get('rect')
        return found

    def focused_app_id(self):
        return next((n.get('app_id') for n in self._nodes(self.ipc('', 4)) if n.get('focused')),
                    None)

    def wait_full(self, app_ids):
        def check():
            rects = self.rects(app_ids)
            if set(rects) != set(app_ids):
                return None
            return rects if all(rect == FULL for rect in rects.values()) else None
        return self._wait(check)

    def capture(self, name):
        path = self.dir / name
        subprocess.run(['grim', str(path)], env=self.env, check=True)
        return Image.open(path).convert('RGB')


def neighbour_column(image, row=700):
    """The x-range at `row` -- a row well inside the always-visible middle
    band even with the pre-fix crop -- that is not backdrop and not the
    outgoing (left) card's own colour band. Returns (x0, x1) inclusive, or
    None if no such run is found."""
    ONE = {(32, 112, 176), (16, 56, 88)}

    def is_one(p):
        return min(sum(abs(a - b) for a, b in zip(p, c)) for c in ONE) < 20
    run = []
    for x in range(PANEL_WIDTH):
        p = image.getpixel((x, row))
        if not is_backdrop(p) and not is_one(p):
            run.append(x)
    if not run:
        return None
    return min(run), max(run)


def column_profile(image, x):
    """content/backdrop classification down the full column at x."""
    return [not is_backdrop(image.getpixel((x, y))) for y in range(PANEL_HEIGHT)]


def runs(profile):
    """Contiguous (value, start, end) runs, for readable assertion failures."""
    out = []
    y = 0
    for value, group in itertools.groupby(profile):
        n = len(list(group))
        out.append((value, y, y + n - 1))
        y += n
    return out


class SwitchNeighbourRenderTests(unittest.TestCase):
    def test_held_partial_drag_neighbour_full_height_and_stable(self):
        sway, client = binaries()
        names = ['k230.card.one', 'k230.card.two']
        with tempfile.TemporaryDirectory(prefix='card-switch-neighbour-') as directory, \
                _Session(sway, client, Path(directory) / 'session') as session:
            for app_id in names:
                session.start_client(app_id)
            session.wait_full(names)
            session.command('test-touch init')
            session.ipc('[app_id="k230.card.one"] focus')
            session._wait(lambda: session.focused_app_id() == 'k230.card.one')
            time.sleep(.2)

            # The coordinator's exact board reproduction: down at (420,1226),
            # stepped to (280,1226) at constant y, then held.
            session.command('down 1 420 1226')
            session.command('motion 1 420 1226')
            for x in range(400, 279, -20):
                session.command(f'motion 1 {x} 1226')

            time.sleep(.05)
            held_1 = session.capture('held-1.png')
            time.sleep(1.6)
            held_2 = session.capture('held-2.png')
            session.command('up 1')

            for label, frame in (('held-1', held_1), ('held-2', held_2)):
                column = neighbour_column(frame)
                self.assertIsNotNone(column, (label, 'no neighbour content found'))
                x0, x1 = column
                # A real sliver, not a stray anti-aliased pixel or two.
                self.assertGreaterEqual(x1 - x0, 20, (label, column))
                mid = (x0 + x1) // 2
                profile = column_profile(frame, mid)
                content_runs = runs(profile)
                self.assertEqual(content_runs, [(True, 0, PANEL_HEIGHT - 1)],
                                  (label, 'neighbour column has backdrop rows', content_runs))

            # Genuinely held: no further input between the two captures.
            # The animating synthetic client is free to keep repainting (that
            # is real liveness, not a bug), but the content/backdrop
            # boundary the crop bug exposed must be bit-for-bit stable.
            mid_1 = sum(neighbour_column(held_1)) // 2
            mid_2 = sum(neighbour_column(held_2)) // 2
            self.assertEqual(column_profile(held_1, mid_1), column_profile(held_2, mid_2),
                              'neighbour content/backdrop boundary moved while held')


if __name__ == '__main__':
    unittest.main()
