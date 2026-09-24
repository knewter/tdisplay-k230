#!/usr/bin/env python3
"""Native socket tests for the opt-in Sway deck appearance receiver."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nix/card-shell/appearance.c'
HEADER = ROOT / 'nix/card-shell/appearance.h'
HARNESS = ROOT / 'tests/fixtures/card_appearance_receiver.c'
DEFAULT_ID = '111111111111111111111111'
NEXT_ID = '222222222222222222222222'


def generation(root, identity, *, gradient=False, wallpaper=False):
    directory = root / 'generations' / identity
    directory.mkdir(parents=True)
    palette = {'background': '#1e1e2e', 'dark_background': '#161622',
               'lighter_background': '#313244', 'foreground': '#cdd6f4'}
    (directory / 'report.json').write_text(json.dumps(
        {'generation': identity, 'palette': palette}))
    brush = {'kind': 'brush', 'stops': [
        {'argb': '#ff113355', 'offset': 0},
        {'argb': '#804477aa', 'offset': 1}], 'angle_degrees': 72.0, 'alpha': .75}
    selected = {'kind': 'brush', 'stops': [
        {'argb': '#ff4477aa', 'offset': 0}], 'angle_degrees': 0, 'alpha': 1}
    sections = {'card': {'background': brush, 'selected-background': selected}} if gradient else {}
    (directory / 'appearance.json').write_text(json.dumps(
        {'version': 1, 'generation': identity, 'background': 'background' if wallpaper else None,
         'sections': sections}))
    return directory


class AppearanceReceiver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='card-appearance-build-')
        included = Path(cls.build.name) / 'include/sway'
        included.mkdir(parents=True)
        (included / 'card_shell_appearance.h').symlink_to(HEADER)
        cls.binary = Path(cls.build.name) / 'receiver'
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'json-c'], text=True).split()
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(included.parent),
                        str(SOURCE), str(HARNESS), *flags, '-lm', '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='card-appearance-test-')
        self.root = Path(self.temp.name)
        self.default = generation(self.root, DEFAULT_ID)
        self.next = generation(self.root, NEXT_ID, gradient=True, wallpaper=True)
        self.socket = self.root / 'card-appearance.sock'
        self.process = subprocess.Popen([str(self.binary), str(self.socket), str(self.root),
                                         str(self.default)], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {DEFAULT_ID} 1 1 0')
        self.assertEqual(self.process.stdout.readline().strip(), 'READY')

    def tearDown(self):
        self.process.terminate()
        self.process.communicate(timeout=2)
        self.temp.cleanup()

    def exchange(self, phase, identity, path, **extra):
        request = {'protocol': 1, 'phase': phase, 'generation': identity,
                   'path': str(path) if path else None, **extra}
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(self.socket))
            client.sendall(json.dumps(request).encode() + b'\n')
            response = b''
            while not response.endswith(b'\n'):
                chunk = client.recv(256)
                if not chunk:
                    raise AssertionError('receiver closed without acknowledgement')
                response += chunk
        return json.loads(response)

    def test_prepare_commit_repeated_commit_and_rollback(self):
        prior = {'previous_generation': None, 'previous_path': None}
        prepare = self.exchange('prepare', NEXT_ID, self.next, **prior)
        self.assertEqual(prepare, {'protocol': 1, 'phase': 'prepare',
                                   'generation': NEXT_ID, 'status': 'ok'})
        self.assertEqual(self.exchange('commit', NEXT_ID, self.next)['status'], 'ok')
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {NEXT_ID} 2 1 1')
        self.assertEqual(self.exchange('commit', NEXT_ID, self.next)['status'], 'ok')
        self.assertEqual(self.exchange('rollback', None, None)['status'], 'ok')
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {NEXT_ID} 2 1 1')
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {DEFAULT_ID} 1 1 0')
        self.assertEqual(self.exchange('rollback', None, None)['status'], 'ok')
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {DEFAULT_ID} 1 1 0')

    def test_failed_prepare_cannot_commit_and_rollback_still_acks(self):
        (self.next / 'appearance.json').write_text(json.dumps(
            {'version': 1, 'generation': 'wrong', 'sections': {}, 'background': None}))
        prior = {'previous_generation': None, 'previous_path': None}
        self.assertEqual(self.exchange('prepare', NEXT_ID, self.next, **prior)['status'], 'error')
        self.assertEqual(self.exchange('commit', NEXT_ID, self.next)['status'], 'error')
        self.assertEqual(self.exchange('rollback', None, None)['status'], 'ok')
        self.assertEqual(self.process.stdout.readline().strip(), f'APPLY {DEFAULT_ID} 1 1 0')

    def test_foreign_path_rejected_and_socket_private(self):
        self.assertEqual(os.stat(self.socket).st_mode & 0o777, 0o600)
        foreign = self.root / 'foreign' / NEXT_ID
        foreign.parent.mkdir()
        foreign.symlink_to(self.next)
        self.assertEqual(self.exchange('prepare', NEXT_ID, foreign,
                                       previous_generation=None, previous_path=None)['status'], 'ok')
        # A real foreign tree cannot resolve to the prepared cache.
        other = self.root / 'other'
        other.mkdir()
        (other / NEXT_ID).symlink_to(self.default)
        self.assertEqual(self.exchange('prepare', NEXT_ID, other / NEXT_ID,
                                       previous_generation=None, previous_path=None)['status'], 'error')

    def test_fresh_state_root_uses_pinned_default(self):
        fresh = self.root / 'new-home' / 'state' / 'themes'
        fresh_socket = self.root / 'fresh.sock'
        process = subprocess.Popen([str(self.binary), str(fresh_socket), str(fresh),
                                    str(self.default)], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), f'APPLY {DEFAULT_ID} 1 1 0')
            self.assertEqual(process.stdout.readline().strip(), 'READY')
            self.assertTrue(fresh_socket.is_socket())
        finally:
            process.terminate()
            process.communicate(timeout=2)

    def test_rgba_palette_is_accepted(self):
        report = self.next / 'report.json'
        data = json.loads(report.read_text())
        data['palette']['background'] = '#1e1e2e80'
        report.write_text(json.dumps(data))
        self.assertEqual(self.exchange('prepare', NEXT_ID, self.next,
                                       previous_generation=None, previous_path=None)['status'], 'ok')

    def test_fifo_payload_rejected_without_blocking_compositor(self):
        payload = self.next / 'appearance.json'
        payload.unlink()
        os.mkfifo(payload)
        self.assertEqual(self.exchange('prepare', NEXT_ID, self.next,
                                       previous_generation=None, previous_path=None)['status'], 'error')
        self.assertIsNone(self.process.poll())


if __name__ == '__main__':
    unittest.main()
