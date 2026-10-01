#!/usr/bin/env python3
"""Host tests: release safety boundaries; no network, Nix build or board."""
import importlib.util
import json
import lzma
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_image', Path(__file__).resolve().parents[1] / 'tools/release-image.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_dirty_source_refused(self):
        with patch.object(release, 'run', return_value=' M flake.nix'):
            with self.assertRaisesRegex(ValueError, 'dirty'):
                release.clean_source()

    def test_staging_inside_any_worktree_refused(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / 'tmp') as temp:
            subprocess.run(['git', 'init', '-q', temp], check=True)
            for asset_dir in (Path(temp) / 'nested' / 'assets', Path(temp) / '.git' / 'nested' / 'assets'):
                with self.assertRaisesRegex(ValueError, 'outside'):
                    release.outside_git(asset_dir)

    def test_existing_release_or_tag_refused(self):
        for pages in [[[{'tag_name': 'taken'}]], [[{'name': 'taken'}]]]:
            values = [json.dumps(pages)] if 'tag_name' in pages[0][0] else ['[[]]', json.dumps(pages)]
            with patch.object(release, 'run', side_effect=values):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    release.fresh_release('owner/repo', 'taken')

    def test_network_failure_is_not_absence(self):
        with patch.object(release, 'run', side_effect=subprocess.CalledProcessError(1, 'gh')):
            with self.assertRaises(subprocess.CalledProcessError):
                release.fresh_release('owner/repo', 'new')

    def test_assets_and_revision_provenance(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / 'tmp') as temp:
            p = Path(temp); image = p / 'source.img'; image.write_bytes(b'bootable bytes' * 100)
            compressed = p / ('tdisplay-k230-coherent-' + 'a' * 12 + '.img.xz'); compressed.write_bytes(lzma.compress(image.read_bytes()))
            outputs = {key: {'outPath': str(image), 'drvPath': 'source.drv'} for key in release.TARGETS}
            m = {'revision': 'a' * 40, 'target': 'sdImage-coherent', 'configuration': 'k230-coherent-shell',
                 'kernel_version': '6.6.36-xuantie', 'flake_lock_sha256': 'lock-hash', 'outputs': outputs, 'validation_limits': release.LIMITS,
                 'image': {'name': compressed.name, 'sha256': release.digest(image), 'bytes': image.stat().st_size},
                 'compressed': {'sha256': release.digest(compressed), 'bytes': compressed.stat().st_size}}
            (p / 'release-metadata.json').write_text(json.dumps(m))
            (p / 'release-notes.md').write_text(release.notes(m))
            names = [compressed.name, 'release-metadata.json', 'release-notes.md']
            release.write_checksums(p, names)
            with patch.object(release, 'revision_sha', return_value=m['revision']), patch.object(release, 'evaluate', return_value=outputs), patch.object(release, 'source_details', return_value={'kernel_version': m['kernel_version'], 'flake_lock_sha256': m['flake_lock_sha256']}):
                self.assertEqual(set(release.verify_stage(p, m)), set(names + ['SHA256SUMS']))
                compressed.write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    release.verify_stage(p, m)
            with patch.object(release, 'revision_sha', return_value=m['revision']), patch.object(release, 'evaluate', return_value={}), patch.object(release, 'source_details', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Provenance'):
                    release.verify_stage(p, m)


    def test_draft_without_tag_is_found_by_list(self):
        draft = {'id': 123, 'tag_name': 'new', 'draft': True}
        with patch.object(release, 'run', return_value=json.dumps([[draft]])) as run:
            self.assertEqual(release.find_created_draft('owner/repo', 'new'), draft)
            self.assertEqual(run.call_args.args[0][-1], 'repos/owner/repo/releases')

    def test_failed_remote_verification_keeps_draft(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / 'tmp') as temp:
            p = Path(temp); (p / 'one').write_bytes(b'asset')
            metadata = {'repository': 'owner/repo', 'tag': 'new', 'revision': 'a' * 40}
            info = {'id': 123, 'tag_name': 'new', 'draft': True, 'prerelease': True,
                    'target_commitish': metadata['revision'], 'assets': [{'name': 'one', 'size': 999}]}
            release.save_draft_receipt(p, metadata, ['one'], info)
            with patch.object(release, 'run', side_effect=[json.dumps(info), '']) as run:
                with self.assertRaisesRegex(ValueError, 'remains draft'):
                    release.finish_draft(p, metadata, ['one'])
                self.assertFalse(any('edit' in call.args[0] for call in run.call_args_list))

    def test_transaction_receipt_refuses_different_source_or_assets(self):
        with tempfile.TemporaryDirectory(dir=Path.home() / 'tmp') as temp:
            p = Path(temp); (p / 'one').write_bytes(b'asset')
            metadata = {'repository': 'owner/repo', 'tag': 'new', 'revision': 'a' * 40}
            info = {'id': 123, 'tag_name': 'new', 'draft': True, 'prerelease': True,
                    'target_commitish': metadata['revision']}
            release.save_draft_receipt(p, metadata, ['one'], info)
            with patch.object(release, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    release.finish_draft(p, {**metadata, 'revision': 'b' * 40}, ['one'])
                (p / 'one').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Assets differ'):
                    release.finish_draft(p, metadata, ['one'])
                run.assert_not_called()

    def test_wrong_draft_identity_refused(self):
        metadata = {'tag': 'new', 'revision': 'a' * 40}
        for overrides in ({'target_commitish': 'b' * 40}, {'draft': False}, {'tag_name': 'unrelated'}):
            info = {'tag_name': 'new', 'draft': True, 'prerelease': True, 'target_commitish': metadata['revision'], **overrides}
            with self.assertRaisesRegex(ValueError, 'identity'):
                release.draft_identity(info, metadata)


if __name__ == '__main__':
    unittest.main()
