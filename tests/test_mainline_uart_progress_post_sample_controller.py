"""Host-only fixed-frame, actual pump and immutable artifact qualification fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('breadcrumb_fixtures', ROOT / 'tests/test_mainline_uart_progress_breadcrumbs_controller.py')
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)
old, trial = bc.old, bc.trial
ARGS = bc.ARGS + ' ' + trial.UART_PROGRESS_POST_SAMPLE_FLAG
CMDLINE = ('[    0.2] Kernel command line: ' + ARGS.removeprefix('bootargs=') + '\n').encode()
BOOT = old.BANNER + CMDLINE
AFTER, THIRD = (b'\n' + line for line in trial.UART_PROGRESS_POST_SAMPLE)
SELECT = dict(same_image_shell_pid1=True, uart_progress=True, uart_progress_breadcrumbs=True, uart_progress_post_sample=True)


def observe(wire):
    return trial.observe_uart_progress(wire, old.TOKEN, ARGS, timeout=5, readiness_timeout=3,
                                      clock=old.Clock(), uart_progress_breadcrumbs=True, uart_progress_post_sample=True)


class PostSampleControllerTests(unittest.TestCase):
    def test_exact_protocol_rejects_echo_extra_case_version_and_interleaving(self):
        self.assertEqual(trial.uart_progress_post_sample_record(AFTER[1:]), 'after-n1-write')
        self.assertEqual(trial.uart_progress_post_sample_record(THIRD[1:]), 'third-post-sleep')
        for bad in (AFTER, AFTER[1:-1], AFTER[1:] + THIRD[1:], AFTER[1:].replace(b'UPP1', b'UPP2'),
                    AFTER[1:].upper(), AFTER[1:].replace(b'\n', b' extra=1\n'),
                    b"printf '" + AFTER[1:] + b"'", AFTER[1:].replace(b'point=', b'[1.0] point=')):
            with self.subTest(bad=bad): self.assertIsNone(trial.uart_progress_post_sample_record(bad))

    def test_real_pump_split_full_sequence_one_stimulus(self):
        wire = old.Wire([bc.ENTRY[:8], bc.ENTRY[8:], BOOT[:30], BOOT[30:] + old.READY,
                         bc.WAKE, old.record(0), old.record(1), AFTER[:11], AFTER[11:], THIRD,
                         *[old.record(n) for n in range(2, 6)]])
        result = observe(wire)
        self.assertTrue(result['post_sample_complete']); self.assertTrue(result['breadcrumbs_complete'])
        self.assertTrue(result['records_complete']); self.assertTrue(result['receipt_observed'])
        self.assertEqual(wire.writes, [(trial.reception_command(old.TOKEN) + '\r').encode()])
        self.assertFalse(result['reboot_requested'])

    def test_same_chunk_prompt_and_new_points_allow_only_one_stimulus(self):
        result = observe(old.Wire([BOOT + bc.ENTRY + bc.WAKE + old.READY + AFTER + THIRD]))
        self.assertTrue(result['readiness_observed']); self.assertTrue(result['post_sample_complete'])
        self.assertEqual(result['stimulus_attempts'], 1)
        self.assertTrue(all(not p['observed_after_stimulus'] for p in result['post_sample']))

    def test_CRLF_allowed_embedded_CR_rejected_without_input(self):
        result = observe(old.Wire([(BOOT + bc.ENTRY + bc.WAKE + old.READY + AFTER + THIRD).replace(b'\n', b'\r\n')]))
        self.assertTrue(result['post_sample_complete']); self.assertEqual(result['stimulus_attempts'], 1)
        for bad in (AFTER.replace(b'after-n1', b'after-\rn1'), THIRD.replace(b'point=', b'point=\r')):
            wire = old.Wire([BOOT + bad + old.READY])
            self.assertIn('malformed-post-sample', observe(wire)['protocol_errors']); self.assertEqual(wire.writes, [])

    def test_duplicate_reverse_echo_and_interleave_before_readiness_stop_input(self):
        for rows, error in ((AFTER + AFTER, 'duplicate-post-sample'), (THIRD + AFTER, 'post-sample-order'),
                            (AFTER.replace(b'UPP1', b'UPP9'), 'malformed-post-sample'),
                            (b"printf '" + AFTER[1:] + b"'\n", 'malformed-post-sample'),
                            (AFTER.replace(b'point=', b'point=[1.1] printk\n'), 'malformed-post-sample')):
            wire = old.Wire([BOOT + rows + old.READY]); result = observe(wire)
            self.assertIn(error, result['protocol_errors']); self.assertFalse(result['post_sample_complete'])
            self.assertEqual(wire.writes, [])

    def test_truncation_or_late_duplicate_never_adds_input(self):
        for rows, error in ((AFTER[:-1], 'truncated-post-sample'), (AFTER + AFTER, 'duplicate-post-sample')):
            wire = old.Wire([BOOT + old.READY, rows], reply=False); result = observe(wire)
            self.assertIn(error, result['protocol_errors']); self.assertEqual(len(wire.writes), 1)
            self.assertFalse(result['reboot_requested'])

    def test_missing_first_preserves_independent_third_point_without_error(self):
        result = observe(old.Wire([BOOT + old.READY, THIRD], reply=False))
        self.assertEqual(result['post_sample'], [{'point': 'third-post-sleep', 'observed_after_stimulus': True}])
        self.assertFalse(result['post_sample_complete']); self.assertEqual(result['protocol_errors'], [])
        self.assertFalse(result['receipt_observed'])

    def test_missing_numeric_output_does_not_invalidate_return_points(self):
        result = observe(old.Wire([BOOT + old.READY, AFTER, THIRD]))
        self.assertTrue(result['post_sample_complete']); self.assertEqual(result['records'], [])
        self.assertFalse(result['records_complete']); self.assertEqual(result['protocol_errors'], [])

    def test_missing_points_keep_receipt_numeric_and_old_modes_independent(self):
        result = observe(old.Wire([BOOT + bc.ENTRY + bc.WAKE + old.READY, *[old.record(n) for n in range(6)]]))
        self.assertTrue(result['records_complete']); self.assertTrue(result['receipt_observed'])
        self.assertFalse(result['post_sample_complete'])
        result = bc.observe(old.Wire([bc.BOOT + bc.ENTRY + bc.WAKE + old.READY]))
        self.assertNotIn('post_sample', result); self.assertTrue(result['breadcrumbs_complete'])

    def test_stale_capture_missing_wrong_duplicate_received_args_trust_no_points(self):
        for boot in (b'', old.BANNER, bc.BOOT, old.BANNER + CMDLINE + CMDLINE,
                     BOOT.replace(b'7.3.0-rc5', b'6.6.36')):
            wire = old.Wire([AFTER, THIRD, boot + old.READY])
            wire.buffer = BOOT + old.READY + AFTER + THIRD
            result = observe(wire); self.assertEqual(result['post_sample'], []); self.assertEqual(wire.writes, [])

    def test_points_never_authorize_input_without_fresh_init_and_prompt(self):
        for ready in (b'', b'sh-5.3# ', old.READY.replace(b'sh-5.3# ', b'> '),
                      old.READY.replace(b'sh-5.3# ', b"printf 'sh-5.3# '")):
            wire = old.Wire([BOOT + AFTER + THIRD + ready]); result = observe(wire)
            self.assertTrue(result['post_sample_complete']); self.assertEqual(wire.writes, [])

    def test_missing_candidate_with_independent_normal_return_is_incomplete(self):
        result = observe(old.Wire([old.NORMAL]))
        self.assertTrue(result['normal_prompt_observed']); self.assertFalse(result['post_sample_complete'])
        self.assertEqual(result['stimulus_attempts'], 0); self.assertLess(result['capture_seconds'], 5)

    def test_selector_rejections_before_preparation_or_serial(self):
        for changes in ({'uart_progress_post_sample': 1}, {'uart_progress_post_sample': None},
                        {'uart_progress_breadcrumbs': False}, {'uart_progress': False}, {'same_image_shell_pid1': False}):
            with mock.patch.object(trial, 'prepare_trial') as prep, mock.patch.object(trial, 'PrivateSession') as port:
                with self.assertRaises(ValueError): trial.run_trial(Path('m'), Path('l'), Path('r'), 'minimal', **(SELECT | changes))
                prep.assert_not_called(); port.assert_not_called()
        for mode in ('label', 'survey', 'root-mount'):
            with mock.patch.object(trial, 'prepare_trial') as prep, self.assertRaises(ValueError):
                trial.run_trial(Path('m'), Path('l'), Path('r'), mode, **SELECT)
            prep.assert_not_called()

    def test_cli_default_unchanged_and_explicit_typed_dispatch(self):
        with mock.patch.object(sys, 'argv', ['trial', '--uart-progress-post-sample']), mock.patch.object(trial, 'run_trial') as run, mock.patch('sys.stderr'):
            with self.assertRaises(SystemExit): trial.main()
            run.assert_not_called()
        for flags, enabled in (([], False), (['--same-image-shell-pid1', '--uart-progress', '--uart-progress-breadcrumbs', '--uart-progress-post-sample'], True)):
            with mock.patch.object(sys, 'argv', ['trial', *flags]), mock.patch.object(trial, 'run_trial', return_value=True) as run:
                self.assertEqual(trial.main(), 0); self.assertEqual(run.call_args.kwargs.get('uart_progress_post_sample', False), enabled)

    def test_transport_exact_single_addition_and_unsafe_duplicates_rejected(self):
        command = trial.shell_pid1_transport(ARGS, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True, uart_progress_post_sample=True)
        self.assertEqual(command, 'setenv bootargs "' + ARGS.removeprefix('bootargs=') + '"')
        self.assertEqual(ARGS.split(), bc.ARGS.split() + [trial.UART_PROGRESS_POST_SAMPLE_FLAG])
        self.assertLess(len(command), 512); self.assertNotIn('${', command)
        for args in (ARGS + ' ' + trial.UART_PROGRESS_POST_SAMPLE_FLAG, ARGS + '\n', ARGS + ';saveenv', ARGS.replace('post_sample=1', 'post_sample=0')):
            with self.assertRaises(ValueError): trial.shell_pid1_transport(args, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True, uart_progress_post_sample=True)
        with self.assertRaises(ValueError): trial.shell_pid1_transport(ARGS, old.fixtures.SYSTEM, uart_progress=True, uart_progress_post_sample=True)

    def artifact_fixture(self, root):
        p, source, worker, image = bc.BreadcrumbControllerTests().artifact_fixture(root)
        worker.write_bytes(b'reviewed post-sample worker fixture')
        image.write_bytes(image.read_bytes() + AFTER + b'\0' + THIRD + b'\0k230.uart_progress_post_sample=\0')
        return p, source, worker, image

    def test_new_same_drv_source_and_unique_compiled_markers_are_required(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, 'immutable_store_path', side_effect=lambda p, label: p):
            p, source, worker, image = self.artifact_fixture(Path(directory)); digest = hashlib.sha256(worker.read_bytes()).hexdigest()
            drv = p['uart_progress_kernel']['derivation']
            for desc in ({drv: {'env': {'src': str(source)}}}, {'version': 4, 'derivations': {Path(drv).name: {'structuredAttrs': {'src': str(source)}}}}):
                with mock.patch.object(trial, 'UART_POST_SAMPLE_SOURCE_SHA256', digest), mock.patch.object(trial.subprocess, 'check_output', return_value=json.dumps(desc)) as query:
                    proof = trial.inspect_uart_breadcrumb_kernel(p, uart_progress_post_sample=True)
                    self.assertEqual(proof['source'], str(source)); self.assertEqual(proof['worker_sha256'], digest)
                    self.assertEqual(len(proof['marker_offsets']), 4); self.assertEqual(query.call_args.args[0][-1], drv)
                    self.assertIn('--offline', query.call_args.args[0]); self.assertNotIn('build', query.call_args.args[0])
                    with self.assertRaises(ValueError): trial.inspect_uart_breadcrumb_kernel(p)

    def test_legacy_worker_and_missing_duplicate_new_image_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, 'immutable_store_path', side_effect=lambda p, label: p):
            p, source, worker, image = self.artifact_fixture(Path(directory)); digest = hashlib.sha256(worker.read_bytes()).hexdigest()
            good = image.read_bytes(); drv = p['uart_progress_kernel']['derivation']
            desc = json.dumps({drv: {'env': {'src': str(source)}}})
            for failure in ('legacy-worker', 'old-image', 'missing-after', 'duplicate-third', 'missing-gate'):
                worker.write_bytes(b'legacy worker' if failure == 'legacy-worker' else b'reviewed post-sample worker fixture')
                image.write_bytes(good.replace(AFTER + b'\0', b'') if failure == 'missing-after' else good + THIRD + b'\0' if failure == 'duplicate-third' else good.replace(b'k230.uart_progress_post_sample=\0', b'') if failure == 'missing-gate' else b'legacy Image' if failure == 'old-image' else good)
                with mock.patch.object(trial, 'UART_POST_SAMPLE_SOURCE_SHA256', digest), mock.patch.object(trial.subprocess, 'check_output', return_value=desc), self.assertRaises(ValueError):
                    trial.inspect_uart_breadcrumb_kernel(p, uart_progress_post_sample=True)

    def test_variant_failure_never_opens_serial_or_output_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p = {'bundle': root, 'system': old.fixtures.SYSTEM, 'normal': old.fixtures.normal(), 'helper_text': 'pass'}
            with mock.patch.object(trial, 'prepare_trial', return_value=p), mock.patch.object(trial, 'inspect_shell_initrd', return_value={'bash': old.fixtures.BASH}), mock.patch.object(trial, 'inspect_uart_progress_kernel', return_value={'config_sha256': 'fixture'}), mock.patch.object(trial, 'inspect_uart_breadcrumb_kernel', side_effect=ValueError('legacy source')) as qualify, mock.patch.object(trial, 'PrivateSession') as port:
                with self.assertRaises(ValueError): trial.run_trial(root/'m', root/'l', root/'r', 'minimal', **SELECT)
                qualify.assert_called_once(); self.assertTrue(qualify.call_args.kwargs['uart_progress_post_sample'])
                port.assert_not_called(); self.assertFalse((root/'l').exists()); self.assertFalse((root/'r').exists())

    def test_independent_protected_return_never_upgrades_missing_points_or_bad_identity(self):
        normal = old.fixtures.normal(); normal['trial_from_boot_id'] = normal['boot_id']
        after = old.fixtures.Session().run_state('postflight', old.TOKEN)
        for complete, protected in ((False, True), (True, True), (True, False)):
            wire = old.Wire([BOOT + bc.ENTRY + bc.WAKE + old.READY,
                             *[old.record(n) for n in range(6)],
                             AFTER + THIRD if complete else THIRD, old.NORMAL])
            wire.upload_text = mock.Mock()
            wire.run_state = mock.Mock(return_value=after if protected else after | {'kernel': '/wrong'})
            prepared = {'bootargs': ARGS, 'normal': normal, 'helper_text': 'fixture',
                        'system': old.fixtures.SYSTEM, 'bundle': Path('/fixture'),
                        'uart_progress_kernel': {}, 'uart_progress_breadcrumb_kernel': {},
                        'uart_progress_post_sample_kernel': {}}
            original = trial.observe_uart_progress
            def fast(active, token, args, **kwargs):
                return original(active, token, args, timeout=5, readiness_timeout=3, clock=old.Clock(), **kwargs)
            with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, 'observe_uart_progress', side_effect=fast):
                path = Path(directory)/'result'
                accepted = trial.finish_uart_progress(wire, old.TOKEN, prepared, {}, Path(directory)/'log', path)
                result = json.loads(path.read_text())
            self.assertEqual(accepted, complete and protected)
            self.assertEqual(result['normal_recovery'] is not None, protected)
            self.assertEqual(result['diagnostic_ok'], complete)
            self.assertEqual(len(wire.writes), 1); self.assertFalse(result['reboot_requested'])

    def test_full_wire_load_crc_literal_then_single_stimulus_passive_unknown(self):
        class Session(old.fixtures.Session):
            def line(self, text, interrupt=True):
                super().line(text, interrupt)
                if text.startswith('bootm'): self.chunks = [bc.ENTRY, BOOT + old.READY, bc.WAKE, old.record(0), old.record(1), AFTER, THIRD]
            def write(self, data): self.writes.append(data)
            def command(self, text, timeout):
                if text == 'printenv bootargs':
                    self.writes.append(text.encode()); return (ARGS + '\nK230# ').encode()
                return super().command(text, timeout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle = root/'bundle'; bundle.mkdir(); (bundle/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p = {'bundle': bundle, 'system': old.fixtures.SYSTEM, 'normal': old.fixtures.normal(), 'helper_text': 'pass\n',
                 'manifest': {'files': {name: {'bytes': 123, 'crc32': 'abcdef01'} for name, _, _, _ in trial.LOADS}}}
            session = Session(); original = trial.observe_uart_progress
            def fast(active, token, args, **kwargs): return original(active, token, args, timeout=5, readiness_timeout=3, clock=old.Clock(), **kwargs)
            with mock.patch.object(trial, 'prepare_trial', return_value=p), mock.patch.object(trial, 'inspect_shell_initrd', return_value={'bash': old.fixtures.BASH}), mock.patch.object(trial, 'inspect_uart_progress_kernel', return_value={'config_sha256': 'fixture'}), mock.patch.object(trial, 'inspect_uart_breadcrumb_kernel', return_value={'worker_sha256': 'fixture'}), mock.patch.object(trial, 'LOCK_PATH', root/'lock'), mock.patch.object(trial, 'PrivateSession', return_value=session), mock.patch.object(trial, 'observe_uart_progress', side_effect=fast), mock.patch.dict(sys.modules, {'serial': mock.Mock()}):
                self.assertFalse(trial.run_trial(root/'m', root/'l', root/'r', 'minimal', bundle, root/'n', **SELECT))
            result = json.loads((root/'r').read_text()); self.assertTrue(result['uart_progress_post_sample'])
            self.assertTrue(result['probe']['post_sample_complete']); self.assertFalse(result['diagnostic_ok'])
            self.assertIsNone(result['normal_recovery']); self.assertFalse(result['reboot_requested'])
            boot = next(i for i, w in enumerate(session.writes) if w.startswith(b'bootm'))
            self.assertEqual(len(session.writes[boot+1:]), 1); self.assertIn(b'K230_RDINIT_RX', session.writes[-1])
            self.assertEqual(sum(w.startswith(b'ext4load') for w in session.writes), 5)
            self.assertEqual(sum(w.startswith(b'crc32') for w in session.writes), 5)
            self.assertIn(trial.shell_pid1_transport(ARGS, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True, uart_progress_post_sample=True).encode(), session.writes)


if __name__ == '__main__': unittest.main()
