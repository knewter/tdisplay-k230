#!/usr/bin/env python3
"""Compile the real keyboard gesture policy with sanitizers; no hardware claim."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
CASES = ('early-chord', 'late-second', 'horizontal-first', 'stationary-chord', 'grip-keys', 'stale-velocity',
         'surface-loss', 'overlay-isolation', 'reduced', 'elapsed-cadence',
         'contact-drain', 'map-timeout', 'many-contacts', 'end-stream', 'hide-timeout')
class KeyboardGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='keyboard-gesture-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = Path(cls.tmp.name) / 'gesture'
        subprocess.run([os.environ.get('CC','cc'), '-std=c11', '-Wall', '-Wextra',
                        '-Werror', '-pedantic', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I', str(ROOT/'nix/card-keyboard-policy'),
                        str(ROOT/'tests/keyboard_gesture_driver.c'),
                        str(ROOT/'nix/card-keyboard-policy/keyboard-gesture.c'),
                        '-lm', '-o', str(cls.exe)], check=True)
for case in CASES:
    def test(self, name=case):
        r = subprocess.run([str(self.exe), name], capture_output=True, text=True,
                           timeout=10, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1'))
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(r.stdout.strip(),f'PASS {name}')
    setattr(KeyboardGestureTests, 'test_'+case.replace('-','_'), test)
if __name__=='__main__': unittest.main()
