#!/usr/bin/env python3
"""Headless QEMU regression for the ordinary-maximized resize race.

See docs/evidence/card-shell/ordinary-resize-race-fix/README.md for the root
cause: Sway's own handle_commit() (sway/desktop/xdg_shell.c) can clobber a
floating ordinary-maximized container's just-resized pending size back down
to a client's stale pre-configure geometry on the client's first mapping
commit. A card that is not the one currently shown never repaints again to
self-correct, so it stays wrongly sized forever. card_shell_commit()
(nix/card-shell/adapter.c) re-asserts the output's usable-area size after
every commit to close that race.

Two checks, both against real cross-built Sway/Wayland under
qemu-riscv64-static with injected touch -- headless-qemu-injected-input
evidence, never board/panel proof:

  * every ordinary app reaches the output's full usable size, across
    repeated launches alongside one already-shown ordinary app (the
    scenario that reproduced the bug 10/10 times pre-fix);
  * a full bottom-edge app-switch swipe between two ordinary apps never
    leaves either window's compositor-side rect short of the full usable
    area at any captured step -- "clean switch frames" checked at the
    geometry level that the earlier frame-capture evidence showed visibly
    breaking (dark bands / a residual split at settle).
"""
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from card_shell_test_support import ROOT, binaries

FULL = {'x': 0, 'y': 0, 'width': 568, 'height': 1232}
SWAY_CONF = (
    'output HEADLESS-1 mode 568x1232\n'
    'seat seat0 fallback true\n'
    'focus_follows_mouse no\n'
    'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
    'border none, resize set 100 ppt 100 ppt, move position 0 0\n'
)


class _Session:
    """Minimal headless Sway + injected-touch session, matching the
    plumbing already proven in tools/repro-app-switch-swipe.py and
    tests/test_card_shell_usable_area_runtime.py."""

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
        self.ipc('card_shell test-touch init')
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

    def start_client(self, app_id):
        stream = (self.dir / (app_id + '.log')).open('a')
        self.streams.append(stream)
        process = subprocess.Popen([self.client_bin, '--app-id', app_id], env=self.env,
                                    stdout=stream, stderr=stream)
        self.children.append(process)
        return process

    def stop_client(self, process):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        self.children.remove(process)

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

    def wait_mapped(self, app_ids):
        return self._wait(lambda: set(self.rects(app_ids)) == set(app_ids) and self.rects(app_ids) or None)

    def wait_full(self, app_ids):
        def check():
            rects = self.rects(app_ids)
            if set(rects) != set(app_ids):
                return None
            return rects if all(rect == FULL for rect in rects.values()) else None
        return self._wait(check)


class OrdinaryResizeRaceTests(unittest.TestCase):
    def test_repeated_launches_reach_full_usable_size(self):
        """The scenario that stuck 10/10 times pre-fix: two ordinary apps
        mapped back-to-back at startup, one of them never shown again. Each
        trial boots a fresh compositor, matching the tight map-to-map timing
        that made this reproduce ~100% of the time with a stale build (a
        long-lived session's second, third, ... launch has enough of a
        settle gap before it to dodge the race almost every time, which
        would make this check nearly useless)."""
        sway, client = binaries()
        names = ['k230.card.one', 'k230.card.two']
        for i in range(12):
            with tempfile.TemporaryDirectory(prefix=f'card-ordinary-race-launch-{i}-') as directory, \
                    _Session(sway, client, Path(directory) / 'session') as session:
                for app_id in names:
                    session.start_client(app_id)
                rects = session.wait_full(names)
                self.assertEqual(rects, {name: FULL for name in names}, i)

    def test_app_switch_swipe_leaves_no_stray_frame(self):
        """Bottom-edge horizontal swipe between two ordinary apps: every
        captured step keeps both windows' compositor-side rects at the
        output's full usable size -- no residual split, before, during, or
        after the switch (docs/evidence/card-shell/
        ordinary-resize-race-fix/README.md's before/after frame strips)."""
        sway, client = binaries()
        names = ['k230.card.one', 'k230.card.two']
        with tempfile.TemporaryDirectory(prefix='card-ordinary-race-swipe-') as directory, \
                _Session(sway, client, Path(directory) / 'session') as session:
            for app_id in names:
                session.start_client(app_id)
            session.wait_full(names)
            session.ipc('[app_id="k230.card.one"] focus')
            session._wait(lambda: next(
                (n.get('app_id') for n in session._nodes(session.ipc('', 4)) if n.get('focused')),
                None) == 'k230.card.one')

            checked_steps = 0

            def assert_clean(step):
                nonlocal checked_steps
                rects = session.rects(names)
                self.assertEqual(set(rects), set(names), step)
                for app_id, rect in rects.items():
                    self.assertEqual(rect, FULL, (step, app_id, rect))
                checked_steps += 1

            assert_clean('baseline')
            session.ipc('card_shell down 1 420 1226')
            assert_clean('down')
            for x in list(range(420, 119, -20)) + [120]:
                session.ipc(f'card_shell motion 1 {x} 1226')
                assert_clean(f'motion-x{x}')
            session.ipc('card_shell up 1')
            assert_clean('up')
            for _ in range(6):
                time.sleep(.1)
                assert_clean('settle')
            self.assertGreaterEqual(checked_steps, 20)


if __name__ == '__main__':
    unittest.main()
