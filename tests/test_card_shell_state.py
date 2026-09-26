#!/usr/bin/env python3
"""Compile and execute the product C policy; no duplicate model or hardware claim."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = ('enter-expand horizontal overview-geometry '
         'scroll-fling-multi-card scroll-slow-release-snaps-nearest scroll-catch-mid-coast scroll-end-clamp-soft '
         'adjacent-tap adjacent-throw privacy privacy-transition '
         'close-recovery slow-drag repeated-timestamp-throw repeated-timestamp-rejection source-loss restore-gesture multi-contact edge '
         'keyboard-geometry changed-ids many-cards reduced-motion invalid-events buttons stream-cancel stream-cancel-multitouch tracked-entry '
         'entry-geometry-rejects-undersized-source '
         'two-axis-entry two-axis-conflicts direct-carousel app-switch-swipe tracked-expansion randomized').split()


class ProductPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='card-shell-policy-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / 'policy-test'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                        '-Werror', '-pedantic', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', '-I', str(ROOT / 'nix/card-shell-policy'),
                        str(ROOT / 'tests/card_shell_policy_driver.c'),
                        str(ROOT / 'nix/card-shell-policy/card-shell-policy.c'),
                        '-lm', '-o', str(cls.binary)], check=True)


def make_test(case):
    def test(self):
        result = subprocess.run([str(self.binary), case], capture_output=True, text=True,
                                timeout=10, env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), f'PASS {case}')
    return test


for name in CASES:
    setattr(ProductPolicyTests, 'test_' + name.replace('-', '_'), make_test(name))

if __name__ == '__main__':
    unittest.main()
