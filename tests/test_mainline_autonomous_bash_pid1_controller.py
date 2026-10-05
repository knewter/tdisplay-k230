"""Fixed autonomous argv/strict raw capture and zero-input transport fixtures."""
import importlib.util
from pathlib import Path
import sys,tempfile,json,struct,hashlib
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('auto_base',ROOT/'tests/test_mainline_uart_progress_memory_printk_controller.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
t=f.trial;N='0123456789abcdef0123456789abcdef'
SYSTEM='/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd'
ORIGINAL=f.old.fixtures.ORIGINAL.replace(f.old.fixtures.SYSTEM,SYSTEM)
ARGS=t.autonomous_bash_bootargs(ORIGINAL,SYSTEM,N)
BOOT=f.BANNER+('[    0.200000] Kernel command line: '+ARGS.removeprefix('bootargs=')+'\n').encode()+f.REG+f.ENABLE
INIT=f.READY.split(b'sh-5.3# ')[0]
def row(point,nonce=N):return b'K230_BP1:'+nonce.encode()+b':'+point.encode()+b'\n'
def observe(wire):return t.observe_autonomous_bash(wire,N,ARGS,timeout=5,clock=f.old.Clock())

class AutonomousTests(unittest.TestCase):
    def test_exact_fixed_body_arguments_old_Hush_command_and_no_gates(self):
        script=t.autonomous_bash_script(N);self.assertEqual(len(script),154)
        self.assertEqual(script,'n='+N+r';test $$ = 1&&test $EUID = 0&&printf \\nK230_BP1:%s:B\\n $n&&/bin/sleep 5&&printf \\nK230_BP1:%s:E\\n $n;exec /bin/sh -i')
        command=t.autonomous_bash_transport(ARGS,SYSTEM,N)
        self.assertEqual(len(ARGS.removeprefix('bootargs=')),477);self.assertEqual(len(command),503)
        self.assertEqual(command,"setenv bootargs '"+ARGS.removeprefix('bootargs=').replace('\\','\\\\')+"'")
        self.assertNotIn("'",script);self.assertNotIn('"',script)
        self.assertEqual(ARGS.split(' -- ',1)[1],'-c "'+script+'"')
        for token in ('k230.uart_progress','k230.boot_trace','nohz=','nohlt','initcall_debug'):self.assertNotIn(token,ARGS)
        with self.assertRaises(ValueError):t.shell_pid1_transport(ARGS,SYSTEM)

    def test_nonce_and_altered_script_quotes_backslashes_extra_args_reject(self):
        for n in ('a'*31,'A'*32,'g'*32,N+';reboot',None,1):
            with self.assertRaises((ValueError,TypeError)):t.autonomous_bash_script(n)
        for args in (ARGS.replace('sleep 5','sleep 6'),ARGS+' nohz=off',ARGS.replace('\\\\n','\\n'),ARGS.replace(' -- -c "',' -- -c \''),ARGS+'\n',ARGS+';saveenv',ARGS.replace('exec /bin/sh -i','exit')):
            with self.assertRaises(ValueError):t.autonomous_bash_transport(args,SYSTEM,N)
        with self.assertRaises(ValueError):t.autonomous_bash_bootargs(ORIGINAL.replace('loglevel=7','loglevel=8'),SYSTEM,N)

    def test_typed_pre_open_conflicts_and_modes(self):
        selected=dict(autonomous_bash_pid1=True,same_image_shell_pid1=True)
        changes=[{'autonomous_bash_pid1':v}for v in (1,None,'yes')]+[{'same_image_shell_pid1':False}]
        changes += [{k:True}for k in ('uart_progress','uart_progress_breadcrumbs','uart_progress_post_sample','uart_progress_memory','uart_progress_memory_no_stimulus','uart_progress_memory_poll_idle','uart_progress_memory_printk','uart_progress_memory_printk_nohz_off','ignore_unused_clocks','debug_shutdown','runtime_shutdown_trace')]
        for change in changes:
            with mock.patch.object(t,'prepare_trial')as prepare,mock.patch.object(t,'PrivateSession')as port:
                with self.assertRaises(ValueError):t.run_trial(Path('m'),Path('l'),Path('r'),'minimal',**(selected|change))
                prepare.assert_not_called();port.assert_not_called()
        for mode in ('label','survey','root-mount'):
            with mock.patch.object(t,'prepare_trial')as prepare,self.assertRaises(ValueError):t.run_trial(Path('m'),Path('l'),Path('r'),mode,**selected)
            prepare.assert_not_called()

    def test_CLI_exact_selector_and_older_default(self):
        for argv,enabled in (([],False),(['--same-image-shell-pid1','--autonomous-bash-pid1'],True)):
            with mock.patch.object(sys,'argv',['trial',*argv]),mock.patch.object(t,'run_trial',return_value=True)as run:
                self.assertEqual(t.main(),0);self.assertEqual(run.call_args.kwargs.get('autonomous_bash_pid1',False),enabled)
        with mock.patch.object(sys,'argv',['trial','--autonomous-bash-pid1']),mock.patch.object(t,'run_trial')as run,mock.patch('sys.stderr'):
            with self.assertRaises(SystemExit):t.main()
            run.assert_not_called()

    def test_real_pump_complete_split_CRLF_with_exact_Readline_prompt(self):
        wiredata=(BOOT+INIT+b'\n'+row('B')+row('E')+b'\x1b[?2004hsh-5.3# ').replace(b'\n',b'\r\n')
        wire=f.passive.PassiveWire([wiredata[:35],wiredata[35:300],wiredata[300:-16],wiredata[-16:]])
        r=observe(wire);self.assertEqual(r['records'],['B','E']);self.assertTrue(r['records_complete']);self.assertTrue(r['primary_prompt_observed'])
        self.assertEqual(wire.writes,[]);self.assertEqual(r['rx_status'],'NOT_TESTED');self.assertEqual(r['stimulus_attempts'],0)

    def test_partial_records_and_prompt_are_independent(self):
        for records,prompt in ((row('B'),False),(row('B')+row('E'),False),(b'',True)):
            wire=f.passive.PassiveWire([BOOT+INIT+records+(b'sh-5.3# 'if prompt else b'')]);r=observe(wire)
            self.assertEqual(r['begin_observed'],bool(records));self.assertEqual(r['end_observed'],records==row('B')+row('E'))
            self.assertEqual(r['primary_prompt_observed'],prompt);self.assertEqual(wire.writes,[])

    def test_malformed_stale_duplicate_order_echo_ANSI_CR_interleaved(self):
        for data in (row('B')*2,row('E')+row('B'),row('B','b'*32),row('B')[:-1],b"printf '"+row('B')+b"'\n",b'\x1b[0m'+row('B'),row('B').replace(b'BP1',b'B\rP1'),row('B').replace(b':B',b'[1.0] printk:B')):
            wire=f.passive.PassiveWire([BOOT+INIT,data]);r=observe(wire);self.assertFalse(r['records_complete']);self.assertTrue(r['protocol_errors']);self.assertEqual(wire.writes,[])
        wire=f.passive.PassiveWire([row('B')+row('E'),BOOT+INIT]);wire.buffer=BOOT+INIT+row('B')+row('E')
        r=observe(wire);self.assertEqual(r['records'],[]);self.assertEqual(wire.writes,[])

    def test_wrong_missing_duplicate_args_backend_and_entry_unqualified(self):
        for boot in (f.BANNER+f.REG+f.ENABLE,BOOT.replace(N.encode(),b'b'*32),BOOT.replace(f.REG,b''),BOOT.replace(f.ENABLE,b''),BOOT.replace(f.REG,f.REG*2)):
            wire=f.passive.PassiveWire([boot+INIT,row('B')+row('E')]);r=observe(wire)
            self.assertFalse(r['records_complete']);self.assertIn('unqualified-autonomous-record',r['protocol_errors']);self.assertEqual(wire.writes,[])
        wire=f.passive.PassiveWire([BOOT,row('B')+row('E'),INIT]);self.assertFalse(observe(wire)['records_complete'])

    def test_early_normal_return_not_dependent_on_candidate_and_prompt_stale_reject(self):
        wire=f.passive.PassiveWire([f.old.NORMAL]);r=observe(wire)
        self.assertTrue(r['normal_prompt_observed']);self.assertFalse(r['candidate_banner']);self.assertEqual(wire.writes,[])
        wire=f.passive.PassiveWire([BOOT+INIT+b'\x1b[0msh-5.3# ']);self.assertFalse(observe(wire)['primary_prompt_observed'])

    def test_timeout_overflow_read_error_zero_input(self):
        for chunks in ([BOOT+INIT],[BOOT+INIT,b'x'*1048577]):
            wire=f.passive.PassiveWire(chunks);r=observe(wire);self.assertFalse(r['records_complete']);self.assertEqual(wire.writes,[])
        wire=f.passive.PassiveWire([BOOT]);read=wire.port.read
        def fail(size):
            if wire.chunks:return read(size)
            raise OSError('fixture')
        wire.port.read=fail;r=observe(wire);self.assertIn('transport-read-unknown',r['protocol_errors']);self.assertEqual(wire.writes,[])
        for bound in (0,-1,61,float('nan')):
            with self.assertRaises(ValueError):t.observe_autonomous_bash(wire,N,ARGS,timeout=bound)

    def test_prepare_qualifies_existing_source_but_removes_all_reporter_gates(self):
        with tempfile.TemporaryDirectory()as d:
            bundle=Path(d);(bundle/'bootargs.txt').write_text(ORIGINAL)
            p={'bundle':bundle,'system':SYSTEM,'bootargs':f.ARGS,'normal':{},'shell_comparison':{},'uart_progress_memory_no_stimulus':True,'uart_progress_memory_printk':True}
            with mock.patch.object(t,'prepare_uart_memory_printk',return_value=p),mock.patch.object(t,'inspect_autonomous_archive',return_value={'fixture':True})as inspect:
                q=t.prepare_autonomous_bash({},N)
            inspect.assert_called_once();self.assertEqual(q['bootargs'],ARGS);self.assertEqual(len(q['transport']),503)
            self.assertNotIn('uart_progress_memory_printk',q);self.assertNotIn('uart_progress_memory_no_stimulus',q)

    def test_finish_only_independent_protected_normal_allows_helper_input(self):
        normal=f.old.fixtures.normal();normal['trial_from_boot_id']=normal['boot_id'];after=f.old.fixtures.Session().run_state('postflight',N)
        for returned,protected in ((False,False),(True,True),(True,False)):
            wire=f.passive.PassiveWire([BOOT+INIT+row('B')+row('E')]+([f.old.NORMAL]if returned else []));wire.upload_text=mock.Mock();wire.run_state=mock.Mock(return_value=after if protected else after|{'kernel':'wrong'})
            p={'autonomous_nonce':N,'bootargs':ARGS,'normal':normal,'helper_text':'fixture','system':SYSTEM,'bundle':Path('/fixture'),'uart_progress_kernel':{},'autonomous_archive':{},'autonomous_native_proof':{'fixture':True}}
            original=t.observe_autonomous_bash
            def fast(session,nonce,args):return original(session,nonce,args,timeout=5,clock=f.old.Clock())
            with tempfile.TemporaryDirectory()as d,mock.patch.object(t,'observe_autonomous_bash',side_effect=fast):
                path=Path(d)/'result';self.assertEqual(t.finish_autonomous_bash(wire,p,{},Path(d)/'log',path),protected);r=json.loads(path.read_text())
            self.assertEqual(wire.writes,[]);self.assertEqual(wire.upload_text.call_count,2 if returned else 0)
            self.assertFalse(r['reboot_requested']);self.assertEqual(r['normal_recovery']is not None,protected)

    def test_ELF_interpreter_and_builtin_exports_require_defined_functions(self):
        strings=b'\0printf_builtin\0test_builtin\0exec_builtin\0'
        body=bytearray(1024);body[:6]=b'\x7fELF\x02\x01'
        struct.pack_into('<Q',body,32,64);struct.pack_into('<HH',body,54,56,1)
        loader=b'/nix/store/loader/lib/ld-linux-riscv64-lp64d.so.1\0'
        struct.pack_into('<I',body,64,3);struct.pack_into('<Q',body,72,160);struct.pack_into('<Q',body,96,len(loader));body[160:160+len(loader)]=loader
        struct.pack_into('<Q',body,40,600);struct.pack_into('<HH',body,58,64,3)
        struct.pack_into('<IIQQQQIIQQ',body,600+64,0,3,0,0,300,len(strings),0,0,1,0)
        struct.pack_into('<IIQQQQIIQQ',body,600+128,0,11,0,0,400,72,1,0,8,24)
        body[300:300+len(strings)]=strings
        for i,name in enumerate((b'printf_builtin',b'test_builtin',b'exec_builtin')):
            struct.pack_into('<IBBHQQ',body,400+24*i,strings.index(name),0x12,0,1,1,1)
        self.assertEqual(t.elf_interpreter(body),loader[:-1].decode())
        self.assertEqual(t.bash_builtin_exports(bytes(body)),['exec_builtin','printf_builtin','test_builtin'])
        for change in ('undefined','local','not-function','missing','bad-sections','bad-string'):
            bad=bytearray(body)
            if change=='undefined':struct.pack_into('<H',bad,406,0)
            elif change=='local':bad[404]=0x02
            elif change=='not-function':bad[404]=0x11
            elif change=='missing':bad[300+strings.index(b'printf_builtin')]=ord('X')
            elif change=='bad-sections':struct.pack_into('<Q',bad,40,9999)
            else:struct.pack_into('<I',bad,400,9999)
            with self.assertRaises(ValueError):t.bash_builtin_exports(bytes(bad))
        bad=bytearray(body);struct.pack_into('<Q',bad,96,0)
        with self.assertRaises(ValueError):t.elf_interpreter(bad)

    def test_native_gate_checks_pinned_receipt_fixtures_actual_source_and_fixed_vector(self):
        # Isolated evidence fixture: it never claims actual native execution proof.
        with tempfile.TemporaryDirectory() as d:
            repo=Path(d); fixture=repo/'tests/fixtures/mainline-autonomous-pid1';fixture.mkdir(parents=True)
            bundle=repo/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(ORIGINAL)
            source=repo/'source';(source/'lib').mkdir(parents=True);(source/'lib/cmdline.c').write_bytes(b'fixture selected Linux')
            digest=lambda body:hashlib.sha256(body).hexdigest()
            linux_files={'lib/cmdline.c':{'sha256':digest((source/'lib/cmdline.c').read_bytes())}}
            bodies={'cli_hush-v2022.10.c':b'fixture full Hush','linux-selected-functions.h':b'fixture excerpts',
                    'linux-source.json':json.dumps({'files':linux_files}).encode(),
                    'script.expected':t.autonomous_bash_script(N).encode(),
                    'bootargs.expected':ARGS.removeprefix('bootargs=').encode(),
                    'transport.expected':t.autonomous_bash_transport(ARGS,SYSTEM,N).encode()}
            for name,body in bodies.items():(fixture/name).write_bytes(body)
            test=repo/'tests/test_mainline_autonomous_bash_pid1_argv.py';test.write_bytes(b'fixture native test')
            receipt={'schema':1,'status':'PASS','evidence_class':'native-host-parser',
                'fixture_manifest':{str((fixture/name).relative_to(repo)):digest(body)for name,body in bodies.items()},
                'test_source_sha256':digest(test.read_bytes()),
                'hush':{'source_sha256':digest(bodies['cli_hush-v2022.10.c']),'native_execution':True,
                    'dispatch':['setenv','bootargs'],'command_count':1,'parser_ifs_lookups':1,
                    'script_variable_lookups':0,'extra_commands':0,'persistent_writes':0},
                'linux':{'source':str(source),'files':linux_files,'excerpts_sha256':digest(bodies['linux-selected-functions.h']),
                    'native_execution':True,'argv':['-c',t.autonomous_bash_script(N)]},
                'vector':{'nonce':N,'transport_with_cr_length':504}|{name:{'length':len(bodies[name+'.expected']),
                    'sha256':digest(bodies[name+'.expected'])}for name in ('script','bootargs','transport')}}
            path=repo/'docs/evidence/mainline-autonomous-bash-pid1/native-argv/result.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(receipt))
            prepared={'bundle':bundle,'system':SYSTEM,'uart_progress_memory_printk_kernel':{'source':str(source)}}
            pin=digest(path.read_bytes())
            with mock.patch.object(t,'AUTONOMOUS_NATIVE_RECEIPT_SHA256',pin):
                self.assertEqual(t.qualify_autonomous_native(prepared,proof_repo=repo)['fixture_count'],6)
                for target in (path,fixture/'transport.expected',fixture/'cli_hush-v2022.10.c',test,source/'lib/cmdline.c'):
                    old=target.read_bytes();target.write_bytes(old+b'x')
                    with self.assertRaises(ValueError):t.qualify_autonomous_native(prepared,proof_repo=repo)
                    target.write_bytes(old)
                with self.assertRaises(ValueError):t.qualify_autonomous_native(prepared|{'system':'/nix/store/wrong'},proof_repo=repo)
                with self.assertRaises(ValueError):t.qualify_autonomous_native(prepared|{'uart_progress_memory_printk_kernel':{'source':'/missing'}},proof_repo=repo)
                path.unlink()
                with self.assertRaises(ValueError):t.qualify_autonomous_native(prepared,proof_repo=repo)

    def test_missing_native_gate_stops_before_UART_and_boot(self):
        with mock.patch.object(t,'prepare_trial',return_value={}),mock.patch.object(t,'prepare_autonomous_bash',return_value={}),mock.patch.object(t,'qualify_autonomous_native',side_effect=ValueError('missing reviewed proof')),mock.patch.object(t,'PrivateSession')as port:
            with self.assertRaises(ValueError):t.run_trial(Path('m'),Path('l'),Path('r'),'minimal',same_image_shell_pid1=True,autonomous_bash_pid1=True)
            port.assert_not_called()

    def test_full_mocked_boot_exact_single_Hush_command_and_no_postboot_input(self):
        class Session(f.old.fixtures.Session):
            def line(self,text,interrupt=True):
                super().line(text,interrupt)
                if text.startswith('bootm'):self.chunks=[BOOT+INIT,row('B')+row('E')]
            def write(self,data):self.writes.append(data)
            def command(self,text,timeout):
                if text=='printenv bootargs':self.writes.append(text.encode());return(ARGS+'\nK230# ').encode()
                return super().command(text,timeout)
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);bundle=root/'bundle';bundle.mkdir();(bundle/'bootargs.txt').write_text(ORIGINAL)
            prepared={'bundle':bundle,'system':SYSTEM,'normal':f.old.fixtures.normal(),'helper_text':'fixture',
                'manifest':{'files':{name:{'bytes':123,'crc32':'abcdef01'}for name,*_ in t.LOADS}},
                'uart_progress_kernel':{},'shell_comparison':{'bash':f.old.fixtures.BASH},
                'uart_progress_memory_no_stimulus':True,'uart_progress_memory_printk':True}
            session=Session();original=t.observe_autonomous_bash
            def fast(active,nonce,args):return original(active,nonce,args,timeout=5,clock=f.old.Clock())
            with mock.patch.object(t,'prepare_trial',return_value=prepared),mock.patch.object(t,'prepare_uart_memory_printk',side_effect=lambda x:x),mock.patch.object(t,'inspect_autonomous_archive',return_value={'fixture':True}),mock.patch.object(t,'qualify_autonomous_native',return_value={'fixture':True},create=True),mock.patch.object(t.uuid,'uuid4',return_value=type('UUID',(),{'hex':N})()),mock.patch.object(t,'LOCK_PATH',root/'lock'),mock.patch.object(t,'PrivateSession',return_value=session),mock.patch.object(t,'observe_autonomous_bash',side_effect=fast),mock.patch.dict(sys.modules,{'serial':mock.Mock()}):
                self.assertFalse(t.run_trial(root/'m',root/'l',root/'r','minimal',bundle,root/'n',same_image_shell_pid1=True,autonomous_bash_pid1=True))
            r=json.loads((root/'r').read_text());boot=next(i for i,w in enumerate(session.writes)if w.startswith(b'bootm'))
            self.assertEqual(session.writes[boot+1:],[]);self.assertTrue(r['probe']['records_complete'])
            commands=[w for w in session.writes if w.startswith(b'setenv bootargs')]
            self.assertEqual(commands,[t.autonomous_bash_transport(ARGS,SYSTEM,N).encode()])
            self.assertEqual(sum(w.startswith(b'ext4load')for w in session.writes),5);self.assertEqual(sum(w.startswith(b'crc32')for w in session.writes),5)
            self.assertEqual(r['rx_status'],'NOT_TESTED');self.assertFalse(r['reboot_requested'])
            class FlushUnknown(Session):
                def line(self,text,interrupt=True):
                    super().line(text,interrupt)
                    if text.startswith('bootm'):raise OSError('write accepted; flush unknown')
            failed=FlushUnknown()
            with mock.patch.object(t,'prepare_trial',return_value=prepared),mock.patch.object(t,'prepare_uart_memory_printk',side_effect=lambda x:x),mock.patch.object(t,'inspect_autonomous_archive',return_value={'fixture':True}),mock.patch.object(t,'qualify_autonomous_native',return_value={'fixture':True}),mock.patch.object(t.uuid,'uuid4',return_value=type('UUID',(),{'hex':N})()),mock.patch.object(t,'LOCK_PATH',root/'lock'),mock.patch.object(t,'PrivateSession',return_value=failed),mock.patch.dict(sys.modules,{'serial':mock.Mock()}),mock.patch('sys.stderr'):
                with self.assertRaises(OSError):t.run_trial(root/'m',root/'unknown.log',root/'unknown.result','minimal',bundle,root/'n',same_image_shell_pid1=True,autonomous_bash_pid1=True)
            boot=next(i for i,w in enumerate(failed.writes)if w.startswith(b'bootm'))
            self.assertEqual(failed.writes[boot+1:],[])
            unknown=json.loads((root/'unknown.result').read_text());self.assertTrue(unknown['boot_attempted'])
            self.assertEqual(unknown['candidate_execution'],'UNVERIFIED');self.assertIsNone(unknown['normal_recovery'])

if __name__=='__main__':unittest.main()
