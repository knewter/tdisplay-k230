"""MemoryPrintk strict channel/backend and passive transport fixtures."""
import importlib.util
import hashlib
import json
import sys
import tempfile
from unittest import mock
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('memory_printk_fixtures',ROOT/'tests/test_mainline_uart_progress_memory_no_stimulus_controller.py')
passive=importlib.util.module_from_spec(spec);spec.loader.exec_module(passive)
memory,old,trial=passive.memory,passive.old,passive.trial
ARGS=memory.ARGS+' '+trial.UART_MEMORY_PRINTK_FLAG
BANNER=b'[    0.100000] Linux version 7.3.0-rc5 candidate\n'
CMDLINE=('[    0.200000] Kernel command line: '+ARGS.removeprefix('bootargs=')+'\n').encode()
REG=b'[    2.402787] 91400000.serial: ttyS0 MMIO32:0x0000000091400000 (irq = 12, base_baud = 3125000) is a 16550A\n'
ENABLE=b'[    2.403113] printk: console [ttyS0] enabled\n'
BOOT=BANNER+CMDLINE+REG+ENABLE
READY=old.READY.replace(b'[    4.1]',b'[    4.549880]')


def summary(*args,**kwargs):
    return b'[   45.123456] '+memory.summary(*args,**kwargs)[1:].replace(b'K230_UMP1',b'K230_UMK1')


def observe(wire):
    return trial.observe_uart_progress(wire,old.TOKEN,ARGS,timeout=5,readiness_timeout=3,
                                      clock=old.Clock(),uart_progress_memory=True,
                                      uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True)


