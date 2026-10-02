#!/usr/bin/env python3
"""Reject malformed staged boot plans before opening serial or rebooting."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('coherent_boot',
    Path(__file__).resolve().parents[1] / 'tools/coherent-shell-board-boot.py')
boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)


class StagedBootIdentity(unittest.TestCase):
    def setUp(self):
        files = {n: dict(bytes=211, sha256='a'*64, crc32='b'*8) for n in
                 ('Image', 'initrd.uimg', 'bootargs.txt', 'k230-tdisplay.dtb')}
        self.candidate = dict(system='/nix/store/' + 'c'*32 + '-nixos-system-26.11',
                              boot_files=files)
        normal = copy.deepcopy(files)
        normal['fw_jump_add_uboot_head.bin'] = dict(bytes=270808, sha256='d'*64, crc32='e'*8)
        self.state = dict(candidate=copy.deepcopy(self.candidate), normal_files=normal,
                          stage='/var/lib/k230/coherent-boot/candidate-20261001')

    def test_valid_plan(self):
        boot.validate_state(self.state, self.candidate)

    def test_different_staged_candidate(self):
        self.state['candidate']['system'] += '-another'
        with self.assertRaisesRegex(ValueError, 'differs'):
            boot.validate_state(self.state, self.candidate)

    def test_staging_path_injection_and_escape(self):
        for path in ('/var/lib/k230/coherent-boot/x; reset', '/var/lib/k230/coherent-boot/../boot',
                     '/boot', '/var/lib/k230/coherent-boot/x\nreset'):
            self.state['stage'] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'staging path'):
                boot.validate_state(self.state, self.candidate)

    def test_system_path_injection(self):
        self.candidate['system'] += '; reset'
        self.state['candidate'] = copy.deepcopy(self.candidate)
        with self.assertRaisesRegex(ValueError, 'system path'):
            boot.validate_state(self.state, self.candidate)

    def test_baseline_and_candidate_checksums_and_bounds(self):
        for which in ('normal_files', 'candidate'):
            for key, bad in [('bytes', 0), ('bytes', True), ('bytes', 64*1024**2),
                             ('sha256', 'x'*64), ('crc32', '123')]:
                state = copy.deepcopy(self.state); candidate = copy.deepcopy(self.candidate)
                files = state['normal_files'] if which == 'normal_files' else candidate['boot_files']
                files['Image'][key] = bad
                state['candidate'] = copy.deepcopy(candidate)
                with self.subTest(which=which, key=key, bad=bad), self.assertRaises(ValueError):
                    boot.validate_state(state, candidate)


if __name__ == '__main__':
    unittest.main()
