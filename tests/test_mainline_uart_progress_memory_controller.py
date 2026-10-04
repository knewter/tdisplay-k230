"""Host-only exact summary, real-pump, qualification and transport fixtures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('memory_progress_fixtures', ROOT/'tests/test_mainline_uart_progress_controller.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
trial = old.trial
ARGS = old.ARGS + ' ' + trial.UART_PROGRESS_MEMORY_FLAG
CMDLINE = ('[    0.2] Kernel command line: ' + ARGS.removeprefix('bootargs=') + '\n').encode()
BOOT = old.BANNER + CMDLINE
SELECT = dict(same_image_shell_pid1=True, uart_progress=True, uart_progress_memory=True)


def summary(stage=4, index=5, mask=0x3f, last=None, waited=None):
    if last is None: last = mask.bit_length()-1 if mask else 6
    if waited is None: waited = int(stage in (4, 5, 6))
    return f'\nK230_UMP1 s={stage} n={index} m={mask:02x} l={last} w={waited}\n'.encode()


def observe(wire):
    return trial.observe_uart_progress(wire, old.TOKEN, ARGS, timeout=5, readiness_timeout=3,
                                      clock=old.Clock(), uart_progress_memory=True)


class MemoryControllerTests(unittest.TestCase):
    def test_all_exact_stages_and_masks_with_independent_timeout_races(self):
        rows = [summary(0, 6, 0), summary(6, 6, 0), summary()]
        for stage in (1, 2, 3, 5):
            for n in range(6): rows.append(summary(stage, n, (1 << (n + int(stage == 3)))-1))
        for line in rows:
            with self.subTest(line=line):
                result = trial.uart_memory_summary(line[1:]); self.assertIsNotNone(result)
                self.assertEqual(result['worker_completed'], result['stage'] == 4)
        for stage, n, mask in ((4, 5, 0x3f), (5, 1, 1), (6, 6, 0)):
            result = trial.uart_memory_summary(summary(stage, n, mask, waited=0)[1:])
            self.assertTrue(result['wait_timed_out']); self.assertFalse(result['completion_wait_satisfied'])

    def test_literal_version_case_width_extra_echo_and_insertions_reject(self):
        good = summary()[1:]
        for bad in (good[:-1], good+good, good.replace(b'UMP1', b'UMP2'), good.replace(b'm=3f', b'm=3F'),
                    good.replace(b's=4', b's=04'), good.replace(b'm=3f', b'm=03f'),
                    good.replace(b'w=1', b'w=2'), good.replace(b'\n', b' extra=1\n'),
                    b"printf '"+good+b"'", good.replace(b' n=', b' [1.2] printk n=')):
            with self.subTest(bad=bad): self.assertIsNone(trial.uart_memory_summary(bad))

    def test_inconsistent_stage_index_mask_last_or_wait_reject(self):
        for line in (summary(0, 0, 0), summary(6, 6, 1), summary(1, 6, 0), summary(2, 2, 2),
                     summary(3, 1, 1), summary(4, 4, 0x3f), summary(4, 5, 0x1f),
                     summary(5, 1, 0), summary(4, 5, 0x3f, last=4), summary(0, 6, 0, last=0),
                     summary(3, 5, 0x3f, waited=1), summary(1, 0, 0, waited=1), summary(4, 5, 0xff)):
            with self.subTest(line=line): self.assertIsNone(trial.uart_memory_summary(line[1:]))

    def test_real_pump_split_summary_and_one_fresh_stimulus(self):
        row = summary(); wire = old.Wire([BOOT[:30], BOOT[30:] + old.READY, row[:11], row[11:]])
        result = observe(wire)
        self.assertTrue(result['memory_summary_valid']); self.assertTrue(result['memory_summary']['worker_completed'])
        self.assertTrue(result['receipt_observed']); self.assertEqual(result['records'], [])
        self.assertEqual(wire.writes, [(trial.reception_command(old.TOKEN)+'\r').encode()])
        self.assertFalse(result['reboot_requested'])

    def test_same_chunk_prompt_summary_CRLF_and_embedded_CR_boundaries(self):
        for output in (BOOT+old.READY+summary(), (BOOT+old.READY+summary()).replace(b'\n', b'\r\n')):
            result = observe(old.Wire([output])); self.assertTrue(result['memory_summary_valid'])
            self.assertTrue(result['readiness_observed']); self.assertEqual(result['stimulus_attempts'], 1)
            self.assertFalse(result['memory_summary']['observed_after_stimulus'])
        for bad in (summary().replace(b'UMP1', b'UM\rP1'), summary().replace(b'm=3f', b'm=3\rf')):
            wire = old.Wire([BOOT+old.READY+bad]); result = observe(wire)
            self.assertIn('malformed-memory-summary', result['protocol_errors'])
            self.assertFalse(result['memory_summary_valid']); self.assertEqual(wire.writes, [])

    def test_duplicate_echo_interleave_or_bad_summary_prevents_initial_stimulus(self):
        for rows, error in ((summary()+summary(), 'duplicate-memory-summary'),
                            (b"printf '"+summary()[1:]+b"'\n", 'malformed-memory-summary'),
                            (summary().replace(b'n=', b'n=[2.0] printk\n'), 'malformed-memory-summary'),
                            (summary(4, 4, 0x3f), 'malformed-memory-summary')):
            wire = old.Wire([BOOT+rows+old.READY]); result = observe(wire)
            self.assertIn(error, result['protocol_errors']); self.assertFalse(result['memory_summary_valid'])
            self.assertEqual(wire.writes, [])

    def test_late_duplicate_or_truncation_preserves_one_attempt_and_no_reboot(self):
        for rows, error in ((summary()+summary(), 'duplicate-memory-summary'), (summary()[:-1], 'truncated-memory-summary')):
            wire = old.Wire([BOOT+old.READY, rows], reply=False); result = observe(wire)
            self.assertIn(error, result['protocol_errors']); self.assertEqual(len(wire.writes), 1)
            self.assertFalse(result['memory_summary_valid']); self.assertFalse(result['reboot_requested'])

    def test_missing_summary_receipt_and_timeout_remain_independent(self):
        result = observe(old.Wire([BOOT+old.READY]))
        self.assertTrue(result['receipt_observed']); self.assertIsNone(result['memory_summary'])
        self.assertFalse(result['memory_summary_valid'])
        result = observe(old.Wire([BOOT+old.READY, summary(1, 2, 3)], reply=False))
        self.assertTrue(result['memory_summary_valid']); self.assertTrue(result['memory_summary']['wait_timed_out'])
        self.assertFalse(result['memory_summary']['worker_completed']); self.assertFalse(result['receipt_observed'])
        self.assertEqual(result['stimulus_attempts'], 1)

    def test_missing_wrong_duplicate_args_and_stale_buffer_never_trust_summary(self):
        for boot in (b'', old.BANNER, old.BOOT, old.BANNER+CMDLINE+CMDLINE, BOOT.replace(b'7.3.0-rc5', b'6.6.36')):
            wire = old.Wire([summary(), boot+old.READY]); wire.buffer = BOOT+old.READY+summary()
            result = observe(wire); self.assertIsNone(result['memory_summary']); self.assertEqual(wire.writes, [])

    def test_summary_does_not_authorize_input_without_fresh_init_primary_prompt(self):
        for ready in (b'', b'sh-5.3# ', old.READY.replace(b'sh-5.3# ', b'> '),
                      old.READY.replace(b'sh-5.3# ', b"printf 'sh-5.3# '")):
            wire = old.Wire([BOOT+summary()+ready]); result = observe(wire)
            self.assertTrue(result['memory_summary_valid']); self.assertEqual(wire.writes, [])

    def test_unexpected_numeric_or_point_output_invalidates_memory_mode(self):
        for row in (old.record(0), old.record(0).replace(b'UP1', b'U\rP1'), b'\nK230_UPB1 point=worker-entry\n', b'\nK230_UPP1 point=after-n1-write\n'):
            wire = old.Wire([BOOT+row+old.READY]); result = observe(wire)
            self.assertIn('unexpected-worker-output', result['protocol_errors']); self.assertEqual(wire.writes, [])

    def test_independent_normal_return_with_no_candidate_is_not_acceptance(self):
        result = observe(old.Wire([old.NORMAL])); self.assertTrue(result['normal_prompt_observed'])
        self.assertFalse(result['candidate_banner']); self.assertIsNone(result['memory_summary'])
        self.assertEqual(result['stimulus_attempts'], 0); self.assertLess(result['capture_seconds'], 5)

    def test_selector_types_conflicts_and_modes_fail_before_prepare_or_port(self):
        for changes in ({'uart_progress_memory': 1}, {'uart_progress_memory': None}, {'uart_progress': False},
                        {'same_image_shell_pid1': False}, {'uart_progress_breadcrumbs': True},
                        {'uart_progress_breadcrumbs': True, 'uart_progress_post_sample': True},
                        {'debug_shutdown': True}, {'runtime_shutdown_trace': True}, {'ignore_unused_clocks': True}):
            with mock.patch.object(trial,'prepare_trial') as prep, mock.patch.object(trial,'PrivateSession') as port:
                with self.assertRaises(ValueError): trial.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(SELECT|changes))
                prep.assert_not_called(); port.assert_not_called()
        for mode in ('survey','label','root-mount'):
            with mock.patch.object(trial,'prepare_trial') as prep, self.assertRaises(ValueError):
                trial.run_trial(Path('m'),Path('l'),Path('r'),mode,**SELECT)
            prep.assert_not_called()

    def test_CLI_default_compatibility_and_typed_selection(self):
        for flags in (['--uart-progress-memory'], ['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-breadcrumbs']):
            with mock.patch.object(sys,'argv',['trial',*flags]), mock.patch.object(trial,'run_trial') as run, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit): trial.main()
                run.assert_not_called()
        for flags, enabled in (([],False),(['--same-image-shell-pid1','--uart-progress','--uart-progress-memory'],True)):
            with mock.patch.object(sys,'argv',['trial',*flags]), mock.patch.object(trial,'run_trial',return_value=True) as run:
                self.assertEqual(trial.main(),0); self.assertEqual(run.call_args.kwargs.get('uart_progress_memory',False),enabled)

    def test_full_literal_adds_only_memory_gate_and_rejects_unsafe_extras(self):
        cmd = trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True)
        self.assertEqual(cmd,'setenv bootargs "'+ARGS.removeprefix('bootargs=')+'"')
        self.assertEqual(ARGS.split(),old.ARGS.split()+[trial.UART_PROGRESS_MEMORY_FLAG])
        self.assertLess(len(cmd),512); self.assertNotIn('${',cmd)
        for args in (ARGS+' '+trial.UART_PROGRESS_MEMORY_FLAG,ARGS+'\n',ARGS+';saveenv',ARGS.replace('memory=1','memory=0'),ARGS+' '+trial.UART_PROGRESS_BREADCRUMBS_FLAG):
            with self.assertRaises(ValueError): trial.shell_pid1_transport(args,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True)

    def artifact_fixture(self, root):
        source=root/'source'; (source/'drivers/soc/canaan').mkdir(parents=True)
        worker=source/'drivers/soc/canaan/k230-uart-progress.c'; worker.write_bytes(b'reviewed memory worker fixture')
        kernel=root/'kernel'; kernel.mkdir(); image=kernel/'Image'
        image.write_bytes(b'prefix'+trial.UART_MEMORY_FORMAT+b'k230.uart_progress_memory=\0')
        return {'uart_progress_kernel': {'kernel':str(kernel),'derivation':'/nix/store/'+'a'*32+'-kernel.drv'}},source,worker,image

    def test_real_source_query_fixture_requires_same_drv_hash_and_linked_format(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial,'immutable_store_path',side_effect=lambda p,label:p):
            p,source,worker,image=self.artifact_fixture(Path(directory)); digest=hashlib.sha256(worker.read_bytes()).hexdigest(); drv=p['uart_progress_kernel']['derivation']
            for desc in ({drv:{'env':{'src':str(source)}}},{'version':4,'derivations':{Path(drv).name:{'structuredAttrs':{'src':str(source)}}}}):
                with mock.patch.object(trial,'UART_MEMORY_SOURCE_SHA256',digest), mock.patch.object(trial.subprocess,'check_output',return_value=json.dumps(desc)) as query:
                    proof=trial.inspect_uart_memory_kernel(p); self.assertEqual(proof['worker_sha256'],digest)
                    self.assertEqual(proof['summary_format_offset'],6); self.assertEqual(proof['source'],str(source))
                    self.assertEqual(query.call_args.args[0][-1],drv); self.assertIn('--offline',query.call_args.args[0]); self.assertNotIn('build',query.call_args.args[0])

    def test_legacy_source_and_missing_or_duplicate_image_format_gate_reject(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial,'immutable_store_path',side_effect=lambda p,label:p):
            p,source,worker,image=self.artifact_fixture(Path(directory)); digest=hashlib.sha256(worker.read_bytes()).hexdigest(); good=image.read_bytes(); drv=p['uart_progress_kernel']['derivation']
            for failure in ('legacy-source','old-image','duplicate-format','missing-gate','wrong-derivation','unknown-schema'):
                worker.write_bytes(b'legacy worker' if failure=='legacy-source' else b'reviewed memory worker fixture')
                image.write_bytes(b'legacy Image' if failure=='old-image' else good+trial.UART_MEMORY_FORMAT if failure=='duplicate-format' else good.replace(b'k230.uart_progress_memory=\0',b'') if failure=='missing-gate' else good)
                desc={} if failure=='wrong-derivation' else {'version':99,'derivations':{}} if failure=='unknown-schema' else {drv:{'env':{'src':str(source)}}}
                with mock.patch.object(trial,'UART_MEMORY_SOURCE_SHA256',digest), mock.patch.object(trial.subprocess,'check_output',return_value=json.dumps(desc)), self.assertRaises(ValueError): trial.inspect_uart_memory_kernel(p)

    def test_preparation_variant_failure_never_creates_logs_or_serial(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p={'bundle':root,'system':old.fixtures.SYSTEM,'normal':old.fixtures.normal(),'helper_text':'pass'}
            with mock.patch.object(trial,'prepare_trial',return_value=p), mock.patch.object(trial,'inspect_shell_initrd',return_value={'bash':old.fixtures.BASH}), mock.patch.object(trial,'inspect_uart_progress_kernel',return_value={'config_sha256':'fixture'}), mock.patch.object(trial,'inspect_uart_memory_kernel',side_effect=ValueError('legacy source')), mock.patch.object(trial,'PrivateSession') as port:
                with self.assertRaises(ValueError): trial.run_trial(root/'m',root/'l',root/'r','minimal',**SELECT)
                port.assert_not_called(); self.assertFalse((root/'l').exists()); self.assertFalse((root/'r').exists())

    def test_protected_return_requires_worker_completion_receipt_and_normal_guards(self):
        normal=old.fixtures.normal(); normal['trial_from_boot_id']=normal['boot_id']; after=old.fixtures.Session().run_state('postflight',old.TOKEN)
        for complete, receipt, protected, waited in ((False,True,True,0),(True,True,True,1),(True,True,True,0),(True,False,True,1),(True,True,False,1)):
            row=summary(waited=waited) if complete else summary(1,2,3)
            wire=old.Wire([BOOT+old.READY,row,old.NORMAL],reply=receipt)
            wire.upload_text=mock.Mock(); wire.run_state=mock.Mock(return_value=after if protected else after|{'kernel':'/wrong'})
            prepared={'bootargs':ARGS,'normal':normal,'helper_text':'fixture','system':old.fixtures.SYSTEM,'bundle':Path('/fixture'),'uart_progress_kernel':{},'uart_progress_memory_kernel':{}}
            original=trial.observe_uart_progress
            def fast(active,token,args,**kwargs): return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kwargs)
            with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial,'observe_uart_progress',side_effect=fast):
                path=Path(directory)/'result'; accepted=trial.finish_uart_progress(wire,old.TOKEN,prepared,{},Path(directory)/'log',path); result=json.loads(path.read_text())
            self.assertEqual(accepted,complete and receipt and protected)
            self.assertEqual(result['diagnostic_ok'],complete and receipt)
            self.assertEqual(result['normal_recovery'] is not None,protected)
            self.assertEqual(len(wire.writes),1); self.assertFalse(result['reboot_requested'])

    def test_full_wire_load_crc_printed_policy_and_one_stimulus_passive_unknown(self):
        class Session(old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'): self.chunks=[BOOT+old.READY,summary()]
            def write(self,data): self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs': self.writes.append(text.encode()); return (ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); bundle=root/'bundle'; bundle.mkdir(); (bundle/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p={'bundle':bundle,'system':old.fixtures.SYSTEM,'normal':old.fixtures.normal(),'helper_text':'pass\n','manifest':{'files':{name:{'bytes':123,'crc32':'abcdef01'} for name,*_ in trial.LOADS}}}
            session=Session(); original=trial.observe_uart_progress
            def fast(active,token,args,**kwargs): return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kwargs)
            with mock.patch.object(trial,'prepare_trial',return_value=p), mock.patch.object(trial,'inspect_shell_initrd',return_value={'bash':old.fixtures.BASH}), mock.patch.object(trial,'inspect_uart_progress_kernel',return_value={'config_sha256':'fixture'}), mock.patch.object(trial,'inspect_uart_memory_kernel',return_value={'worker_sha256':'fixture'}), mock.patch.object(trial,'LOCK_PATH',root/'lock'), mock.patch.object(trial,'PrivateSession',return_value=session), mock.patch.object(trial,'observe_uart_progress',side_effect=fast), mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                self.assertFalse(trial.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',**SELECT))
            result=json.loads((root/'r').read_text()); self.assertTrue(result['uart_progress_memory'])
            self.assertTrue(result['probe']['memory_summary_valid']); self.assertFalse(result['diagnostic_ok'])
            self.assertIsNone(result['normal_recovery']); self.assertFalse(result['reboot_requested'])
            boot=next(i for i,w in enumerate(session.writes) if w.startswith(b'bootm'))
            self.assertEqual(len(session.writes[boot+1:]),1); self.assertIn(b'K230_RDINIT_RX',session.writes[-1])
            self.assertEqual(sum(w.startswith(b'ext4load') for w in session.writes),5); self.assertEqual(sum(w.startswith(b'crc32') for w in session.writes),5)
            self.assertIn(trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True).encode(),session.writes)


if __name__=='__main__': unittest.main()
