#!/usr/bin/env python3
"""Candidate presence rules for on-board staging, without a board."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('stage_tool',
    Path(__file__).resolve().parents[1] / 'tools/coherent-shell-board-stage.py')
stage = importlib.util.module_from_spec(spec); spec.loader.exec_module(stage)

SYSTEM = '/nix/store/' + 'a' * 32 + '-nixos-system-candidate'


class CandidatePresence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.current = Path(self.tmp.name) / 'current-system'

    def result(self, code):
        return subprocess.CompletedProcess([], code)

    def test_running_candidate_needs_no_store_query(self):
        self.current.symlink_to(SYSTEM)
        with patch.object(stage.subprocess, 'run') as run:
            self.assertTrue(stage.candidate_present(SYSTEM, self.current))
        run.assert_not_called()

    def test_imported_candidate_is_accepted_when_registered(self):
        self.current.symlink_to('/nix/store/' + 'b' * 32 + '-nixos-system-normal')
        with patch.object(stage.subprocess, 'run', return_value=self.result(0)) as run:
            self.assertTrue(stage.candidate_present(SYSTEM, self.current))
        self.assertEqual(run.call_args.args[0], ['nix-store', '--check-validity', SYSTEM])

    def test_unregistered_candidate_is_refused(self):
        self.current.symlink_to('/nix/store/' + 'b' * 32 + '-nixos-system-normal')
        with patch.object(stage.subprocess, 'run', return_value=self.result(1)):
            self.assertFalse(stage.candidate_present(SYSTEM, self.current))


if __name__ == '__main__':
    unittest.main()
