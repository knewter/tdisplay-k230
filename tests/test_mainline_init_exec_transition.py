"""Bounded optional transition qualification, strict passive witnesses and transport."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('transition_parent_fixtures', ROOT/'tests/test_mainline_init_exec_return.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
t, d = f.t, f.d


def selected(original=d.ORIGINAL):
    return t.ordinary_bootargs(original, d.SYSTEM, wait_initramfs_in_initcall=True,
                              without_boot_markers=True, init_exec_return=True, init_exec_transition=True)


def prepared():
    p = f.prepared()
    p.update(init_exec_transition=True, bootargs=selected(),
             diagnostic_controls=t.diagnostic_controls(True, without_boot_markers=True,
                                                       init_exec_return=True, init_exec_transition=True))
    return p


PARENT = b'[    4.548457] K230_INIT_EXEC_RETURN_V1 ret=0\n'
RETURN = b'[    4.549000] K230_INIT_EXEC_TRANSITION_V1 point=kernel-init-return\n'
ECALL = b'[    4.550000] K230_INIT_EXEC_TRANSITION_V1 point=first-user-ecall\n'
LOGIN = b'nixos login: \nroot@nixos:~# '


def observe(body, p=None):
    p = p or prepared()
    session = f.Pump([body[i:i+17] for i in range(0, len(body), 17)])
    ready = t.wait_init_exec_candidate(session, p, timeout=180, clock=session.clock)
    return ready, p['init_exec_transition_observation'], p['init_exec_return_observation'], session


class Selection(unittest.TestCase):
    def test_exact_child_gates_literal_bound_and_old_profiles(self):
        self.assertEqual(selected(), f.selected()+' '+t.INIT_EXEC_TRANSITION_FLAG)
        p=prepared();command=t.volatile_bootargs_command(p)
        self.assertEqual(command, 'setenv bootargs "'+selected().removeprefix('bootargs=')+'"')
        self.assertLessEqual(len(command.encode()), 512)
        for wait, without, debug, info, kmsg, parent in (
            (False,False,False,False,False,False), (True,False,False,False,False,False),
            (True,True,False,False,False,False), (True,True,True,False,False,False),
            (True,True,False,True,False,False), (True,True,False,False,True,False),
            (True,True,False,False,False,True)):
            kw=dict(wait_initramfs_in_initcall=wait,without_boot_markers=without,initrd_debug_logging=debug,
                    initrd_info_logging=info,initrd_info_kmsg_logging=kmsg,init_exec_return=parent)
            self.assertEqual(t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**kw),
                             t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**kw,init_exec_transition=False))

    def test_types_dependencies_conflicts_preparation_output_and_UART_never_called(self):
        baseline=dict(phase='begin',wait_initramfs_in_initcall=True,without_boot_markers=True,
                      init_exec_return=True,init_exec_transition=True)
        changes=[{'init_exec_transition':v} for v in (None,0,1,'false')]
        changes += [{'phase':v} for v in ('finish','touch')]
        changes += [{k:v} for k in ('init_exec_return','wait_initramfs_in_initcall','without_boot_markers') for v in (False,None,1,'true')]
        changes += [{k:True} for k in ('initrd_debug_logging','initrd_info_logging','initrd_info_kmsg_logging')]
        for change in changes:
            with self.subTest(change=change), mock.patch.object(t,'prepare') as prep, mock.patch.object(t.rd,'safe_log_path') as output, mock.patch.object(t.rd,'PrivateSession') as uart:
                with self.assertRaises(ValueError):t.run(SimpleNamespace(**(baseline|change)))
                prep.assert_not_called();output.assert_not_called();uart.assert_not_called()

    def test_inherited_alias_missing_duplicate_changed_and_injection_rejected(self):
        for key in ('k230.init_exec_transition','k230.init-exec-transition','rd.k230.init_exec_transition'):
            for tail in ('','=1','=0'):
                with self.assertRaises(ValueError):selected(d.ORIGINAL.rstrip()+' '+key+tail+'\n')
        p=prepared()
        for value in (p['bootargs'].replace('k230.init_exec_transition=1','k230.init_exec_transition=0'),
                      p['bootargs'].replace(' k230.init_exec_transition=1',''),
                      p['bootargs']+' '+t.INIT_EXEC_TRANSITION_FLAG,p['bootargs']+' $x',
                      p['bootargs']+';saveenv',p['bootargs']+' '+'a'*512):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'bootargs':value})
            facts=f.f.f.facts()['bootargs']|{'cmdline':value.removeprefix('bootargs=')}
            with self.assertRaises(t.Unknown):t.validate_stage('bootargs',facts,p,p['normal'])

    def test_saved_default_false_typed_resume_and_invalid_saved_no_input(self):
        p=prepared();facts=f.f.f.facts();facts['bootargs']['cmdline']=p['bootargs'].removeprefix('bootargs=')
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);root.chmod(0o700)
            args=f.f.args_at(root,initrd_info_kmsg_logging=False,init_exec_return=True,init_exec_transition=True)
            Session=f.f.session_for(p);f.f.f.FlowSession.values=facts;f.f.f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}), mock.patch.object(t,'prepare',return_value=p) as prep, mock.patch.object(t.rd,'PrivateSession',Session), mock.patch.object(t.rd,'LOCK_PATH',root/'lock'), mock.patch.object(t,'wait_init_exec_candidate',side_effect=lambda s,p:t.wait_candidate(s)):
                    self.assertTrue(t.run(args));state=json.loads(args.state.read_text());self.assertTrue(state['init_exec_transition'])
                    args.phase='finish';args.init_exec_transition=False;args.init_exec_return=False
                    args.log=root/'finish.log';args.result=root/'finish.result'
                    self.assertTrue(t.run(args));self.assertTrue(prep.call_args.kwargs['init_exec_transition'])
            finally:f.f.f.FlowSession.values=None
            state.pop('init_exec_transition');args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop')) as prep:
                with self.assertRaises(ValueError):t.run(args)
                self.assertNotIn('init_exec_transition',prep.call_args.kwargs)
            for v in ('false',0,1,None):
                args.state.write_text(json.dumps(state|{'init_exec_transition':v}))
                with mock.patch.object(t,'prepare') as prep, mock.patch.object(t.rd,'safe_log_path') as output:
                    with self.assertRaises(ValueError):t.run(args)
                    prep.assert_not_called();output.assert_not_called()

    def test_core_load_boot_identity_recovery_and_parent_qualifier_unchanged(self):
        original=subprocess.check_output(['git','show','ea54f9e0:tools/mainline-drm-system-trial.py'],cwd=ROOT,text=True)
        funcs=lambda s:{n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
        old,new=funcs(original),funcs(Path(t.__file__).read_text())
        # touch: task 3.1 replaced whole-log evtest retrieval with a bounded on-board
        # K230_TOUCH_SUMMARY record; capture_command and parse_touch are untouched.
        changed={'diagnostic_controls','ordinary_bootargs','prepare','inspect_init_exec_kernel','wait_init_exec_candidate','volatile_bootargs_command','run','main','touch'}
        for name in old.keys()-changed:self.assertEqual(old[name],new[name],name)
        old_q=subprocess.check_output(['git','show','ea54f9e0:tools/mainline-init-exec-return-qualify.py'],cwd=ROOT)
        self.assertEqual(old_q,(ROOT/'tools/mainline-init-exec-return-qualify.py').read_bytes())

    def test_CLI_child_requires_parent_and_both_comparison_flags(self):
        paths=['--bundle','b','--manifest','m','--normal-report','n','--state','s','--log','l','--result','r']
        parents=['--wait-initramfs-in-initcall','--without-boot-markers','--init-exec-return']
        for flags in ([],parents[:2],parents[1:],parents+['--initrd-info-logging']):
            with mock.patch.object(sys,'argv',['trial','begin',*paths,*flags,'--init-exec-transition']),mock.patch.object(t,'run') as run, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit) as exc:t.main()
                self.assertEqual(exc.exception.code,2);run.assert_not_called()
        with mock.patch.object(sys,'argv',['trial','begin',*paths,*parents,'--init-exec-transition']),mock.patch.object(t,'run',return_value=True) as run:
            self.assertEqual(t.main(),0);self.assertTrue(run.call_args.args[0].init_exec_transition)


class Records(unittest.TestCase):
    def test_exact_known_complete_timestamp_lines_only(self):
        for point,line in zip(t.INIT_EXEC_TRANSITION_POINTS,(RETURN,ECALL)):
            for ending in (line,line.replace(b'\n',b'\r\n')):self.assertEqual(t.init_exec_transition_record(ending),point)
        for line in (RETURN.rstrip(b'\n'),RETURN.replace(b'4.549000',b'4.549'),b'echo '+RETURN,
                     RETURN.replace(b'kernel-init-return',b'unknown'),RETURN.replace(b'V1',b'V2'),
                     RETURN.replace(b'point=',b'point=\r'),b'sh-5.3# '+RETURN,
                     RETURN.replace(b'] ',b'][    5.000000] unrelated\n')):
            self.assertIsNone(t.init_exec_transition_record(line))

    def test_complete_sequence_is_passive_fact_until_login_prompt(self):
        p=prepared();wire=f.phase(p)+PARENT+RETURN+ECALL
        ready,facts,parent,session=observe(wire,p)
        self.assertFalse(ready);self.assertTrue(facts['sequence_complete']);self.assertEqual(facts['missing_records'],[])
        self.assertTrue(facts['kernel_init_return_observed']);self.assertTrue(facts['user_ecall_observed'])
        self.assertEqual(facts['exec_result_output_call_return'],'OBSERVED')
        self.assertEqual(parent['record_output_call_return'],'OBSERVED')
        self.assertEqual(facts['kernel_init_return_output_call_return'],'OBSERVED')
        self.assertEqual(facts['record_output_call_return'],'UNVERIFIED');self.assertEqual(session.writes,[])
        ready,facts,parent,session=observe(wire+LOGIN)
        self.assertTrue(ready);self.assertTrue(parent['primary_prompt']);self.assertEqual(session.writes,[])

    def test_missing_earlier_retains_independent_later_ecall_not_readiness(self):
        for records,missing in ((ECALL,['exec-result-zero','kernel-init-return']),
                                (PARENT+ECALL,['kernel-init-return']),
                                (RETURN+ECALL,['exec-result-zero']),
                                (PARENT+RETURN,['first-user-ecall'])):
            p=prepared();ready,facts,parent,s=observe(f.phase(p)+records+LOGIN,p)
            self.assertFalse(ready);self.assertEqual(facts['errors'],[]);self.assertEqual(facts['missing_records'],missing)
            self.assertEqual(facts['user_ecall_observed'],ECALL in records)
            self.assertEqual(facts['kernel_init_return_output_call_return'],'OBSERVED' if RETURN in records and ECALL in records else 'UNVERIFIED')
            self.assertEqual(s.writes,[])

    def test_hostile_scope_order_duplicate_nonzero_truncation_unqualified_never_ready(self):
        p=prepared();phase=f.phase(p)
        cases=[phase+PARENT+RETURN+RETURN+ECALL,phase+PARENT+ECALL+RETURN,
               phase+PARENT.replace(b'ret=0',b'ret=-2')+RETURN+ECALL,
               phase+PARENT+RETURN+ECALL.rstrip(b'\n'),phase+PARENT+b'echo '+RETURN+ECALL,
               phase+PARENT+RETURN.replace(b'point=',b'point=\r')+ECALL,
               phase.replace(b'k230.init_exec_transition=1',b'k230.init_exec_transition=0')+PARENT+RETURN+ECALL,
               phase+phase+PARENT+RETURN+ECALL,phase+PARENT+RETURN+ECALL+b'U-Boot SPL\n',
               phase.replace(b'[    4.000000] Run /init as init process\n',b'')+PARENT+RETURN+ECALL]
        for wire in cases:
            with self.subTest(wire=wire):
                ready,facts,parent,s=observe(wire,prepared())
                self.assertFalse(ready);self.assertTrue(facts['errors']);self.assertEqual(s.writes,[])
                self.assertFalse(facts['user_ecall_observed'])
        ready,facts,parent,s=observe(ECALL+phase+PARENT+RETURN)
        self.assertFalse(ready);self.assertEqual(facts['points'],['kernel-init-return'])

    def test_real_pump_keeps_early_facts_beyond_ring_buffer_and_partial_bound(self):
        p=prepared();s=f.Pump([f.phase(p)+PARENT+RETURN,b'x\n'*90000,ECALL])
        self.assertFalse(t.wait_init_exec_candidate(s,p,timeout=10,clock=s.clock))
        self.assertTrue(p['init_exec_transition_observation']['sequence_complete']);self.assertEqual(s.writes,[])
        p=prepared();s=f.Pump([f.phase(p)+PARENT+RETURN,b'x'*4097])
        with self.assertRaises(t.Unknown):t.wait_init_exec_candidate(s,p,timeout=10,clock=s.clock)
        self.assertEqual(p['init_exec_transition_observation']['points'],['kernel-init-return']);self.assertEqual(s.writes,[])

    def test_full_transport_unknown_keeps_facts_no_postboot_input(self):
        p=prepared();Session=f.f.session_for(p)
        real_capture=t.wait_init_exec_transition_candidate
        def capture(session,p,*unused):
            raw=f.phase(p)+PARENT+RETURN+ECALL
            pump=f.Pump([raw]);return real_capture(pump,p,timeout=10,clock=pump.clock)
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);root.chmod(0o700);args=f.f.args_at(root,initrd_info_kmsg_logging=False,init_exec_return=True,init_exec_transition=True)
            with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_init_exec_transition_candidate',side_effect=capture),mock.patch('sys.stderr'):
                self.assertFalse(t.run(args))
            wire=Session.instances[-1].writes
            self.assertEqual(sum(w.startswith(b'ext4load') for w in wire),5)
            self.assertEqual(sum(w.startswith(b'crc32') for w in wire),5)
            self.assertIn(t.volatile_bootargs_command(p).encode(),wire)
            self.assertEqual(wire[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
            result=json.loads(args.result.read_text());self.assertTrue(result['init_exec_transition'])
            self.assertTrue(result['init_exec_transition_observation']['sequence_complete'])
            self.assertIsNone(result['normal_recovery']);self.assertFalse(args.state.exists())

    def test_bad_load_crc_printenv_and_boot_flush_stop_without_candidate_input(self):
        for failure in ('load','crc','printenv','flush'):
            p=prepared();Base=f.f.session_for(p)
            class Session(Base):
                def command(self,command,timeout):
                    value=super().command(command,timeout)
                    if failure=='load' and command.startswith('ext4load'):return b'124 bytes read in 1 ms\nK230# '
                    if failure=='crc' and command.startswith('crc32'):return b'CRC32 => deadbeef\nK230# '
                    if failure=='printenv' and command=='printenv bootargs':return b'bootargs=bad\nK230# '
                    return value
                def line(self,command,interrupt=True):
                    super().line(command,interrupt)
                    if failure=='flush' and command.startswith('bootm'):raise OSError('accepted write, failed flush')
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as name:
                root=Path(name);root.chmod(0o700);args=f.f.args_at(root,initrd_info_kmsg_logging=False,init_exec_return=True,init_exec_transition=True)
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_init_exec_transition_candidate') as capture,mock.patch('sys.stderr'):
                    self.assertFalse(t.run(args));capture.assert_not_called()
                wire=Session.instances[-1].writes
                self.assertEqual(sum(w.startswith(b'bootm') for w in wire),failure=='flush')
                if failure=='flush':self.assertEqual(wire[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
                self.assertIsNone(json.loads(args.result.read_text())['normal_recovery'])


class Artifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('transition_qualifier',ROOT/'tools/mainline-init-exec-transition-qualify.py')
        cls.q=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.q)

    def test_parent_archive_policy_reused_not_forked(self):
        self.assertIs(self.q.archive_delta,self.q.parent.archive_delta)
        self.assertIs(self.q.hardware_dt,self.q.parent.hardware_dt)
        old,new=f.ArchiveDelta().trees();self.assertTrue(self.q.archive_delta(old,new)['module_tree_relocation']['normalized_bytes_and_modes_equal'])
        for bad in (new|{'etc/unit':(0o100644,b'changed unit')},new|{'unrelated':(0o100644,b'new dependency')}):
            with self.assertRaises(ValueError):self.q.archive_delta(old,bad)

    def test_actual_parent_rejected_without_build_UART(self):
        system=Path('/nix/store/gi850b5xn2s398grgfw7xlbwdf1n5cbf-nixos-system-nixos-26.11.20260919.20b1ddd')
        if not system.exists():self.skipTest('realized parent artifact unavailable')
        with self.assertRaisesRegex(ValueError,'not the reviewed exec-return variant'):
            t.inspect_init_exec_kernel({'system':str(system),'init_exec_transition':True})

    def test_realized_source_hashes_are_the_reviewed_four_files(self):
        source=Path('/nix/store/79yd40jv8h4x866bm1vyw94cm948grax-linux-mainline-k230-init-exec-transition-src')
        if not source.exists():self.skipTest('immutable source absent on CI host')
        for name,expected in t.INIT_EXEC_TRANSITION_SOURCE_SHA256.items():
            self.assertEqual(hashlib.sha256((source/name).read_bytes()).hexdigest(),expected,name)

    def test_selected_four_sources_config_unique_formats_fail_closed(self):
        paths=('init/main.c','arch/riscv/kernel/process.c','arch/riscv/kernel/traps.c','include/linux/k230-init-exec-transition.h')
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source';kernel=root/'kernel';kernel.mkdir()
            for path in paths:
                file=source/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(('fixture '+path).encode())
            hashes={path:hashlib.sha256((source/path).read_bytes()).hexdigest() for path in paths}
            config=root/'config';config.write_bytes(b'CONFIG_PRINTK=y\nCONFIG_PRINTK_TIME=y\nCONFIG_SERIAL_8250_CONSOLE=y\n# CONFIG_PRINTK_CALLER is not set\n')
            literals=(t.INIT_EXEC_RETURN_FORMAT,b'k230.init_exec_return=\0',*t.INIT_EXEC_TRANSITION_FORMATS,b'k230.init_exec_transition=\0')
            image=b'ELFfixture'+b''.join(literals);(kernel/'Image').write_bytes(image)
            proof={'kernel':str(kernel),'config':str(config),'derivation':'/nix/store/'+'a'*32+'-kernel.drv'}
            drv=json.dumps({proof['derivation']:{'env':{'src':str(source)}}})
            with mock.patch.object(t,'INIT_EXEC_TRANSITION_SOURCE_SHA256',hashes),mock.patch.object(t.rd,'inspect_uart_progress_kernel',return_value=proof),mock.patch.object(t.subprocess,'check_output',return_value=drv),mock.patch.object(t.rd,'immutable_store_path',side_effect=lambda p,label:p):
                result=t.inspect_init_exec_kernel({'init_exec_transition':True})
                self.assertEqual(result['transition_source_sha256'],hashes)
                for path in paths:
                    file=source/path;old=file.read_bytes();file.write_bytes(old+b'changed')
                    with self.assertRaises(ValueError):t.inspect_init_exec_kernel({'init_exec_transition':True})
                    file.write_bytes(old)
                for broken in (image.replace(literals[-1],b''),image+literals[-2],image.replace(literals[2],b'')):
                    (kernel/'Image').write_bytes(broken)
                    with self.assertRaises(ValueError):t.inspect_init_exec_kernel({'init_exec_transition':True})
                (kernel/'Image').write_bytes(image);config.write_bytes(config.read_bytes()+b'CONFIG_PRINTK_CALLER=y\n')
                # Explicit disabled plus enabled is never an eligible config.
                with self.assertRaises(ValueError):t.inspect_init_exec_kernel({'init_exec_transition':True})
                config.write_bytes(b'CONFIG_PRINTK=y\nCONFIG_PRINTK_TIME=y\nCONFIG_SERIAL_8250_CONSOLE=y\n# CONFIG_PRINTK_CALLER is not set\n')
                for v in (1,None,'false'):
                    with self.assertRaises(ValueError):t.inspect_init_exec_kernel({'init_exec_transition':v})


if __name__=='__main__':unittest.main()
