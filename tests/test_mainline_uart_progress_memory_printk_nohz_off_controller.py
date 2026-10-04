"""Same-image nohz-off qualification, exact transport and passive wire tests."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('printk_nohz_base',ROOT/'tests/test_mainline_uart_progress_memory_printk_controller.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
t=f.trial
SELECT=dict(same_image_shell_pid1=True,uart_progress=True,uart_progress_memory=True,
    uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True,uart_progress_memory_printk_nohz_off=True)
ARGS=f.ARGS+' nohz=off'
BOOT=f.BOOT.replace(f.ARGS.removeprefix("bootargs=").encode(),ARGS.removeprefix("bootargs=").encode())


def prepared(root):
    p,source,worker,image,config=f.MemoryPrintkControllerTests().printk_artifact(root)
    config.write_bytes(config.read_bytes()+b'CONFIG_NO_HZ_COMMON=y\nCONFIG_NO_HZ_FULL=y\nCONFIG_HIGH_RES_TIMERS=y\nCONFIG_HZ=250\nCONFIG_RISCV_TIMER=y\nCONFIG_RISCV_SBI=y\n# CONFIG_NO_HZ is not set\n')
    image.write_bytes(image.read_bytes()+b'nohz=\0')
    p.update(bootargs=f.ARGS,transport=t.shell_pid1_transport(f.ARGS,p['system'],uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True),
        uart_progress_memory_printk=True,uart_progress_memory_no_stimulus=True,
        uart_progress_memory_kernel={'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()},uart_progress_memory_printk_kernel={})
    p['uart_progress_kernel']['config_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
    return p,image,config


def observe(wire):
    return t.observe_uart_progress(wire,f.old.TOKEN,ARGS,timeout=5,readiness_timeout=3,clock=f.old.Clock(),
        uart_progress_memory=True,uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True)


class NoHzOffTests(unittest.TestCase):
    def test_typed_dependencies_modes_and_conflicts_fail_before_prepare_or_open(self):
        changes=[{'uart_progress_memory_printk_nohz_off':v}for v in (1,None,'yes')]
        changes += [{k:False}for k in SELECT if k!='uart_progress_memory_printk_nohz_off']
        changes += [{k:True}for k in ('uart_progress_memory_poll_idle','uart_progress_breadcrumbs','uart_progress_post_sample','ignore_unused_clocks','debug_shutdown','runtime_shutdown_trace')]
        for change in changes:
            with mock.patch.object(t,'prepare_trial')as prep,mock.patch.object(t,'PrivateSession')as port:
                with self.assertRaises(ValueError):t.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(SELECT|change))
                prep.assert_not_called();port.assert_not_called()
        for mode in ('survey','label','root-mount'):
            with mock.patch.object(t,'prepare_trial')as prep,self.assertRaises(ValueError):t.run_trial(Path('m'),Path('l'),Path('r'),mode,**SELECT)
            prep.assert_not_called()

    def test_CLI_default_and_exact_new_opt_in(self):
        flags=['--'+k.replace('_','-')for k in SELECT]
        for argv,enabled in (([],False),(flags,True)):
            with mock.patch.object(sys,'argv',['trial',*argv]),mock.patch.object(t,'run_trial',return_value=True)as run:
                self.assertEqual(t.main(),0);self.assertEqual(run.call_args.kwargs.get('uart_progress_memory_printk_nohz_off',False),enabled)
        for bad in (['--uart-progress-memory-printk-nohz-off'],flags+['--uart-progress-memory-poll-idle']):
            with mock.patch.object(sys,'argv',['trial',*bad]),mock.patch.object(t,'run_trial')as run,mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit):t.main()
                run.assert_not_called()

    def test_exact_one_token_transport_and_old_printk_rejection(self):
        kw=dict(uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True)
        original=t.shell_pid1_transport(f.ARGS,f.old.fixtures.SYSTEM,**kw)
        command=t.shell_pid1_transport(ARGS,f.old.fixtures.SYSTEM,**kw,uart_progress_memory_printk_nohz_off=True)
        self.assertEqual(command,original[:-1]+' nohz=off"');self.assertEqual(len(command)-len(original),9)
        self.assertEqual(ARGS.split(),f.ARGS.split()+['nohz=off'])
        with self.assertRaises(ValueError):t.shell_pid1_transport(ARGS,f.old.fixtures.SYSTEM,**kw)
        for v in (1,None,'yes'):
            with self.assertRaises(ValueError):t.shell_pid1_transport(ARGS,f.old.fixtures.SYSTEM,**kw,uart_progress_memory_printk_nohz_off=v)

    def test_bare_empty_alternate_duplicate_competing_unsafe_arguments_reject(self):
        for value in ('nohz','nohz=','nohz=0','nohz=of','nohz=OFF','nohz=off nohz=off','nohz_full=0','nohz=off nohz_full=0','nohz=off nohlt','nohz=off highres=off','nohz=off;saveenv','nohz=off\n'):
            with self.assertRaises(ValueError):t.shell_pid1_transport(f.ARGS+' '+value,f.old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True,uart_progress_memory_printk_nohz_off=True)

    def test_actual_style_config_legacy_NO_HZ_unset_and_hash_proof(self):
        with tempfile.TemporaryDirectory()as d:
            p,image,config=prepared(Path(d));old=dict(p);q=t.prepare_uart_memory_printk_nohz_off(p)
            self.assertEqual(q['bootargs'],ARGS);self.assertEqual(q['transport'],p['transport'][:-1]+' nohz=off"')
            self.assertEqual(p,old);self.assertEqual(q['uart_progress_kernel'],p['uart_progress_kernel'])
            self.assertEqual(q['uart_progress_memory_kernel'],p['uart_progress_memory_kernel'])
            self.assertEqual(q['uart_progress_memory_printk_nohz_off_kernel']['hz'],250)
            self.assertEqual(q['uart_progress_memory_printk_nohz_off_kernel']['linked_nohz_setup_offset'],image.read_bytes().index(b'nohz=\0'))

    def test_each_required_builtin_and_HZ_duplicate_missing_wrong_reject(self):
        for name in ('NO_HZ_COMMON','NO_HZ_FULL','HIGH_RES_TIMERS','RISCV_TIMER','RISCV_SBI','HZ'):
            for change in ('missing','wrong','duplicate'):
                with tempfile.TemporaryDirectory()as d:
                    p,image,config=prepared(Path(d));value=b'250'if name=='HZ'else b'y';line=b'CONFIG_'+name.encode()+b'='+value+b'\n';raw=config.read_bytes()
                    config.write_bytes(raw.replace(line,b'')if change=='missing'else raw.replace(line,line.replace(value,b'100'if name=='HZ'else b'm'))if change=='wrong'else raw+line)
                    p['uart_progress_kernel']['config_sha256']=hashlib.sha256(config.read_bytes()).hexdigest()
                    with self.assertRaises(ValueError):t.prepare_uart_memory_printk_nohz_off(p)

    def test_config_Image_hash_or_missing_duplicate_setup_reject(self):
        for failure in ('config-hash','image-hash','missing','duplicate'):
            with tempfile.TemporaryDirectory()as d:
                p,image,config=prepared(Path(d))
                if failure=='config-hash':p['uart_progress_kernel']['config_sha256']='0'*64
                elif failure=='image-hash':p['uart_progress_memory_kernel']['image_sha256']='0'*64
                else:
                    image.write_bytes(image.read_bytes().replace(b'nohz=\0',b'')if failure=='missing'else image.read_bytes()+b'nohz=\0')
                    p['uart_progress_memory_kernel']['image_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):t.prepare_uart_memory_printk_nohz_off(p)

    def test_prior_args_transport_or_policy_mismatch_reject(self):
        for key,value in (('bootargs',f.ARGS+' nohz=off'),('bootargs',f.ARGS+' nohz_full=0'),('transport','unsafe'),('uart_progress_memory_printk',False),('uart_progress_memory_no_stimulus',False),('uart_progress_memory_poll_idle',True)):
            with tempfile.TemporaryDirectory()as d:
                p,*_=prepared(Path(d));p[key]=value
                with self.assertRaises(ValueError):t.prepare_uart_memory_printk_nohz_off(p)

    def test_real_pump_split_CRLF_summary_and_Readline_prompt_zero_input(self):
        data=(BOOT+f.READY.replace(b'sh-5.3# ',b'\x1b[?2004hsh-5.3# ')+b'\n'+f.summary()).replace(b'\n',b'\r\n')
        wire=f.passive.PassiveWire([data[:100],data[100:-20],data[-20:]])
        r=observe(wire);self.assertTrue(r['readiness_observed']);self.assertTrue(r['memory_summary_valid']);self.assertEqual(wire.writes,[])
        self.assertEqual(r['receipt_status'],'NOT_REQUESTED');self.assertEqual(r['rx_status'],'NOT_TESTED')

    def test_wrong_stale_missing_args_and_bad_records_do_not_authorize_writes(self):
        for boot in (f.BOOT,BOOT.replace(b'nohz=off',b'nohz=on'),f.BANNER+f.REG+f.ENABLE):
            wire=f.passive.PassiveWire([boot+f.READY,b'\n'+f.summary()]);r=observe(wire)
            self.assertFalse(r['kernel_args_verified']);self.assertFalse(r['memory_summary_valid']);self.assertEqual(wire.writes,[])
        for row in (f.summary()*2,f.summary()[:-1],f.memory.summary(),f.summary().replace(b'UMK1',b'UM\rK1')):
            wire=f.passive.PassiveWire([BOOT+f.READY,b'\n'+row]);r=observe(wire)
            self.assertFalse(r['memory_summary_valid']);self.assertEqual(wire.writes,[])

    def test_timeout_overflow_read_error_zero_input(self):
        for chunks in ([BOOT+f.READY],[BOOT+f.READY,b'x'*1048577]):
            wire=f.passive.PassiveWire(chunks);r=observe(wire);self.assertEqual(wire.writes,[]);self.assertFalse(r['memory_summary_valid'])
        wire=f.passive.PassiveWire([BOOT]);read=wire.port.read
        def fail(size):
            if wire.chunks:return read(size)
            raise OSError('fixture')
        wire.port.read=fail;r=observe(wire);self.assertIn('transport-read-unknown',r['protocol_errors']);self.assertEqual(wire.writes,[])

    def test_finish_proof_and_independent_protected_recovery(self):
        with tempfile.TemporaryDirectory()as d:
            p,*_=prepared(Path(d));p=t.prepare_uart_memory_printk_nohz_off(p);p.update(normal=f.old.fixtures.normal(),helper_text='fixture',bundle=Path('/fixture'))
            p['normal']['trial_from_boot_id']=p['normal']['boot_id']
            after=f.old.fixtures.Session().run_state('postflight',f.old.TOKEN)
            for normal,protected in ((b'',False),(f.old.NORMAL,True)):
                wire=f.passive.PassiveWire([BOOT+f.READY,b'\n'+f.summary(),normal]);wire.upload_text=mock.Mock();wire.run_state=mock.Mock(return_value=after)
                original=t.observe_uart_progress
                def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=f.old.Clock(),**kw)
                result=Path(d)/('returned'if protected else 'unknown')
                with mock.patch.object(t,'observe_uart_progress',side_effect=fast):self.assertEqual(t.finish_uart_progress(wire,f.old.TOKEN,p,{},Path(d)/'log',result),protected)
                r=json.loads(result.read_text());self.assertTrue(r['uart_progress_memory_printk_nohz_off']);self.assertEqual(wire.writes,[])
                self.assertEqual(wire.upload_text.call_count,2 if protected else 0)
                self.assertEqual(r['normal_recovery']is not None,protected)
            bad=dict(p);del bad['uart_progress_memory_printk_nohz_off_kernel']
            with self.assertRaises(ValueError):t.finish_uart_progress(wire,f.old.TOKEN,bad,{},Path(d)/'log',Path(d)/'bad')

    def test_full_boot_protocol_qualifies_printk_and_never_writes_candidate(self):
        class Session(f.old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'):self.chunks=[BOOT+f.READY,b'\n'+f.summary()]
            def write(self,data):self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs':self.writes.append(text.encode());return(ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);bundle=root/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(f.old.fixtures.ORIGINAL)
            p={'bundle':bundle,'system':f.old.fixtures.SYSTEM,'normal':f.old.fixtures.normal(),'helper_text':'pass\n',
               'manifest':{'files':{name:{'bytes':123,'crc32':'abcdef01'}for name,*_ in t.LOADS}}}
            fixture,image,config=prepared(root);source=root/'source';worker=source/'drivers/soc/canaan/k230-uart-progress.c';digest=hashlib.sha256(worker.read_bytes()).hexdigest();desc={fixture['uart_progress_kernel']['derivation']:{'env':{'src':str(source)}}}
            session=Session();original=t.observe_uart_progress
            def fast(active,token,args,**kw):return original(active,token,args,timeout=5,readiness_timeout=3,clock=f.old.Clock(),**kw)
            selected=dict(same_image_shell_pid1=True,uart_progress=True,uart_progress_memory=True,uart_progress_memory_no_stimulus=True,uart_progress_memory_printk=True,uart_progress_memory_printk_nohz_off=True)
            with mock.patch.object(t,'prepare_trial',return_value=p),mock.patch.object(t,'inspect_shell_initrd',return_value={'bash':f.old.fixtures.BASH}),mock.patch.object(t,'inspect_uart_progress_kernel',return_value=fixture['uart_progress_kernel']),mock.patch.object(t,'UART_MEMORY_PRINTK_SOURCE_SHA256',digest),mock.patch.object(t,'immutable_store_path',side_effect=lambda p,label:p),mock.patch.object(t.subprocess,'check_output',return_value=json.dumps(desc)),mock.patch.object(t,'LOCK_PATH',root/'lock'),mock.patch.object(t,'PrivateSession',return_value=session),mock.patch.object(t,'observe_uart_progress',side_effect=fast),mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                self.assertFalse(t.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',**selected))
            result=json.loads((root/'r').read_text());boot=next(i for i,w in enumerate(session.writes)if w.startswith(b'bootm'))
            self.assertEqual(session.writes[boot+1:],[]);self.assertEqual(result['rx_status'],'NOT_TESTED')
            self.assertTrue(result['uart_progress_memory_printk']);self.assertTrue(result['probe']['memory_summary_valid'])
            self.assertEqual(sum(w.startswith(b'ext4load')for w in session.writes),5);self.assertEqual(sum(w.startswith(b'crc32')for w in session.writes),5)
            self.assertIn(t.shell_pid1_transport(ARGS,f.old.fixtures.SYSTEM,uart_progress=True,uart_progress_memory=True,uart_progress_memory_printk=True,uart_progress_memory_printk_nohz_off=True).encode(),session.writes)


if __name__=='__main__':unittest.main()