class MemoryPrintkControllerTests(unittest.TestCase):
    def test_all_state_rules_and_six_decimal_timestamp(self):
        for stage,n,mask in ((0,6,0),(1,2,3),(2,2,3),(3,2,7),(4,5,63),(5,0,0),(6,6,0)):
            row=summary(stage,n,mask);result=trial.uart_memory_printk_summary(row)
            self.assertEqual(result['stage'],stage);self.assertEqual(result['kernel_timestamp_ns'],45123456000)
        for line in (summary().replace(b'45.123456',b'45.12345'),summary().replace(b'45.123456',b'45.1234567'),
                     summary().replace(b'[   45',b'[45'),summary().replace(b'[   45',b'[  045'),
                     summary().replace(b'] ',b'] [T123] '),summary().replace(b'] ',b'] [CPU0] '),
                     b'\x1b[0m'+summary(),b'prefix '+summary(),summary().replace(b'UMK1',b'UMP1'),
                     summary().replace(b'm=3f',b'm=3F'),summary(4,4,63),summary()[:-1]):
            with self.subTest(line=line):self.assertIsNone(trial.uart_memory_printk_summary(line))

    def test_unique_ordered_exact_UART0_backend(self):
        result=trial.linux_console_backend(REG+ENABLE);self.assertEqual(result['status'],'MATCHED')
        self.assertEqual(result['irq'],12);self.assertEqual(result['base_baud'],3125000)
        for text,status in ((REG,'UNKNOWN'),(ENABLE,'UNKNOWN'),(ENABLE+REG,'MISMATCH'),(REG*2+ENABLE,'DUPLICATE'),
                            (REG+ENABLE*2,'DUPLICATE'),(REG.replace(b'91400000.serial',b'91401000.serial')+ENABLE,'MISMATCH'),
                            (REG.replace(b'91400000 (',b'91401000 (')+ENABLE,'MISMATCH'),(REG.replace(b'irq = 12',b'irq = 0')+ENABLE,'MISMATCH'),
                            (REG.replace(b'irq = 12',b'irq = 4294967296')+ENABLE,'MISMATCH'),
                            (REG.replace(b'base_baud = 3125000',b'base_baud = '+b'9'*5000)+ENABLE,'MISMATCH'),
                            (REG+ENABLE+b'[    2.500000] printk: console [tty0] enabled\n','MISMATCH'),
                            (b"printf '"+REG+b"'\n"+ENABLE,'UNKNOWN')):
            with self.subTest(text=text):self.assertEqual(trial.linux_console_backend(text)['status'],status)
        for text in (b'corrupt\r'+REG+ENABLE,REG+b'corrupt\r'+ENABLE):
            self.assertNotEqual(trial.linux_console_backend(text)['status'],'MATCHED')
        for bad in (REG[:-1],REG.replace(b'ttyS0',b'tty\rS0'),REG.replace(b'2.402787',b'2.40278')):
            self.assertNotEqual(trial.linux_console_backend(bad+ENABLE)['status'],'MATCHED')

    def test_actual_printk_blank_prefix_separates_prompt_without_repair(self):
        # One pr_info("\nK230_UMK1 ...\n") renders a blank timestamped
        # line after the existing prompt, then the clean summary line.
        wire=passive.PassiveWire([BOOT+READY+b'[   45.123456] \n'+summary()])
        result=observe(wire);self.assertEqual(wire.writes,[])
        self.assertTrue(result['primary_prompt_observed']);self.assertTrue(result['readiness_observed'])
        self.assertTrue(result['memory_summary_valid']);self.assertEqual(result['summary_channel'],'linux-printk')
        self.assertEqual(result['receipt_status'],'NOT_REQUESTED');self.assertEqual(result['rx_status'],'NOT_TESTED')

    def test_observed_bracketed_paste_prompt_at_end_split_and_CRLF(self):
        enabled=READY.replace(b'sh-5.3# ',b'\x1b[?2004hsh-5.3# ')
        data=BOOT+enabled
        for chunks in ([data],[data[:-9],data[-9:-3],data[-3:]],
                       [data.replace(b'\n',b'\r\n')],
                       [(BOOT+enabled+b'\n'+summary()).replace(b'\n',b'\r\n')]):
            wire=passive.PassiveWire(chunks);result=observe(wire)
            self.assertTrue(result['primary_prompt_observed']);self.assertTrue(result['readiness_observed'])
            self.assertEqual(wire.writes,[]);self.assertEqual(result['stimulus_attempts'],0)
            self.assertEqual(result['receipt_status'],'NOT_REQUESTED');self.assertEqual(result['rx_status'],'NOT_TESTED')
        wire=passive.PassiveWire([BOOT+enabled[:-1]]);result=observe(wire)
        self.assertFalse(result['primary_prompt_observed']);self.assertEqual(wire.writes,[])

    def test_prompt_prefix_never_accepts_other_ANSI_echo_or_embedded_CR(self):
        for prefix in (b'\x1b[0m',b'\x1b[?2004l',b'\x1b[?2004h\x1b[0m',b'\x1b[?2004h\x1b[?2004h',
                       b'\x1b[?200\r4h',b'corrupt\r\x1b[?2004h',b"printf '"):
            wire=passive.PassiveWire([BOOT+READY.replace(b'sh-5.3# ',prefix+b'sh-5.3# ')])
            result=observe(wire);self.assertFalse(result['primary_prompt_observed'])
            self.assertFalse(result['readiness_observed']);self.assertEqual(wire.writes,[])
        for prompt in (b'\x1b[?2004hsh-5.\r3# ',b'\x1b[?2004hsh-5.3# \r',
                       b'\x1b[?2004hsh-5.3# \x1b[0m'):
            wire=passive.PassiveWire([BOOT+READY.replace(b'sh-5.3# ',prompt)])
            result=observe(wire);self.assertFalse(result['primary_prompt_observed']);self.assertEqual(wire.writes,[])

    def test_prompt_prefix_does_not_sanitize_raw_kernel_qualification(self):
        enabled=READY.replace(b'sh-5.3# ',b'\x1b[?2004hsh-5.3# ')
        for boot in (BANNER+b'\x1b[?2004h'+CMDLINE+REG+ENABLE,
                     BANNER+CMDLINE+b'\x1b[?2004h'+REG+ENABLE,
                     BANNER+CMDLINE+REG+b'\x1b[?2004h'+ENABLE):
            wire=passive.PassiveWire([boot+enabled,b'\n'+summary()]);result=observe(wire)
            self.assertFalse(result['readiness_observed']);self.assertFalse(result['memory_summary_valid'])
            self.assertEqual(wire.writes,[])
        wire=passive.PassiveWire([BOOT+enabled,b'\n\x1b[?2004h'+summary()]);result=observe(wire)
        self.assertFalse(result['memory_summary_valid']);self.assertIn('malformed-memory-printk-summary',result['protocol_errors'])
        self.assertEqual(wire.writes,[])

    def test_real_pump_split_backend_prompt_and_summary_CRLF(self):
        data=(BOOT+READY+b'\n'+summary()).replace(b'\n',b'\r\n')
        wire=passive.PassiveWire([data[:40],data[40:175],data[175:-13],data[-13:]])
        result=observe(wire);self.assertEqual(wire.writes,[]);self.assertTrue(result['memory_summary_valid'])
        self.assertEqual(result['stimulus_attempts'],0);self.assertEqual(result['linux_console_backend']['status'],'MATCHED')

    def test_old_channel_duplicates_echo_inserted_CR_or_printk_reject(self):
        for row,error in ((memory.summary(),'wrong-memory-summary-channel'),(summary()*2,'duplicate-memory-summary'),
                          (summary()[:-1],'truncated-memory-printk-summary'),
                          (summary().replace(b'UMK1',b'UM\rK1'),'malformed-memory-printk-summary'),
                          (summary().replace(b' n=',b' [7.0] printk n='),'malformed-memory-printk-summary'),
                          (b"printf '"+summary()+b"'\n",'malformed-memory-printk-summary')):
            wire=passive.PassiveWire([BOOT+READY,b'\n'+row]);result=observe(wire)
            self.assertEqual(wire.writes,[]);self.assertFalse(result['memory_summary_valid']);self.assertIn(error,result['protocol_errors'])

    def test_embedded_CR_backend_and_mixed_old_records_never_qualify_summary(self):
        for markers in (b'corrupt\r'+REG+ENABLE,REG+b'corrupt\r'+ENABLE):
            wire=passive.PassiveWire([BANNER+CMDLINE+markers+READY,b'\n'+summary()]);result=observe(wire)
            self.assertEqual(wire.writes,[]);self.assertIsNone(result['memory_summary'])
            self.assertIn('unqualified-memory-printk-summary',result['protocol_errors'])
        for row in (old.record(0),b'\nK230_UPB1 point=worker-entry\n',b'\nK230_UPP1 point=after-n1-write\n'):
            wire=passive.PassiveWire([BOOT+READY,b'\n'+row+summary()]);result=observe(wire)
            self.assertEqual(wire.writes,[]);self.assertEqual(result['records'],[])
            self.assertFalse(result['memory_summary_valid']);self.assertIn('wrong-memory-summary-channel',result['protocol_errors'])

    def test_missing_wrong_duplicate_reordered_backend_keeps_summary_unqualified(self):
        for markers in (b'',REG,ENABLE,REG*2+ENABLE,ENABLE+REG,REG.replace(b'91400000.serial',b'91401000.serial')+ENABLE):
            wire=passive.PassiveWire([BANNER+CMDLINE+markers+READY,b'\n'+summary()]);result=observe(wire)
            self.assertEqual(wire.writes,[]);self.assertIsNone(result['memory_summary'])
            self.assertIn('unqualified-memory-printk-summary',result['protocol_errors'])
        wire=passive.PassiveWire([BANNER+CMDLINE+summary()+REG+ENABLE+READY]);result=observe(wire)
        self.assertIsNone(result['memory_summary']);self.assertIn('unqualified-memory-printk-summary',result['protocol_errors'])

    def test_prebanner_stale_summary_and_backend_cannot_qualify(self):
        wire=passive.PassiveWire([REG+ENABLE+summary(),BANNER+CMDLINE+READY]);wire.buffer=BOOT+READY+b'\n'+summary()
        result=observe(wire);self.assertIsNone(result['memory_summary']);self.assertEqual(result['linux_console_backend']['status'],'UNKNOWN')
        self.assertEqual(wire.writes,[])
        wire=passive.PassiveWire([summary(),BOOT+READY,b'\n'+summary()]);result=observe(wire)
        self.assertTrue(result['memory_summary_valid']);self.assertEqual(result['protocol_errors'],[])

    def test_raw_received_args_missing_duplicate_wrong_or_embedded_CR_fail_closed(self):
        for cmdline in (b'',CMDLINE*2,CMDLINE.replace(b'printk=1',b'printk=0'),CMDLINE.replace(b'printk=1',b'print\rk=1')):
            wire=passive.PassiveWire([BANNER+cmdline+REG+ENABLE+READY,b'\n'+summary()]);result=observe(wire)
            self.assertFalse(result['kernel_args_verified']);self.assertFalse(result['memory_summary_valid']);self.assertEqual(wire.writes,[])
        wire=passive.PassiveWire([BANNER.replace(b'Linux',b'Lin\rux')+CMDLINE+REG+ENABLE+READY,b'\n'+summary()]);result=observe(wire)
        self.assertFalse(result['memory_summary_valid']);self.assertEqual(wire.writes,[])

    def test_incomplete_timeout_summary_and_absent_prompt_remain_independent(self):
        for row in (summary(1,2,3),summary(waited=0)):
            wire=passive.PassiveWire([BOOT,row]);result=observe(wire)
            self.assertTrue(result['memory_summary_valid']);self.assertTrue(result['memory_summary']['wait_timed_out'])
            self.assertFalse(result['readiness_observed']);self.assertEqual(wire.writes,[])

    def test_missing_summary_overflow_read_error_timeout_zero_input(self):
        for chunks in ([BOOT+READY],[BOOT+READY,b'x'*(1048576+1)]):
            wire=passive.PassiveWire(chunks);result=observe(wire);self.assertEqual(wire.writes,[])
            self.assertIsNone(result['memory_summary']);self.assertEqual(result['receipt_status'],'NOT_REQUESTED')
        wire=passive.PassiveWire([BOOT+READY]);read=wire.port.read
        def fail(size):
            if wire.chunks:return read(size)
            raise OSError('fixture')
        wire.port.read=fail;result=observe(wire);self.assertEqual(wire.writes,[]);self.assertIn('transport-read-unknown',result['protocol_errors'])

    def test_early_normal_return_independent_of_failed_candidate_backend(self):
        wire=passive.PassiveWire([old.NORMAL]);result=observe(wire)
        self.assertTrue(result['normal_prompt_observed']);self.assertFalse(result['candidate_banner'])
        self.assertEqual(result['linux_console_backend']['status'],'UNKNOWN');self.assertEqual(wire.writes,[])

    def test_typed_dependencies_conflicts_and_modes_reject_before_prepare_open(self):
        selected=dict(same_image_shell_pid1=True,uart_progress=True,uart_progress_memory=True,
                      uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True)
        changes=[{'uart_progress_memory_printk':v}for v in (1,None,'yes')]
        changes += [{k:False}for k in ('same_image_shell_pid1','uart_progress','uart_progress_memory','uart_progress_memory_no_stimulus')]
        changes += [{k:True}for k in ('uart_progress_memory_poll_idle','uart_progress_breadcrumbs','uart_progress_post_sample','debug_shutdown','runtime_shutdown_trace','ignore_unused_clocks')]
        for change in changes:
            with mock.patch.object(trial,'prepare_trial')as prep,mock.patch.object(trial,'PrivateSession')as port:
                with self.assertRaises(ValueError):trial.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(selected|change))
                prep.assert_not_called();port.assert_not_called()
        for mode in ('survey','label','root-mount'):
            with mock.patch.object(trial,'prepare_trial')as prep,self.assertRaises(ValueError):trial.run_trial(Path('m'),Path('l'),Path('r'),mode,**selected)
            prep.assert_not_called()

    def test_CLI_defaults_and_exact_required_selection(self):
        for flags in (['--uart-progress-memory-printk'],['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-memory-printk']):
            with mock.patch.object(sys,'argv',['trial',*flags]),mock.patch.object(trial,'run_trial')as run,mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit):trial.main()
                run.assert_not_called()
        flags=['--same-image-shell-pid1','--uart-progress','--uart-progress-memory','--uart-progress-memory-no-stimulus','--uart-progress-memory-printk']
        for argv,enabled in (([],False),(flags,True)):
            with mock.patch.object(sys,'argv',['trial',*argv]),mock.patch.object(trial,'run_trial',return_value=True)as run:
                self.assertEqual(trial.main(),0);self.assertEqual(run.call_args.kwargs.get('uart_progress_memory_printk',False),enabled)

    def printk_artifact(self,root):
        source=root/'source';(source/'drivers/soc/canaan').mkdir(parents=True)
        worker=source/'drivers/soc/canaan/k230-uart-progress.c';worker.write_bytes(b'reviewed new printk worker fixture')
        kernel=root/'kernel';kernel.mkdir();image=kernel/'Image'
        image.write_bytes(b'prefix'+trial.UART_MEMORY_PRINTK_FORMAT+b'k230.uart_progress_memory=\0k230.uart_progress_memory_printk=\0')
        config=root/'config';config.write_bytes(b'CONFIG_PRINTK=y\nCONFIG_PRINTK_TIME=y\nCONFIG_SERIAL_8250_CONSOLE=y\nCONFIG_SERIAL_8250_DW=y\n# CONFIG_PRINTK_CALLER is not set\n')
        proof={'kernel':str(kernel),'config':str(config),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
               'derivation':'/nix/store/'+'a'*32+'-kernel.drv'}
        return {'system':old.fixtures.SYSTEM,'bootargs':old.ARGS,'transport':trial.shell_pid1_transport(old.ARGS,old.fixtures.SYSTEM,uart_progress=True),'uart_progress_kernel':proof},source,worker,image,config

    def test_new_source_hash_format_setup_config_qualification(self):
        with tempfile.TemporaryDirectory()as directory,mock.patch.object(trial,'immutable_store_path',side_effect=lambda p,label:p):
            p,source,worker,image,config=self.printk_artifact(Path(directory));digest=hashlib.sha256(worker.read_bytes()).hexdigest()
            desc={p['uart_progress_kernel']['derivation']:{'env':{'src':str(source)}}}
            with mock.patch.object(trial,'prepare_uart_progress',return_value=p),mock.patch.object(trial,'UART_MEMORY_PRINTK_SOURCE_SHA256',digest),mock.patch.object(trial.subprocess,'check_output',return_value=json.dumps(desc))as query:
                q=trial.prepare_uart_memory_printk({'fixture':'base'})
            self.assertEqual(q['bootargs'],ARGS);self.assertEqual(q['uart_progress_memory_kernel']['worker_sha256'],digest)
            self.assertEqual(q['uart_progress_memory_printk_kernel']['printk_caller'],'disabled')
            self.assertTrue(q['uart_progress_memory_no_stimulus']);self.assertTrue(q['uart_progress_memory_printk'])
            self.assertIn('--offline',query.call_args.args[0]);self.assertNotIn('build',query.call_args.args[0])
            self.assertEqual(q['transport'],'setenv bootargs "'+ARGS.removeprefix('bootargs=')+'"')

    def test_legacy_source_missing_or_wrong_format_setup_gate_reject(self):
        for failure in ('old-source','old-format','no-leading-LF','duplicate-format','missing-printk-gate'):
            with tempfile.TemporaryDirectory()as directory,mock.patch.object(trial,'immutable_store_path',side_effect=lambda p,label:p):
                p,source,worker,image,config=self.printk_artifact(Path(directory));digest=hashlib.sha256(worker.read_bytes()).hexdigest();good=image.read_bytes()
                if failure=='old-source':worker.write_bytes(b'legacy Memory worker')
                elif failure=='old-format':image.write_bytes(trial.UART_MEMORY_FORMAT+b'k230.uart_progress_memory=\0')
                elif failure=='no-leading-LF':image.write_bytes(good.replace(b'\x016\nK230',b'\x016K230'))
                elif failure=='duplicate-format':image.write_bytes(good+trial.UART_MEMORY_PRINTK_FORMAT)
                else:image.write_bytes(good.replace(b'k230.uart_progress_memory_printk=\0',b''))
                desc={p['uart_progress_kernel']['derivation']:{'env':{'src':str(source)}}}
                with mock.patch.object(trial,'prepare_uart_progress',return_value=p),mock.patch.object(trial,'UART_MEMORY_PRINTK_SOURCE_SHA256',digest),mock.patch.object(trial.subprocess,'check_output',return_value=json.dumps(desc)),self.assertRaises(ValueError):trial.prepare_uart_memory_printk({})

    def test_unsupported_caller_enabled_or_duplicate_config_reject_before_source(self):
        for change in ('missing-printk','module-console','caller-y','caller-missing','caller-duplicate','hash-mismatch'):
            with tempfile.TemporaryDirectory()as directory:
                p,source,worker,image,config=self.printk_artifact(Path(directory));raw=config.read_bytes()
                raw=raw.replace(b'CONFIG_PRINTK=y\n',b'')if change=='missing-printk'else raw.replace(b'CONSOLE=y',b'CONSOLE=m')if change=='module-console'else raw.replace(b'# CONFIG_PRINTK_CALLER is not set',b'CONFIG_PRINTK_CALLER=y')if change=='caller-y'else raw.replace(b'# CONFIG_PRINTK_CALLER is not set\n',b'')if change=='caller-missing'else raw+b'# CONFIG_PRINTK_CALLER is not set\n'if change=='caller-duplicate'else raw
                config.write_bytes(raw)
                p['uart_progress_kernel']['config_sha256']='0'*64 if change=='hash-mismatch'else hashlib.sha256(raw).hexdigest()
                with mock.patch.object(trial,'prepare_uart_progress',return_value=p),mock.patch.object(trial,'inspect_uart_memory_kernel')as inspect,self.assertRaises(ValueError):trial.prepare_uart_memory_printk({})
                inspect.assert_not_called()

    def test_exact_new_transport_and_all_previous_mode_outputs(self):
        command=trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True)
        self.assertEqual(command,'setenv bootargs "'+ARGS.removeprefix('bootargs=')+'"')
        self.assertEqual(ARGS.split(),memory.ARGS.split()+[trial.UART_MEMORY_PRINTK_FLAG])
        for bad in (ARGS+' '+trial.UART_MEMORY_PRINTK_FLAG,ARGS+' nohlt',ARGS.replace('printk=1','printk=0'),ARGS+';saveenv',ARGS+'\n'):
            with self.assertRaises(ValueError):trial.shell_pid1_transport(bad,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True)
        for args,kw in ((old.ARGS,{'uart_progress':True}),(memory.ARGS,{'uart_progress':True,'uart_progress_memory':True}),
                        (memory.ARGS+' nohlt',{'uart_progress':True,'uart_progress_memory':True,'uart_progress_memory_poll_idle':True})):
            self.assertEqual(trial.shell_pid1_transport(args,old.fixtures.SYSTEM,**kw),'setenv bootargs "'+args.removeprefix('bootargs=')+'"')

    def test_guarded_normal_return_is_independent_from_summary_and_caller_channel(self):
        normal=old.fixtures.normal();normal['trial_from_boot_id']=normal['boot_id'];after=old.fixtures.Session().run_state('postflight',old.TOKEN)
        for row,protected in ((summary(),True),(summary(1,2,3),True),(b'',True),(summary(),False)):
            wire=passive.PassiveWire([BOOT+READY,b'\n'+row,old.NORMAL]);wire.upload_text=mock.Mock();wire.run_state=mock.Mock(return_value=after if protected else after|{'kernel':'/wrong'})
            p={'bootargs':ARGS,'normal':normal,'helper_text':'fixture','system':old.fixtures.SYSTEM,'bundle':Path('/fixture'),
               'uart_progress_kernel':{},'uart_progress_memory_kernel':{},'uart_progress_memory_no_stimulus':True,
               'uart_progress_memory_printk':True,'uart_progress_memory_printk_kernel':{}}
            original=trial.observe_uart_progress
            def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kw)
            with tempfile.TemporaryDirectory()as directory,mock.patch.object(trial,'observe_uart_progress',side_effect=fast):
                path=Path(directory)/'result';accepted=trial.finish_uart_progress(wire,old.TOKEN,p,{},Path(directory)/'log',path);result=json.loads(path.read_text())
            self.assertEqual(accepted,protected and row==summary());self.assertEqual(wire.writes,[])
            self.assertEqual(result['normal_recovery']is not None,protected);self.assertEqual(wire.upload_text.call_count,2)
            self.assertTrue(result['uart_progress_memory_printk']);self.assertEqual(result['rx_status'],'NOT_TESTED')

    def test_full_boot_protocol_qualifies_printk_and_never_writes_candidate(self):
        class Session(old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'):self.chunks=[BOOT+READY,b'\n'+summary()]
            def write(self,data):self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs':self.writes.append(text.encode());return(ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);bundle=root/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(old.fixtures.ORIGINAL)
            p={'bundle':bundle,'system':old.fixtures.SYSTEM,'normal':old.fixtures.normal(),'helper_text':'pass\n',
               'manifest':{'files':{name:{'bytes':123,'crc32':'abcdef01'}for name,*_ in trial.LOADS}}}
            f,source,worker,image,config=self.printk_artifact(root);digest=hashlib.sha256(worker.read_bytes()).hexdigest();desc={f['uart_progress_kernel']['derivation']:{'env':{'src':str(source)}}}
            session=Session();original=trial.observe_uart_progress
            def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=old.Clock(),**kw)
            selected=dict(same_image_shell_pid1=True,uart_progress=True,uart_progress_memory=True,uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True)
            with mock.patch.object(trial,'prepare_trial',return_value=p),mock.patch.object(trial,'inspect_shell_initrd',return_value={'bash':old.fixtures.BASH}),mock.patch.object(trial,'inspect_uart_progress_kernel',return_value=f['uart_progress_kernel']),mock.patch.object(trial,'UART_MEMORY_PRINTK_SOURCE_SHA256',digest),mock.patch.object(trial,'immutable_store_path',side_effect=lambda p,label:p),mock.patch.object(trial.subprocess,'check_output',return_value=json.dumps(desc)),mock.patch.object(trial,'LOCK_PATH',root/'lock'),mock.patch.object(trial,'PrivateSession',return_value=session),mock.patch.object(trial,'observe_uart_progress',side_effect=fast),mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                self.assertFalse(trial.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',**selected))
            result=json.loads((root/'r').read_text());boot=next(i for i,w in enumerate(session.writes)if w.startswith(b'bootm'))
            self.assertEqual(session.writes[boot+1:],[]);self.assertEqual(result['rx_status'],'NOT_TESTED')
            self.assertTrue(result['uart_progress_memory_printk']);self.assertTrue(result['probe']['memory_summary_valid'])
            self.assertEqual(sum(w.startswith(b'ext4load')for w in session.writes),5);self.assertEqual(sum(w.startswith(b'crc32')for w in session.writes),5)
            self.assertIn(trial.shell_pid1_transport(ARGS,old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True).encode(),session.writes)


if __name__=='__main__':unittest.main()
