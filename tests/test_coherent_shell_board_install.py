#!/usr/bin/env python3
"""Exercise qualification and boot-file interruption handling without a board."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('install_boot',
    Path(__file__).resolve().parents[1] / 'tools/coherent-shell-board-install.py')
install = importlib.util.module_from_spec(spec); spec.loader.exec_module(install)


class BootInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home() / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'root-backup'; self.source.write_bytes(b'new kernel')
        self.target = self.root / 'Image'; self.target.write_bytes(b'old kernel')
        self.expected = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def test_atomic_replacement(self):
        self.assertEqual(install.replace_payload(self.source, self.target, self.expected), 'atomic-rename')
        self.assertEqual(self.target.read_bytes(), b'new kernel')
        self.assertEqual(self.source.read_bytes(), b'new kernel')

    def test_wrong_source_never_changes_target(self):
        with self.assertRaisesRegex(ValueError, 'source payload'):
            install.replace_payload(self.source, self.target, 'a'*64)
        self.assertEqual(self.target.read_bytes(), b'old kernel')

    def test_protected_selector_is_not_replaceable(self):
        target = self.root / 'force_dtb'; target.write_bytes(b'protected')
        with self.assertRaisesRegex(ValueError, 'unrelated boot file'):
            install.replace_payload(self.source, target, self.expected)
        self.assertEqual(target.read_bytes(), b'protected')

    def test_insufficient_space_does_not_delete_target(self):
        with patch.object(install.shutil, 'disk_usage') as usage:
            usage.return_value.free = 0
            with self.assertRaisesRegex(ValueError, 'insufficient boot space'):
                install.replace_payload(self.source, self.target, self.expected)
        self.assertEqual(self.target.read_bytes(), b'old kernel')

    def test_root_backed_gap_and_copy_failure_preserves_backup(self):
        self.source.write_bytes(b'n' * (2*1024**2)); self.target.write_bytes(b'o' * (2*1024**2))
        expected = install.digest(self.source)
        with patch.object(install.shutil, 'disk_usage') as usage, patch.object(install.shutil, 'copyfileobj', side_effect=OSError('injected interruption')):
            usage.return_value.free = 1536*1024
            with self.assertRaisesRegex(OSError, 'injected interruption'):
                install.replace_payload(self.source, self.target, expected)
        self.assertFalse(self.target.exists())
        self.assertEqual(install.digest(self.source), expected)
        partial = self.root / 'Image.k230-new'; self.assertTrue(partial.exists())
        with self.assertRaisesRegex(ValueError, 'unfinished payload'):
            install.replace_payload(self.source, self.target, expected)
        partial.unlink()
        self.assertEqual(install.replace_payload(self.source, self.target, expected), 'atomic-rename')
        self.assertEqual(install.digest(self.target), expected)

    def test_successful_root_backed_gap(self):
        self.source.write_bytes(b'n' * (2*1024**2)); self.target.write_bytes(b'o' * (2*1024**2))
        with patch.object(install.shutil, 'disk_usage') as usage:
            usage.return_value.free = 1536*1024
            self.assertEqual(install.replace_payload(self.source, self.target, install.digest(self.source)),
                             'root-backed-replacement')
        self.assertEqual(self.target.read_bytes(), self.source.read_bytes())

    def test_qualification_requires_exact_bundle_and_user_checks(self):
        candidate = dict(system='/nix/store/system', kernel='/nix/store/kernel/Image', bundle='/nix/store/bundle')
        q = dict(candidate, evidence_class='operator-real-finger-report', shell_executable='/nix/store/shell/bin/shell',
                 checks={'home_to_all_apps': True, 'bottom_handle_to_overview': True, 'terminal_open_and_return': True})
        install.validate_qualification(q, candidate)
        for field in ('system', 'kernel', 'bundle', 'evidence_class', 'shell_executable', 'checks'):
            wrong = copy.deepcopy(q); wrong[field] = {} if field == 'checks' else 'another'
            with self.subTest(field=field), self.assertRaises(ValueError):
                install.validate_qualification(wrong, candidate)


if __name__ == '__main__':
    unittest.main()
