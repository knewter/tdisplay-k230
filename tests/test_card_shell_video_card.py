#!/usr/bin/env python3
"""Headless QEMU regression for video windows becoming ordinary, closable
cards (docs/evidence/card-shell/video-card/).

Root cause of "big buck bunny played and I can't close it": k230-video-
software/k230-video-mvx (mpv, launched by nix/video-session.py) were
excluded from `card_shell ordinary` alongside real transient/popup views
(nix/card-shell/adapter.c's now-removed "video and transient views stay
unmarked" check), so a playing video stayed a small floating window: no
card, not in the overview, not reachable by the bottom-edge switch gesture,
and with no other close control in this touch-only shell.

This test uses the synthetic k230-video-software app_id as an ordinary card
fixture (a real mpv/video decode is out of scope for a headless-QEMU check;
see runtime/video's own board evidence for that) and proves, against real
cross-built Sway under qemu-riscv64-static with injected touch:

  * a video app_id reaches full ordinary-maximized card geometry (the same
    568x1232 resize every other coherent-shell app gets), not a small
    floating window;
  * a real touch-first vertical entry swipe starting from a focused video
    card is accepted into the overview like any other source, and once
    there the video card is a genuine, switchable deck member reachable by
    `previous`/`next` (the same persistent-button route the bottom-edge
    gesture's own lateral release resolves to -- see
    docs/evidence/card-shell/video-card/README.md for why this test proves
    switchability that way rather than guessing a drag direction);
  * requesting its close (the same `card_shell close` route every card
    uses, close-timeout coverage in tests/card_shell_runtime.py's own suite
    already exercises this exact IPC path) both sends the ordinary
    xdg_toplevel close and invokes the video-stop helper
    (`SWAY_K230_CARD_VIDEO_STOP ... stop`) exactly once -- the fix for the
    session controller otherwise being unable to tell "the user closed it"
    from "the decoder died" and relaunching a fallback player right after
    close;
  * the other ordinary card is unaffected and the deck remains usable with
    one fewer card.

Headless-QEMU-injected-input evidence only; no physical touch, panel, or
mpv/decode proof -- see runtime/video's own board evidence for that.
"""
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from card_shell_test_support import binaries

FULL = {'x': 0, 'y': 0, 'width': 568, 'height': 1232}
SWAY_CONF = (
    'output HEADLESS-1 mode 568x1232\n'
    'seat seat0 fallback true\n'
    'focus_follows_mouse no\n'
    'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
    'border none, resize set 100 ppt 100 ppt, move position 0 0\n'
    'for_window [app_id="^k230-video-(software|mvx)$"] card_shell ordinary, '
    'floating enable, border none, resize set 100 ppt 100 ppt, move position 0 0\n'
)


class _Session:
    def __init__(self, sway, client, directory, video_stop_helper,
                 qemu='/usr/bin/qemu-riscv64-static'):
        self.sway_bin = sway
        self.client_bin = client
        self.qemu = qemu
        self.dir = Path(directory)
        self.children = []
        self.streams = []
        self.log = None
        self.video_stop_helper = video_stop_helper

    def __enter__(self):
        self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        config = self.dir / 'sway.conf'
        config.write_text(SWAY_CONF)
        self.env = dict(os.environ, XDG_RUNTIME_DIR=str(self.dir), WLR_BACKENDS='headless',
                         WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
                         SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TOUCH_FIRST='1',
                         SWAY_K230_CARD_TEST_INPUT='1',
                         SWAY_K230_CARD_VIDEO_STOP=str(self.video_stop_helper))
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

    def _wait(self, predicate, seconds=30):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(.03)
        raise AssertionError('timed out waiting for compositor state: ' + self._logs()[-4000:])

    def ipc(self, command, kind=0, check=True):
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
            if kind == 0 and check:
                assert all(row['success'] for row in result), (command, result)
            return result

    def command(self, s, check=True):
        return self.ipc('card_shell ' + s, check=check)

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

    def rect(self, app_id):
        tree = self.ipc('', 4)
        for node in self._nodes(tree):
            if node.get('app_id') == app_id:
                return node.get('rect')
        return None

    def wait_full(self, app_ids):
        def check():
            tree = self.ipc('', 4)
            found = {}
            for node in self._nodes(tree):
                if node.get('app_id') in app_ids:
                    found[node['app_id']] = node.get('rect')
            return found if set(found) == set(app_ids) and all(
                r == FULL for r in found.values()) else None
        return self._wait(check)

    def debug_scene(self):
        return self.ipc('card_shell debug-scene')[0]['error']

    def selected_app_id(self):
        # shell.policy.selected (an index into the deck) is never the same
        # thing as Sway's real seat focus while merely browsing the deck:
        # restore() only reassigns seat focus at CS_RESTORE (leaving the
        # overview), so this reads the compositor's own selection directly
        # (debug_scene_text's selected_app_id field, nix/card-shell/
        # adapter.c) instead of polling the IPC tree's "focused" node,
        # which does not move until the deck is actually left.
        match = re.search(r'selected_app_id=(\S+)', self.debug_scene())
        assert match, self.debug_scene()
        value = match.group(1)
        return None if value == '(none)' else value

    def card_count(self):
        match = re.search(r'ordinary_maximized_cards=(\d+)', self.debug_scene())
        assert match, self.debug_scene()
        return int(match.group(1))

    def mode(self):
        # cs_mode (card-shell-policy.h): CS_NORMAL=0, CS_DECK=1,
        # CS_DRAGGING=2, CS_CLOSING=3, CS_ENTERING=4, CS_EXPANDING=5.
        # `next`/`previous` are a deliberate no-op while mode==CS_ENTERING
        # (cs_step, card-shell-policy.c), so a test must wait for the entry
        # animation to actually settle to CS_DECK before stepping -- reading
        # selected_app_id alone is not enough, since shell.policy.selected
        # is already correct (unchanged) throughout the settle.
        match = re.search(r' mode=(\d+) ', self.debug_scene())
        assert match, self.debug_scene()
        return int(match.group(1))


