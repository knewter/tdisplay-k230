"""Zero-candidate-input policy fixtures using the real rolling serial pump."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('memory_no_stimulus_fixtures', ROOT/'tests/test_mainline_uart_progress_memory_controller.py')
memory = importlib.util.module_from_spec(spec); spec.loader.exec_module(memory)
old, trial = memory.old, memory.trial
SELECT = memory.SELECT | {'uart_progress_memory_no_stimulus': True}


class PassiveWire(old.Wire):
    def write(self, data):
        self.writes.append(data)
        raise AssertionError('candidate input forbidden')


def observe(wire):
    return trial.observe_uart_progress(wire, old.TOKEN, memory.ARGS, timeout=5, readiness_timeout=3,
                                      clock=old.Clock(), uart_progress_memory=True,
                                      uart_progress_memory_no_stimulus=True)


class NoStimulusTests(unittest.TestCase):
    def assert_passive(self, result, wire):
        self.assertEqual(wire.writes, [])
        self.assertEqual(result['stimulus_attempts'], 0)
        self.assertEqual(result['receipt_status'], 'NOT_REQUESTED')
        self.assertFalse(result['receipt_observed'])
        self.assertEqual(result['rx_status'], 'NOT_TESTED')
        self.assertFalse(result['reboot_requested'])

    def test_real_pump_split_ready_and_summary_zero_input(self):
        row = memory.summary()
        wire = PassiveWire([memory.BOOT[:25], memory.BOOT[25:]+old.READY[:50], old.READY[50:], row[:14], row[14:]])
        result = observe(wire); self.assert_passive(result, wire)
        self.assertTrue(result['readiness_observed']); self.assertTrue(result['memory_summary_valid'])
        self.assertTrue(result['memory_summary']['worker_completed'])
        self.assertFalse(result['memory_summary']['observed_after_stimulus'])

    def test_same_chunk_CRLF_and_observed_readiness_latched_without_input(self):
        for first in (memory.BOOT+old.READY+memory.summary(), (memory.BOOT+old.READY+memory.summary()).replace(b'\n',b'\r\n')):
            wire=PassiveWire([first,b'\nunrelated later status\n']); result=observe(wire)
            self.assert_passive(result,wire); self.assertTrue(result['readiness_observed'])
            self.assertTrue(result['primary_prompt_observed']); self.assertTrue(result['memory_summary_valid'])

    def test_complete_summary_without_prompt_is_separate_observation(self):
        for ready in (b'', b'sh-5.3# ', old.READY.replace(b'sh-5.3# ',b'> ')):
            wire=PassiveWire([memory.BOOT+memory.summary()+ready]); result=observe(wire)
            self.assert_passive(result,wire); self.assertTrue(result['memory_summary_valid'])
            self.assertFalse(result['readiness_observed'])

    def test_missing_and_consistent_incomplete_timeout_summary_independent(self):
        for row in (b'',memory.summary(1,2,3),memory.summary(waited=0)):
            wire=PassiveWire([memory.BOOT+old.READY,row]); result=observe(wire)
            self.assert_passive(result,wire)
            self.assertEqual(result['memory_summary_valid'],bool(row))
            if row: self.assertTrue(result['memory_summary']['wait_timed_out'])
            self.assertEqual(result['capture_timeout_seconds'],5)

    def test_duplicate_truncate_malformed_echo_interleave_embedded_CR_zero_input(self):
        for row,error in ((memory.summary()*2,'duplicate-memory-summary'),
                          (memory.summary()[:-1],'truncated-memory-summary'),
                          (memory.summary(4,4,0x3f),'malformed-memory-summary'),
                          (b"printf '"+memory.summary()[1:]+b"'\n",'malformed-memory-summary'),
                          (memory.summary().replace(b' n=',b' [1.1] printk n='),'malformed-memory-summary'),
                          (memory.summary().replace(b'UMP1',b'UM\rP1'),'malformed-memory-summary')):
            for chunks in ([memory.BOOT+old.READY+row],[memory.BOOT+old.READY,row]):
                wire=PassiveWire(chunks); result=observe(wire); self.assert_passive(result,wire)
                self.assertIn(error,result['protocol_errors']); self.assertFalse(result['memory_summary_valid'])

    def test_stale_wrong_missing_duplicate_args_do_not_trust_summary(self):
        for boot in (b'',old.BANNER,old.BOOT,old.BANNER+memory.CMDLINE*2,memory.BOOT.replace(b'7.3.0-rc5',b'6.6.36')):
            wire=PassiveWire([memory.summary(),boot+old.READY]); wire.buffer=memory.BOOT+old.READY+memory.summary()
            result=observe(wire); self.assert_passive(result,wire)
            self.assertIsNone(result['memory_summary']); self.assertFalse(result['readiness_observed'])

    def test_unsolicited_nonce_receipt_does_not_test_RX(self):
        wire=PassiveWire([memory.BOOT+old.READY, f'\nK230_RDINIT_RX {old.TOKEN}\n'.encode(),memory.summary()])
        result=observe(wire); self.assert_passive(result,wire); self.assertTrue(result['memory_summary_valid'])

    def test_overflow_and_read_error_preserve_zero_input(self):
        wire=PassiveWire([memory.BOOT+old.READY,b'x'*(1048576+1)]); result=observe(wire)
        self.assert_passive(result,wire); self.assertIn('capture-byte-bound',result['protocol_errors'])
        wire=PassiveWire([memory.BOOT+old.READY]); original=wire.port.read
        def read(size):
            if wire.chunks: return original(size)
            raise OSError('fixture serial failure')
        wire.port.read=read; result=observe(wire); self.assert_passive(result,wire)
        self.assertIn('transport-read-unknown',result['protocol_errors'])

    def test_early_normal_is_independent_of_candidate_or_summary(self):
        wire=PassiveWire([old.NORMAL]); result=observe(wire); self.assert_passive(result,wire)
        self.assertTrue(result['normal_prompt_observed']); self.assertFalse(result['candidate_banner'])
        self.assertLess(result['capture_seconds'],5)
        for output in (b'root@nixos:~# ',memory.BOOT+b'nixos login:\nroot@nixos:~# '):
            self.assertFalse(observe(PassiveWire([output]))['normal_prompt_observed'])

    def test_default_memory_keeps_one_stimulus_and_receipt(self):
        wire=old.Wire([memory.BOOT+old.READY,memory.summary()]); result=memory.observe(wire)
        self.assertEqual(wire.writes,[(trial.reception_command(old.TOKEN)+'\r').encode()])
        self.assertTrue(result['receipt_observed']); self.assertNotIn('rx_status',result)
        self.assertNotIn('uart_progress_memory_no_stimulus',result)

    def test_invalid_typed_selector_conflicts_and_modes_before_prepare_or_port(self):
        changes=[{'uart_progress_memory_no_stimulus':v} for v in (1,None,'yes')]
        changes += [{'uart_progress_memory':False},{'uart_progress':False},{'same_image_shell_pid1':False},
                    {'uart_progress_breadcrumbs':True},{'uart_progress_post_sample':True},
                    {'ignore_unused_clocks':True},{'debug_shutdown':True},{'runtime_shutdown_trace':True}]
        for change in changes:
            with mock.patch.object(trial,'prepare_trial') as prep, mock.patch.object(trial,'PrivateSession') as port:
                with self.assertRaises(ValueError): trial.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(SELECT|change))
                prep.assert_not_called(); port.assert_not_called()
        for mode in ('label','survey','root-mount'):
            with mock.patch.object(trial,'prepare_trial') as prep, self.assertRaises(ValueError):
                trial.run_trial(Path('m'),Path('l'),Path('r'),mode,**SELECT)
            prep.assert_not_called()

    def test_CLI_selector_dependencies_and_default_unchanged(self):
        for flags in (['--uart-progress-memory-no-stimulus'],['--same-image-shell-pid1','--uart-progress','--uart-progress-memory-no-stimulus']):
            with mock.patch.object(sys,'argv',['trial',*flags]),mock.patch.object(trial,'run_trial') as run,mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit):trial.main()
                run.assert_not_called()
        for flags,enabled in (([],False),(['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-memory-no-stimulus'],True)):
            with mock.patch.object(sys,'argv',['trial',*flags]),mock.patch.object(trial,'run_trial',return_value=True) as run:
                self.assertEqual(trial.main(),0)
                self.assertEqual(run.call_args.kwargs.get('uart_progress_memory_no_stimulus',False),enabled)

    def test_guarded_normal_return_and_completion_are_independent(self):
        normal=old.fixtures.normal(); normal['trial_from_boot_id']=normal['boot_id']
        after=old.fixtures.Session().run_state('postflight',old.TOKEN)
        cases=((memory.summary(),True,True),(memory.summary(waited=0),True,True),
               (memory.summary(1,2,3),True,False),(b'',True,False),(memory.summary(),False,False))
        for row,protected,accepted in cases:
            wire=PassiveWire([memory.BOOT+old.READY,row,old.NORMAL]); uploads=[]
            wire.upload_text=lambda *args:uploads.append(args)
            wire.run_state=mock.Mock(return_value=after if protected else after|{'kernel':'/wrong'})
            prepared={'bootargs':memory.ARGS,'normal':normal,'helper_text':'fixture','system':old.fixtures.SYSTEM,
                      'bundle':Path('/fixture'),'uart_progress_kernel':{},'uart_progress_memory_kernel':{},
                      'uart_progress_memory_no_stimulus':True}
            original=trial.observe_uart_progress
            def fast(active,token,args,**kwargs):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kwargs)
            with tempfile.TemporaryDirectory() as directory,mock.patch.object(trial,'observe_uart_progress',side_effect=fast):
                path=Path(directory)/'result'; result_ok=trial.finish_uart_progress(wire,old.TOKEN,prepared,{},Path(directory)/'log',path)
                result=json.loads(path.read_text())
            self.assertEqual(result_ok,accepted);self.assertEqual(len(uploads),2)
            self.assertEqual(result['normal_recovery'] is not None,protected);self.assert_passive(result['probe'],wire)

    def test_candidate_normal_looking_prompt_never_authorizes_postflight_writes(self):
        wire=PassiveWire([memory.BOOT+old.READY,memory.summary(),b'\nnixos login:\nroot@nixos:~# '])
        wire.upload_text=mock.Mock(side_effect=AssertionError('candidate upload forbidden'))
        wire.run_state=mock.Mock(side_effect=AssertionError('candidate guard forbidden'))
        prepared={'bootargs':memory.ARGS,'normal':old.fixtures.normal(),'helper_text':'fixture','system':old.fixtures.SYSTEM,
                  'bundle':Path('/fixture'),'uart_progress_kernel':{},'uart_progress_memory_kernel':{},'uart_progress_memory_no_stimulus':True}
        original=trial.observe_uart_progress
        def fast(active,token,args,**kwargs):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kwargs)
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(trial,'observe_uart_progress',side_effect=fast):
            path=Path(directory)/'result';self.assertFalse(trial.finish_uart_progress(wire,old.TOKEN,prepared,{},Path(directory)/'log',path))
        wire.upload_text.assert_not_called();wire.run_state.assert_not_called();self.assertEqual(wire.writes,[])

    def test_full_transport_identical_default_and_zero_bytes_after_boot(self):
        class Session(old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'):self.chunks=[memory.BOOT+old.READY,memory.summary()]
            def write(self,data):self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs':self.writes.append(text.encode());return(memory.ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        transports=[]
        for passive in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);bundle=root/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
                p={'bundle':bundle,'system':old.fixtures.SYSTEM,'normal':old.fixtures.normal(),'helper_text':'pass\n',
                   'manifest':{'files':{name:{'bytes':123,'crc32':'abcdef01'}for name,*_ in trial.LOADS}}}
                session=Session();original=trial.observe_uart_progress
                def fast(active,token,args,**kwargs):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kwargs)
                with mock.patch.object(trial,'prepare_trial',return_value=p),mock.patch.object(trial,'inspect_shell_initrd',return_value={'bash':old.fixtures.BASH}),mock.patch.object(trial,'inspect_uart_progress_kernel',return_value={'config_sha256':'fixture'}),mock.patch.object(trial,'inspect_uart_memory_kernel',return_value={'worker_sha256':'fixture'}),mock.patch.object(trial,'LOCK_PATH',root/'lock'),mock.patch.object(trial,'PrivateSession',return_value=session),mock.patch.object(trial,'observe_uart_progress',side_effect=fast),mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                    self.assertFalse(trial.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',**(memory.SELECT|({'uart_progress_memory_no_stimulus':True}if passive else{}))))
                result=json.loads((root/'r').read_text());boot=next(i for i,w in enumerate(session.writes)if w.startswith(b'bootm'))
                self.assertEqual(len(session.writes[boot+1:]),0 if passive else 1)
                self.assertEqual(sum(w.startswith(b'ext4load')for w in session.writes),5)
                self.assertEqual(sum(w.startswith(b'crc32')for w in session.writes),5)
                transports.append([w for w in session.writes if w.startswith(b'setenv bootargs') or w.startswith(b'bootm')])
                if passive:self.assertEqual(result['probe']['receipt_status'],'NOT_REQUESTED');self.assertEqual(result['rx_status'],'NOT_TESTED')
        self.assertEqual(transports[0],transports[1])


if __name__=='__main__':unittest.main()
