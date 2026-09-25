#!/usr/bin/env python3
"""Regression for a real, independent Home-layer bug found while
investigating the reported bottom-band flicker (docs/evidence/card-shell/
bottom-band-flicker/hypotheses.md) -- explicitly NOT a claimed fix for that
hardware-level flicker itself; this is a separate defect the investigation
surfaced.

Root cause: `home_layer_sync` (nix/card-shell/adapter.c) previously ran
only from handle_result's CS_SHRINK branch and from restore(), toggling
layers.shell_bottom's scene node purely as a side effect of card-shell's
own state transitions. An unrelated Sway focus change while the overview
was still open (an IPC `[app_id=...] focus` command, or any other code
path that reassigns seat focus without going through card-shell) was
observed to re-enable that scene node -- home_enabled flips from 0 back to
1 -- *without* shell.active or shell.policy.mode changing at all, so
nothing in card-shell's own state machine ever ran home_layer_sync again to
correct it. Since the overview's own canvas is deliberately transparent
while active, this would let Home paint through the deck for the rest of
that session -- a real regression of the invariant
`the-overview-hides-the-home-screen` established
(docs/evidence/card-shell/overview-home-bleed-through/).

The fix makes `home_layer_sync` self-healing: `prepare_impl` (nix/card-shell/
adapter.c) now calls it unconditionally on every frame, before that frame's
scene is ever built or committed, so any such drift is corrected within one
frame regardless of what caused it.

Headless-QEMU-injected-input evidence only; no physical touch or panel
proof.
"""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from card_shell_test_support import binaries

SWAY_CONF = (
    'output HEADLESS-1 mode 568x1232\n'
    'seat seat0 fallback true\n'
    'focus_follows_mouse no\n'
    'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
    'border none, resize set 100 ppt 100 ppt, move position 0 0\n'
)


class HomeLayerSelfHealTest(unittest.TestCase):
    def test_unrelated_focus_change_during_overview_does_not_reshow_home(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix='card-shell-home-heal-') as directory:
            work = Path(directory)
            config = work / 'sway.conf'
            config.write_text(SWAY_CONF)
            env = dict(os.environ, XDG_RUNTIME_DIR=str(work), WLR_BACKENDS='headless',
                       WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
                       SWAY_K230_CARD_SHELL='1')
            log = (work / 'sway.log').open('w')
            procs = [subprocess.Popen(['/usr/bin/qemu-riscv64-static', sway, '-c', str(config), '-d'],
                                       env=env, stdout=log, stderr=log)]
            try:
                def logs():
                    return (work / 'sway.log').read_text()

                def wait(pred, seconds=30):
                    end = time.monotonic() + seconds
                    while time.monotonic() < end:
                        value = pred()
                        if value:
                            return value
                        time.sleep(.03)
                    raise AssertionError('timed out: ' + logs()[-4000:])
                wait(lambda: 'Running compositor on wayland display' in logs(), 60)
                env['WAYLAND_DISPLAY'] = next(
                    p.name for p in work.glob('wayland-*') if not p.name.endswith('.lock'))

                def ipc(command, kind=0, check=True):
                    with socket.socket(socket.AF_UNIX) as sock:
                        sock.settimeout(8)
                        sock.connect(str(next(work.glob('sway-ipc.*.sock'))))
                        payload = command.encode()
                        sock.sendall(b'i3-ipc' + struct.pack('=II', len(payload), kind) + payload)

                        def read(n):
                            data = b''
                            while len(data) < n:
                                chunk = sock.recv(n - len(data))
                                assert chunk
                                data += chunk
                            return data
                        header = read(14)
                        length, _ = struct.unpack('=II', header[6:])
                        result = json.loads(read(length))
                        if kind == 0 and check:
                            assert all(row['success'] for row in result), (command, result)
                        return result

                def debug_scene():
                    return ipc('card_shell debug-scene')[0]['error']

                def home_enabled():
                    match = re.search(r'home_enabled=(-?\d+)', debug_scene())
                    assert match, debug_scene()
                    return match.group(1) == '1'

                def nodes(tree):
                    yield tree
                    for node in tree.get('nodes', []) + tree.get('floating_nodes', []):
                        yield from nodes(node)

                names = ['k230.card.one', 'k230.card.two']
                streams = []
                for app_id in names:
                    stream = (work / (app_id + '.log')).open('w')
                    streams.append(stream)
                    procs.append(subprocess.Popen([client, '--app-id', app_id], env=env,
                                                   stdout=stream, stderr=stream))

                def mapped():
                    dump = json.dumps(ipc('', 4))
                    return all(name in dump for name in names)
                wait(mapped)
                time.sleep(.3)
                ipc('[app_id="k230.card.one"] focus')

                def focused():
                    return next((n.get('app_id') for n in nodes(ipc('', 4)) if n.get('focused')),
                                None)
                wait(lambda: focused() == 'k230.card.one')
                time.sleep(.2)
                self.assertTrue(home_enabled(), 'Home should be visible before any card is entered')

                ipc('card_shell enter')
                self.assertFalse(home_enabled(), 'Home must hide the instant the overview opens')

                # An unrelated Sway focus command -- nothing card-shell's own
                # state machine drives -- while the overview is still open.
                ipc('[app_id="k230.card.one"] focus')
                # The self-heal runs every frame, before that frame is ever
                # built or committed; give the compositor time to render at
                # least one frame and settle.
                time.sleep(.3)
                self.assertFalse(home_enabled(),
                                  'Home must stay hidden through an unrelated focus change '
                                  'while the overview is open')
                ipc('[app_id="k230.card.two"] focus')
                time.sleep(.3)
                self.assertFalse(home_enabled(),
                                  'Home must stay hidden through a second unrelated focus change')

                # And it genuinely comes back once the overview is actually
                # left -- the fix must not simply disable Home forever.
                ipc('card_shell back')
                wait(lambda: home_enabled())
            finally:
                for process in reversed(procs):
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                log.close()


if __name__ == '__main__':
    unittest.main()