class VideoCardTests(unittest.TestCase):
    def test_video_is_ordinary_switchable_and_close_stops_controller(self):
        sway, client = binaries()
        names = ['k230.card.one', 'k230-video-software']
        with tempfile.TemporaryDirectory(prefix='card-shell-video-') as directory:
            session_dir = Path(directory) / 'session'
            stop_log = Path(directory) / 'video-stop-calls.jsonl'
            helper = Path(directory) / 'video-stop-helper'
            helper.write_text(
                '#!/bin/sh\n'
                f'printf "%s\\n" "$*" >> "{stop_log}"\n'
            )
            helper.chmod(0o700)
            with _Session(sway, client, session_dir, helper) as session:
                # Started and waited for in sequence, not concurrently: the
                # deck's own card order (shell.cards, populated in
                # card_shell_observe's view-map order) follows whichever
                # client's Wayland surface actually finishes mapping first,
                # which does not reliably follow subprocess start order when
                # both are launched together. Mapping k230.card.one to full
                # size before even starting the video client makes it
                # deterministically the earlier (index 0) card, so `next`/
                # `previous` below have fixed, known directions instead of
                # a flaky 50/50 order race.
                one = session.start_client('k230.card.one')
                session.wait_full(['k230.card.one'])
                video = session.start_client('k230-video-software')
                session.command('test-touch init')

                # Reached full usable size, the same as every other ordinary
                # card -- not left at a small floating geometry.
                session.wait_full(names)

                session.ipc('[app_id="k230-video-software"] focus')

                def focused():
                    return next((n.get('app_id') for n in session._nodes(session.ipc('', 4))
                                 if n.get('focused')), None)
                session._wait(lambda: focused() == 'k230-video-software')
                time.sleep(.15)

                # Present in the deck and reachable by the bottom-edge
                # switch gesture: a real touch-first vertical entry swipe
                # from the focused video card is accepted and settles into
                # the overview, exactly as it would for any other source
                # (cs_begin_entry/cs_enter, card-shell-policy.c).
                session.command('down 1 284 1200')
                # A frame must actually render between `down` and the first
                # `motion` so the adapter's per-frame geometry reconciliation
                # (`cs_entry_set_geometry`, called from card_shell_prepare)
                # sets a positive `entry_travel` before `cs_entry_motion`
                # runs; otherwise it sees entry_travel<=0 and immediately
                # fails the gesture (cs_entry_motion, card-shell-policy.c).
                # Other suites (tests/card_shell_runtime.py) get this for
                # free from a `grim` capture between down and motion; this
                # test has no capture, so it sleeps for one instead.
                time.sleep(.1)
                session.command('motion 1 284 1100')
                session.command('motion 1 284 1050')
                session.command('up 1')
                # Wait for the entry animation to actually settle to
                # CS_DECK (mode==1); see `mode()`'s own doc for why
                # selected_app_id alone is not a sufficient gate here.
                session._wait(lambda: session.mode() == 1)
                self.assertEqual(session.selected_app_id(), 'k230-video-software')
                self.assertEqual(session.card_count(), 2)

                # A genuine, switchable deck member: `previous`/`next` (the
                # same persistent-button route the bottom-edge gesture's own
                # lateral release resolves to) reaches the other card and
                # back. k230.card.one was deterministically mapped first
                # (see the sequenced start above), so it is deck index 0
                # and the video card is index 1 (the last): `previous`
                # moves toward index 0 (cs_step, card-shell-policy.c);
                # `next` from the already-last index is a clamped no-op.
                session.command('previous')
                session._wait(lambda: session.selected_app_id() == 'k230.card.one')
                session.command('next')
                session._wait(lambda: session.selected_app_id() == 'k230-video-software')

                # Close it through the persistent Close route --
                # tests/card_shell_runtime.py's own suite already proves
                # this IPC path requests a close on the currently selected
                # card, the same route the bottom-edge throw-to-close
                # gesture resolves to; not a special video-only control.
                self.assertFalse(stop_log.exists(), 'stop helper must not fire before a close')
                session.command('close')
                session._wait(lambda: 'K230_CARD_SHELL close-request' in session._logs())
                session._wait(lambda: video.poll() is not None, seconds=10)
                session._wait(lambda: stop_log.exists(), seconds=10)

                # The other ordinary card is unaffected and remains a card.
                self.assertIsNone(one.poll(), 'the other ordinary card must be unaffected by the close')
                session._wait(lambda: session.card_count() == 1)
                self.assertEqual(session.selected_app_id(), 'k230.card.one')

            calls = stop_log.read_text().splitlines()
            self.assertEqual(calls, ['stop'],
                              f'video-stop helper must be invoked exactly once with "stop": {calls}')


if __name__ == '__main__':
    unittest.main()
