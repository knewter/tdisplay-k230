#!/usr/bin/env python3
"""Real compositor pointer dispatch and navigation; headless injection only."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import unittest

from card_shell_test_support import binaries


class PointerNavigation(unittest.TestCase):
    def test_pointer_home_cards_edges_and_spread(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix='k230-pointer-', dir=os.environ.get('TMPDIR')) as directory:
            work = Path(directory)
            conf = work / 'sway.conf'
            conf.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n'
                            'focus_follows_mouse no\n'
                            'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, '
                            'border none, resize set 100 ppt 100 ppt, move position 0 0\n')
            env = dict(os.environ, XDG_RUNTIME_DIR=str(work), WLR_BACKENDS='headless',
                       WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
                       SWAY_K230_CARD_TOUCH_FIRST='1')
            log = (work / 'sway.log').open('w')
            procs = [subprocess.Popen(['/usr/bin/qemu-riscv64-static', sway, '-c', str(conf), '-d'],
                                      env=env, stdout=log, stderr=log)]
            try:
                def wait(predicate, seconds=30):
                    until = time.monotonic() + seconds
                    while time.monotonic() < until:
                        value = predicate()
                        if value: return value
                        time.sleep(.03)
                    raise AssertionError('timeout: ' + (work / 'sway.log').read_text()[-3000:])
                wait(lambda: list(work.glob('sway-ipc.*.sock')), 60)
                env['WAYLAND_DISPLAY'] = wait(lambda: next((p.name for p in work.glob('wayland-*')
                    if not p.name.endswith('.lock')), None))

                def ipc(command='', kind=0, check=True):
                    with socket.socket(socket.AF_UNIX) as sock:
                        sock.settimeout(10)
                        sock.connect(str(next(work.glob('sway-ipc.*.sock'))))
                        payload = command.encode()
                        sock.sendall(b'i3-ipc' + struct.pack('=II', len(payload), kind) + payload)
                        def read(n):
                            buf = b''
                            while len(buf) < n:
                                chunk = sock.recv(n - len(buf))
                                if not chunk: raise AssertionError('IPC disconnected')
                                buf += chunk
                            return buf
                        header = read(14)
                        result = json.loads(read(struct.unpack('=II', header[6:])[0]))
                        if kind == 0 and check:
                            self.assertTrue(all(r['success'] for r in result), (command, result))
                        return result
                def nodes(tree):
                    yield tree
                    for n in tree.get('nodes', []) + tree.get('floating_nodes', []): yield from nodes(n)
                def apps():
                    return {n['app_id'] for n in nodes(ipc(kind=4)) if n.get('app_id')}
                def focused():
                    return next((n.get('app_id') for n in nodes(ipc(kind=4)) if n.get('focused')), None)
                def scene(): return ipc('card_shell debug-scene')[0]['error']
                def click(x, y):
                    ipc(f'seat seat0 cursor set {x} {y}; seat seat0 cursor press button1; '
                        'seat seat0 cursor release button1')
                def drag(x, y, end_x, end_y):
                    ipc(f'seat seat0 cursor set {x} {y}; seat seat0 cursor press button1')
                    time.sleep(.04)
                    ipc(f'seat seat0 cursor set {end_x} {end_y}; seat seat0 cursor release button1')
                for name in ('k230.card.one', 'k230.card.two'):
                    procs.append(subprocess.Popen([client, '--app-id', name], env=env,
                                                 stdout=log, stderr=log))
                wait(lambda: len(apps()) == 2)
                ipc('[app_id="k230.card.one"] focus')
                wait(lambda: focused() == 'k230.card.one')
                original = apps()
                ipc('card_shell enter')
                # Hover must neither activate nor select the underlying hidden app.
                ipc('seat seat0 cursor set 284 600')
                self.assertIn('mode=1 ', scene())
                click(284, 1210)  # Home footer: no app close commands.
                wait(lambda: 'home_selected=1 ' in scene())
                self.assertEqual(apps(), original)
                self.assertIsNone(focused())
                ipc('card_shell enter')
                ipc('seat seat0 cursor set 284 600; seat seat0 cursor press button5')
                self.assertIn('selected_app_id=k230.card.two', scene())
                # Spread's binding target uses the same animated policy as a tap.
                ipc('card_shell activate')
                wait(lambda: focused() == 'k230.card.two' and 'mode=0 ' in scene())
                self.assertEqual(apps(), original)
                drag(284, 1230, 284, 900)
                wait(lambda: 'mode=1 ' in scene())
                click(284, 650)
                wait(lambda: focused() == 'k230.card.two' and 'mode=0 ' in scene())
                ipc('card_shell enter')
                # A real compositor-owned touch tap on the same footer.
                ipc('card_shell down 91 284 1210; card_shell up 91')
                wait(lambda: 'home_selected=1 ' in scene())
                self.assertEqual(apps(), original)
                # A cancelled pointer stream may never activate the restored app.
                ipc('card_shell enter')
                ipc('seat seat0 cursor set 284 650; seat seat0 cursor press button1; card_shell cancel; '
                    'seat seat0 cursor release button1')
                self.assertEqual(apps(), original)
                ipc('card_shell home')
                wait(lambda: 'home_selected=1 ' in scene())
                ipc('card_shell enter')
                ipc('card_shell activate')
                wait(lambda: 'mode=0 ' in scene())
            finally:
                for proc in reversed(procs):
                    if proc.poll() is None: proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                log.close()
                if os.environ.get('CARD_NAV_LOG'):
                    shutil.copyfile(work / 'sway.log', os.environ['CARD_NAV_LOG'])
