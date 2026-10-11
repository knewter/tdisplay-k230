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
        scratch = Path.home() / 'tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
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

    def test_no_active_theme_is_a_valid_install_baseline(self):
        with patch.object(install, 'Path', return_value=self.root / 'absent'):
            self.assertEqual(install.appearance(),
                             {'generation': None, 'report_sha256': None})

    def userspace_update(self):
        files = {'Image': 'a'*64, 'initrd.uimg': 'b'*64}
        candidate = dict(system='/nix/store/'+'c'*32+'-nixos-system-candidate',
                         kernel='/nix/store/kernel/Image', bundle='/nix/store/bundle',
                         boot_files={name: {'sha256': value} for name, value in files.items()})
        baseline = dict(system='/nix/store/'+'d'*32+'-nixos-system-accepted',
                        kernel=candidate['kernel'], boot_files=files)
        q = {field: candidate[field] for field in ('system', 'kernel', 'bundle')}
        q.update(evidence_class='operator-authorized-userspace-update',
                 shell_executable='/nix/store/shell/bin/shell',
                 deployment_authorized=True, additional_physical_collection_waived=True,
                 operator_instruction='continue', source_revision='e'*40,
                 accepted_baseline=baseline)
        state = dict(normal_profile=baseline['system'], normal_files=candidate['boot_files'])
        return candidate, q, state

    def test_userspace_authorization_is_distinct_from_finger_proof(self):
        candidate, q, state = self.userspace_update()
        install.validate_qualification(q, candidate)
        install.validate_install_baseline(q, state)
        for field, value in [('deployment_authorized', False),
                             ('additional_physical_collection_waived', False),
                             ('operator_instruction', ''), ('source_revision', 'unbound'),
                             ('checks', {'home_to_all_apps': True})]:
            wrong = copy.deepcopy(q); wrong[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                install.validate_qualification(wrong, candidate)

    def test_userspace_waiver_cannot_authorize_changed_boot_code(self):
        candidate, q, _ = self.userspace_update()
        wrong = copy.deepcopy(q); wrong['accepted_baseline']['kernel'] = '/another/Image'
        with self.assertRaisesRegex(ValueError, 'changes kernel'):
            install.validate_qualification(wrong, candidate)
        for name in ('Image', 'initrd.uimg'):
            wrong = copy.deepcopy(q); wrong['accepted_baseline']['boot_files'][name] = 'f'*64
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'changes '+name):
                install.validate_qualification(wrong, candidate)

    def test_userspace_baseline_must_match_the_protected_board_state(self):
        candidate, q, state = self.userspace_update()
        wrong = copy.deepcopy(state); wrong['normal_profile'] = candidate['system']
        with self.assertRaisesRegex(ValueError, 'baseline profile differs'):
            install.validate_install_baseline(q, wrong)
        for name in ('Image', 'initrd.uimg'):
            wrong = copy.deepcopy(state); wrong['normal_files'][name]['sha256'] = 'f'*64
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'baseline differs'):
                install.validate_install_baseline(q, wrong)

    def test_active_theme_identity_is_preserved(self):
        generation = self.root / 'generation-1'; generation.mkdir()
        report = generation / 'report.json'; report.write_bytes(b'{}\n')
        selection = self.root / 'active'; selection.symlink_to(generation)
        with patch.object(install, 'Path', return_value=selection):
            self.assertEqual(install.appearance(),
                             {'generation': generation.name,
                              'report_sha256': install.digest(report)})

    def test_broken_theme_selection_still_blocks_installation(self):
        selection = self.root / 'active'; selection.symlink_to(self.root / 'missing')
        with patch.object(install, 'Path', return_value=selection):
            with self.assertRaises(FileNotFoundError):
                install.appearance()


if __name__ == '__main__':
    unittest.main()
