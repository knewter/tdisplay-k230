#!/usr/bin/env python3
"""Check the evaluated coherent NixOS service can survive prolonged output loss."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KeyboardServicePolicy(unittest.TestCase):
    def test_restart_is_not_latched_off(self):
        reply = subprocess.run(
            ['nix', 'eval', '--json',
             '.#nixosConfigurations.k230-coherent-shell.config.systemd.services.shell-keyboard',
             '--apply', 's: { startLimitIntervalSec = s.startLimitIntervalSec; '
             'restart = s.serviceConfig.Restart; restartSec = s.serviceConfig.RestartSec; '
             'bindsTo = s.bindsTo; after = s.after; execStart = s.serviceConfig.ExecStart; }'],
            cwd=ROOT, check=True, capture_output=True, text=True)
        service = json.loads(reply.stdout)
        self.assertEqual(service['startLimitIntervalSec'], 0)
        self.assertEqual(service['restart'], 'always')
        self.assertGreaterEqual(service['restartSec'], 2)
        self.assertIn('shell.service', service['bindsTo'])
        self.assertIn('shell.service', service['after'])
        self.assertTrue(service['execStart'].endswith(
            '/bin/k230-supervised-keyboard'))


if __name__ == '__main__':
    unittest.main()
