#!/usr/bin/env python3
"""Host checks of UART proof parsing. These are not guest runtime evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('card_qemu', ROOT/'tools/qemu-card-shell-smoke.py')
smoke = importlib.util.module_from_spec(spec); spec.loader.exec_module(smoke)


class SmokeProofTests(unittest.TestCase):
    def reports(self, token='fresh'):
        return [{'run_id': run, 'evidence_class': 'qemu-system-guest-headless-injected',
                 'machine': 'riscv64', 'uid': 998, 'passed': sorted(smoke.REQUIRED)}
                for run in (token, token+'-restart')]

    def lines(self, reports):
        return ['K230_CARD_GUEST_RESULT '+json.dumps(report) for report in reports]

    def test_requires_two_actual_guest_reports(self):
        reports = self.reports()
        self.assertEqual(smoke.check_reports(self.lines(reports), 'fresh'), reports)
        for selected in ([], reports[:1], reports+reports[:1], self.reports('stale')):
            with self.subTest(selected=selected), self.assertRaises(RuntimeError):
                smoke.check_reports(self.lines(selected), 'fresh')

    def test_requires_nonroot_riscv_complete_runtime(self):
        for field, value in [('uid', 0), ('machine', 'x86_64'), ('passed', []),
                             ('evidence_class', 'headless-user-emulation')]:
            reports = self.reports(); reports[0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                smoke.check_reports(self.lines(reports), 'fresh')

    def test_guest_command_does_not_echo_a_success_marker(self):
        command = smoke.guest_command('fresh')
        self.assertNotIn('K230_CARD_GUEST_DONE fresh 0', command)
        self.assertIn('systemctl restart card-shell-smoke.service', command)
        self.assertIn('systemctl stop card-shell-smoke.service', command)

    def test_boot_prompt_or_echo_is_not_smoke_success(self):
        for script in ["print('[root@nixos:~]#', flush=True)",
                       "import sys; print(sys.stdin.readline(), flush=True)"]:
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(RuntimeError):
                smoke.supervise([sys.executable, '-c', script], Path(directory), 1)
            self.assertFalse(Path(directory).exists())

    def test_timeout_retains_transcript_without_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                smoke.supervise([sys.executable, '-c',
                                 "import time; print('boot-only', flush=True); time.sleep(30)"], path, 1)
            self.assertIn('boot-only', (path/'serial.log').read_text())
            self.assertFalse((path/'result.json').exists())

    def test_fixture_selection_is_explicit(self):
        self.assertNotIn('extendModules', smoke.configuration_expr(False))
        self.assertIn('qemu-card-shell-smoke.nix', smoke.configuration_expr(True))


if __name__ == '__main__':
    unittest.main()
