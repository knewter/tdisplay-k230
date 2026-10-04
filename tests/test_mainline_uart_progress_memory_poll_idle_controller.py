"""Host-only same-image polling policy/qualification and zero-input wire proof."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('poll_idle_fixtures',ROOT/'tests/test_mainline_uart_progress_memory_no_stimulus_controller.py')
passive=importlib.util.module_from_spec(spec);spec.loader.exec_module(passive)
memory,old,trial=passive.memory,passive.old,passive.trial
ARGS=memory.ARGS+' nohlt'
BOOT=old.BANNER+('[    0.2] Kernel command line: '+ARGS.removeprefix('bootargs=')+'\n').encode()
SELECT=passive.SELECT|{'uart_progress_memory_poll_idle':True}


def observe(wire):
    return trial.observe_uart_progress(wire,old.TOKEN,ARGS,timeout=5,readiness_timeout=3,
                                      clock=old.Clock(),uart_progress_memory=True,
                                      uart_progress_memory_no_stimulus=True)


def artifact(root):
    config=root/'config';config.write_bytes(b'CONFIG_GENERIC_IDLE_POLL_SETUP=y\n')
    kernel=root/'kernel';kernel.mkdir();image=kernel/'Image';image.write_bytes(b'prefix-nohlt\0suffix')
    return {'bootargs':memory.ARGS,'transport':trial.shell_pid1_transport(memory.ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True),
            'system':old.fixtures.SYSTEM,'uart_progress_memory_no_stimulus':True,
            'uart_progress_kernel':{'kernel':str(kernel),'config':str(config),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest()},
            'uart_progress_memory_kernel':{'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}},config,image


class PollIdleTests(unittest.TestCase):
    def test_pure_qualification_exact_one_bare_token_without_mutating_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            p,config,image=artifact(Path(directory));original=dict(p);q=trial.prepare_uart_memory_poll_idle(p)
            self.assertEqual(p,original);self.assertEqual(q['bootargs'],ARGS)
            self.assertEqual(q['bootargs'].split(),memory.ARGS.split()+['nohlt'])
            self.assertEqual(q['transport'],'setenv bootargs "'+ARGS.removeprefix('bootargs=')+'"')
            self.assertEqual(len(q['transport'].encode())-len(p['transport'].encode()),6)
            self.assertEqual(q['uart_progress_kernel'],p['uart_progress_kernel'])
            self.assertEqual(q['uart_progress_memory_kernel'],p['uart_progress_memory_kernel'])
            self.assertEqual(q['uart_progress_memory_poll_idle_kernel']['generic_idle_poll_setup'],'y')
            self.assertEqual(q['uart_progress_memory_poll_idle_kernel']['linked_nohlt_setup_offset'],7)

    def test_actual_config_hash_and_builtin_single_definition_required(self):
        for raw,mismatch in ((b'',False),(b'# CONFIG_GENERIC_IDLE_POLL_SETUP is not set\n',False),
                             (b'CONFIG_GENERIC_IDLE_POLL_SETUP=m\n',False),(b'CONFIG_GENERIC_IDLE_POLL_SETUP=y\n'*2,False),
                             (b'CONFIG_GENERIC_IDLE_POLL_SETUP=y\n',True)):
            with tempfile.TemporaryDirectory() as directory:
                p,config,image=artifact(Path(directory));config.write_bytes(raw)
                if not mismatch:p['uart_progress_kernel']['config_sha256']=hashlib.sha256(raw).hexdigest()
                else:p['uart_progress_kernel']['config_sha256']='0'*64
                with self.assertRaises(ValueError):trial.prepare_uart_memory_poll_idle(p)

    def test_missing_duplicate_linked_setup_and_different_Image_fail_closed(self):
        for raw,mismatch in ((b'nohlt',False),(b'nohlt=\0',False),(b'nohlt\0'*2,False),(b'nohlt\0',True)):
            with tempfile.TemporaryDirectory() as directory:
                p,config,image=artifact(Path(directory));image.write_bytes(raw)
                if not mismatch:p['uart_progress_memory_kernel']['image_sha256']=hashlib.sha256(raw).hexdigest()
                with self.assertRaises(ValueError):trial.prepare_uart_memory_poll_idle(p)

    def test_previous_hlt_nohlt_value_duplicate_and_arbitrary_args_rejected(self):
        for suffix in (' nohlt',' nohlt=0',' nohlt=1',' hlt',' hlt=0',' cpuidle.off=1',';saveenv','\n'):
            with tempfile.TemporaryDirectory() as directory:
                p,_,_=artifact(Path(directory));p['bootargs']+=suffix
                with self.assertRaises(ValueError):trial.prepare_uart_memory_poll_idle(p)
        with tempfile.TemporaryDirectory() as directory:
            p,_,_=artifact(Path(directory));p['transport']='setenv bootargs unsafe'
            with self.assertRaises(ValueError):trial.prepare_uart_memory_poll_idle(p)

    def test_transport_exact_policy_and_legacy_default_outputs(self):
        for args,kw in ((memory.ARGS,{'uart_progress':True,'uart_progress_memory':True}),
                        (old.ARGS,{'uart_progress':True}),
                        (trial.shell_pid1_bootargs(old.fixtures.ORIGINAL,old.fixtures.SYSTEM),{})):
            self.assertEqual(trial.shell_pid1_transport(args,old.fixtures.SYSTEM,**kw),'setenv bootargs "'+args.removeprefix('bootargs=')+'"')
        cmd=trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_poll_idle=True)
        self.assertEqual(cmd,'setenv bootargs "'+ARGS.removeprefix('bootargs=')+'"')
        for args in (ARGS+' nohlt',ARGS.replace(' nohlt',' nohlt=0'),ARGS.replace(' nohlt',' hlt'),ARGS+';saveenv',ARGS+'\n',ARGS+' "',ARGS+' $x',ARGS+' '+memory.trial.UART_PROGRESS_MEMORY_FLAG):
            with self.assertRaises(ValueError):trial.shell_pid1_transport(args,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_poll_idle=True)
        for args,kw in ((memory.ARGS,{'uart_progress_memory_poll_idle':True}),(ARGS,{'uart_progress':True,'uart_progress_memory':True}),(ARGS,{'uart_progress':True,'uart_progress_memory':True,'uart_progress_memory_poll_idle':1})):
            with self.assertRaises(ValueError):trial.shell_pid1_transport(args,old.fixtures.SYSTEM,**kw)

    def test_typed_dependencies_modes_conflicts_fail_before_prepare_and_open(self):
        changes=[{'uart_progress_memory_poll_idle':v}for v in (1,None,'yes')]
        changes += [{k:False}for k in ('same_image_shell_pid1','uart_progress','uart_progress_memory','uart_progress_memory_no_stimulus')]
        changes += [{k:True}for k in ('uart_progress_breadcrumbs','uart_progress_post_sample','debug_shutdown','runtime_shutdown_trace','ignore_unused_clocks')]
        for change in changes:
            with mock.patch.object(trial,'prepare_trial')as prep,mock.patch.object(trial,'PrivateSession')as port:
                with self.assertRaises(ValueError):trial.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(SELECT|change))
                prep.assert_not_called();port.assert_not_called()
        for mode in ('survey','label','root-mount'):
            with mock.patch.object(trial,'prepare_trial')as prep,self.assertRaises(ValueError):trial.run_trial(Path('m'),Path('l'),Path('r'),mode,**SELECT)
            prep.assert_not_called()

    def test_CLI_defaults_and_full_dependencies(self):
        for flags in (['--uart-progress-memory-poll-idle'],['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-memory-poll-idle']):
            with mock.patch.object(sys,'argv',['trial',*flags]),mock.patch.object(trial,'run_trial')as run,mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit):trial.main()
                run.assert_not_called()
        flags=['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-memory-no-stimulus','--uart-progress-memory-poll-idle']
        for argv,enabled in (([],False),(flags,True)):
            with mock.patch.object(sys,'argv',['trial',*argv]),mock.patch.object(trial,'run_trial',return_value=True)as run:
                self.assertEqual(trial.main(),0);self.assertEqual(run.call_args.kwargs.get('uart_progress_memory_poll_idle',False),enabled)

    def test_real_pump_split_prompt_summary_no_candidate_input(self):
        row=memory.summary();wire=passive.PassiveWire([BOOT[:25],BOOT[25:]+old.READY,row[:16],row[16:]])
        result=observe(wire);self.assertEqual(wire.writes,[]);self.assertTrue(result['memory_summary_valid'])
        self.assertEqual(result['receipt_status'],'NOT_REQUESTED');self.assertEqual(result['rx_status'],'NOT_TESTED')
        self.assertEqual(result['stimulus_attempts'],0);self.assertTrue(result['kernel_args_verified'])
        self.assertFalse(result['reboot_requested'])

    def test_missing_wrong_duplicate_args_and_stale_cannot_trust_summary(self):
        for boot in (b'',old.BANNER,memory.BOOT,BOOT.replace(b' nohlt',b' nohlt=0'),BOOT+BOOT.split(b'\n',1)[1]):
            wire=passive.PassiveWire([boot+old.READY,memory.summary()]);wire.buffer=BOOT+old.READY+memory.summary()
            result=observe(wire);self.assertEqual(wire.writes,[]);self.assertIsNone(result['memory_summary'])
            self.assertFalse(result['readiness_observed'])

    def test_strict_summary_malformed_duplicate_truncated_and_unavailable(self):
        for row,error in ((memory.summary()*2,'duplicate-memory-summary'),(memory.summary()[:-1],'truncated-memory-summary'),
                          (memory.summary().replace(b'm=3f',b'm=3F'),'malformed-memory-summary'),
                          (memory.summary().replace(b'UMP1',b'UM\rP1'),'malformed-memory-summary')):
            wire=passive.PassiveWire([BOOT+old.READY,row]);result=observe(wire)
            self.assertEqual(wire.writes,[]);self.assertIn(error,result['protocol_errors']);self.assertFalse(result['memory_summary_valid'])
        for row in (b'',memory.summary(1,2,3)):
            wire=passive.PassiveWire([BOOT+old.READY,row]);result=observe(wire);self.assertEqual(wire.writes,[])
            self.assertEqual(result['memory_summary_valid'],bool(row));self.assertFalse(result['reboot_requested'])

    def test_no_prompt_read_error_overflow_timeout_remain_passive(self):
        for chunks in ([BOOT+memory.summary()],[BOOT+old.READY,b'x'*(1048576+1)],[BOOT+old.READY]):
            wire=passive.PassiveWire(chunks);result=observe(wire);self.assertEqual(wire.writes,[])
            self.assertEqual(result['stimulus_attempts'],0);self.assertEqual(result['receipt_status'],'NOT_REQUESTED')
        wire=passive.PassiveWire([BOOT+old.READY]);read=wire.port.read
        def failing(size):
            if wire.chunks:return read(size)
            raise OSError('fixture')
        wire.port.read=failing;result=observe(wire);self.assertIn('transport-read-unknown',result['protocol_errors']);self.assertEqual(wire.writes,[])

    def test_preopen_unsupported_real_config_proof_no_logs_or_port(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);p,config,image=artifact(root);config.write_bytes(b'CONFIG_GENERIC_IDLE_POLL_SETUP=n\n');p['uart_progress_kernel']['config_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
            with mock.patch.object(trial,'prepare_trial',return_value=p),mock.patch.object(trial,'prepare_uart_progress',side_effect=lambda value,**kw:value),mock.patch.object(trial,'PrivateSession')as port:
                with self.assertRaises(ValueError):trial.run_trial(root/'m',root/'l',root/'r','minimal',**SELECT)
                port.assert_not_called();self.assertFalse((root/'l').exists());self.assertFalse((root/'r').exists())

    def test_full_wire_real_poll_qualifier_five_loads_CRCS_zero_input_after_boot(self):
        class Session(old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'):self.chunks=[BOOT+old.READY,memory.summary()]
            def write(self,data):self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs':self.writes.append(text.encode());return(ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);p,_,_=artifact(root);bundle=root/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p.update(bundle=bundle,normal=old.fixtures.normal(),helper_text='pass\n',manifest={'files':{name:{'bytes':123,'crc32':'abcdef01'}for name,*_ in trial.LOADS}})
            session=Session();original=trial.observe_uart_progress
            def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kw)
            with mock.patch.object(trial,'prepare_trial',return_value=p),mock.patch.object(trial,'inspect_shell_initrd',return_value={'bash':old.fixtures.BASH}),mock.patch.object(trial,'inspect_uart_progress_kernel',return_value=p['uart_progress_kernel']),mock.patch.object(trial,'inspect_uart_memory_kernel',return_value=p['uart_progress_memory_kernel']),mock.patch.object(trial,'LOCK_PATH',root/'lock'),mock.patch.object(trial,'PrivateSession',return_value=session),mock.patch.object(trial,'observe_uart_progress',side_effect=fast),mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                self.assertFalse(trial.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',**SELECT))
            result=json.loads((root/'r').read_text());boot=next(i for i,w in enumerate(session.writes)if w.startswith(b'bootm'))
            self.assertEqual(session.writes[boot+1:],[]);self.assertEqual(result['rx_status'],'NOT_TESTED')
            self.assertTrue(result['uart_progress_memory_poll_idle']);self.assertTrue(result['probe']['memory_summary_valid'])
            self.assertEqual(sum(w.startswith(b'ext4load')for w in session.writes),5)
            self.assertEqual(sum(w.startswith(b'crc32')for w in session.writes),5)
            self.assertIn(trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_poll_idle=True).encode(),session.writes)

    def test_protected_return_independent_and_missing_poll_proof_before_capture(self):
        normal=old.fixtures.normal();normal['trial_from_boot_id']=normal['boot_id'];after=old.fixtures.Session().run_state('postflight',old.TOKEN)
        for row,protected in ((memory.summary(),True),(memory.summary(1,2,3),True),(memory.summary(),False)):
            wire=passive.PassiveWire([BOOT+old.READY,row,old.NORMAL]);wire.upload_text=mock.Mock();wire.run_state=mock.Mock(return_value=after if protected else after|{'kernel':'/wrong'})
            p={'bootargs':ARGS,'normal':normal,'helper_text':'fixture','system':old.fixtures.SYSTEM,'bundle':Path('/fixture'),
               'uart_progress_kernel':{},'uart_progress_memory_kernel':{},'uart_progress_memory_no_stimulus':True,
               'uart_progress_memory_poll_idle':True,'uart_progress_memory_poll_idle_kernel':{}}
            original=trial.observe_uart_progress
            def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kw)
            with tempfile.TemporaryDirectory()as directory,mock.patch.object(trial,'observe_uart_progress',side_effect=fast):
                path=Path(directory)/'result';accepted=trial.finish_uart_progress(wire,old.TOKEN,p,{},Path(directory)/'log',path);result=json.loads(path.read_text())
            self.assertEqual(accepted,protected and row==memory.summary());self.assertEqual(wire.writes,[])
            self.assertEqual(result['normal_recovery']is not None,protected);self.assertEqual(wire.upload_text.call_count,2)
        del p['uart_progress_memory_poll_idle_kernel']
        with mock.patch.object(trial,'observe_uart_progress')as capture,self.assertRaises(ValueError):trial.finish_uart_progress(wire,old.TOKEN,p,{},Path('l'),Path('r'))
        capture.assert_not_called()


if __name__=='__main__':unittest.main()
