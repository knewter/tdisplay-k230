"""Fixed initrd-manager logging policy and actual-pump/zero-input fixtures."""
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
spec = importlib.util.spec_from_file_location('ordinary_logging_fixtures', ROOT/'tests/test_mainline_drm_system_trial.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
t = f.trial
SYSTEM = '/nix/store/yk44vx3ny4h6a9mx3ya4rczh7akhyjbj-nixos-system-nixos-26.11.20260919.20b1ddd'
ORIGINAL = ('bootargs=consoleblank=0 console=ttyS0,115200n8 root=fstab loglevel=4 '
            'lsm=landlock,yama,bpf loglevel=7 k230.boot_trace=1 k230.boot_trace_sbi_only=1 '
            f'init={SYSTEM}/init\n')


def selected(system=SYSTEM, original=ORIGINAL):
    return t.ordinary_bootargs(original, system, wait_initramfs_in_initcall=True,
                              without_boot_markers=True, initrd_debug_logging=True)


def prepared():
    p = f.prepared()
    original = ORIGINAL.replace(SYSTEM, f.SYSTEM)
    p['bootargs'] = selected(f.SYSTEM, original)
    p['diagnostic_controls'] = t.diagnostic_controls(True, without_boot_markers=True, initrd_debug_logging=True)
    p['without_boot_markers'] = p['initrd_debug_logging'] = True
    return p


class LoggingTests(unittest.TestCase):
    def test_exact_two_tokens_actual_system_356_arguments_374_transport(self):
        old = t.ordinary_bootargs(ORIGINAL, SYSTEM, wait_initramfs_in_initcall=True, without_boot_markers=True)
        args = selected()
        self.assertEqual(args, old + ' rd.systemd.log_level=debug rd.systemd.log_target=console')
        p = {'bootargs': args, 'without_boot_markers': True, 'initrd_debug_logging': True,
             'diagnostic_controls': t.diagnostic_controls(True, without_boot_markers=True, initrd_debug_logging=True)}
        command = t.volatile_bootargs_command(p)
        self.assertEqual(len(args.removeprefix('bootargs=').encode()), 356)
        self.assertEqual(len(command.encode()), 374)
        self.assertEqual(command, 'setenv bootargs "' + args.removeprefix('bootargs=') + '"')
        self.assertNotIn('${', command); self.assertNotIn('k230.boot_trace', command)
        self.assertEqual([x for x in args.split() if 'log_' in x], list(t.INITRD_DEBUG_LOGGING))

    def test_old_argument_transport_values_and_controls_unchanged(self):
        for wait,without in ((False,False),(True,False),(True,True)):
            old = t.ordinary_bootargs(ORIGINAL,SYSTEM,wait_initramfs_in_initcall=wait,without_boot_markers=without)
            default = t.ordinary_bootargs(ORIGINAL,SYSTEM,wait_initramfs_in_initcall=wait,without_boot_markers=without,initrd_debug_logging=False)
            self.assertEqual(old,default)
            controls=t.CONTROLS+(('initramfs_async=0',)if wait else ())
            self.assertEqual(t.diagnostic_controls(wait,without_boot_markers=without),controls)
            p={'bootargs':old,'diagnostic_controls':controls,'without_boot_markers':without}
            expected=('setenv bootargs "'+old.removeprefix('bootargs=')+'"'if without else
                      'setenv bootargs "${bootargs} '+' '.join(controls)+'"')
            self.assertEqual(t.volatile_bootargs_command(p),expected)
        self.assertEqual(t.diagnostic_controls(),t.CONTROLS)

    def test_types_dependencies_modes_reject_before_prepare_output_or_UART(self):
        base=dict(phase='begin',initrd_debug_logging=True,wait_initramfs_in_initcall=True,without_boot_markers=True)
        changes=[{'initrd_debug_logging':v}for v in (None,0,1,'false')]
        changes += [{'phase':p}for p in ('touch','finish','survey')]
        changes += [{name:v}for name in ('wait_initramfs_in_initcall','without_boot_markers')for v in (False,None,1,'true')]
        for changed in changes:
            with mock.patch.object(t,'prepare')as prepare,mock.patch.object(t.rd,'safe_log_path')as paths,mock.patch.object(t.rd,'PrivateSession')as session:
                with self.assertRaises(ValueError):t.run(SimpleNamespace(**(base|changed)))
                prepare.assert_not_called();paths.assert_not_called();session.assert_not_called()

    def test_all_inherited_logging_aliases_values_fail_before_outputs_UART(self):
        names=[prefix+'systemd.'+key for prefix in ('','rd.')for key in ('log_level','log-level','log_target','log-target')]
        extras=('rd.udev.log_level','rd.systemd.journald.forward_to_console','systemd.setenv','k230.uart_progress','nohz','nohlt',
                'rd.systemd.unit','rd.systemd.mask','systemd.debug-shell','rd.systemd.debug-shell','rd.systemd.break','rd.fsck.mode',
                'initcall-debug','clk-ignore-unused','ignore-loglevel','rd.debug','rd.quiet')
        with tempfile.TemporaryDirectory()as d:
            bundle=Path(d);args=SimpleNamespace(phase='begin',bundle=bundle,manifest=Path('m'),normal_report=Path('n'),initrd_debug_logging=True,wait_initramfs_in_initcall=True,without_boot_markers=True)
            for name in names+list(extras):
                for suffix in ('','=debug','=console','=bad'):
                    (bundle/'bootargs.txt').write_text(ORIGINAL.rstrip()+' '+name+suffix+'\n')
                    with mock.patch.object(t.rd,'prepare_trial',return_value={'system':SYSTEM}),mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as session:
                        with self.assertRaises(ValueError):t.run(args)
                        output.assert_not_called();session.assert_not_called()

    def test_transport_missing_duplicate_alias_changed_unsafe_or_oversized_reject(self):
        p=prepared();args=p['bootargs']
        for changed in (args.replace('rd.systemd.log_level=debug',''),args+' rd.systemd.log_target=console',
                        args.replace('rd.systemd.log_level','rd.systemd.log-level'),args.replace('=console','=kmsg'),
                        args+';saveenv',args+'\n',args+' "',args+' $x',args+' '+'a'*512):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'bootargs':changed})
        for bad in (None,1,'false'):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'initrd_debug_logging':bad})
        with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'without_boot_markers':False})
        with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'diagnostic_controls':t.diagnostic_controls(True)})

    def test_prepare_adds_selection_only_when_enabled_and_keeps_artifact_guards(self):
        with tempfile.TemporaryDirectory()as d:
            bundle=Path(d);(bundle/'bootargs.txt').write_text(ORIGINAL)
            source={'system':SYSTEM,'helper_text':'fixture original helper','normal':{'fixture':True},'manifest':{'fixture':True}}
            with mock.patch.object(t.rd,'prepare_trial',side_effect=lambda *a:dict(source))as original,mock.patch.object(t.os,'access',return_value=True)as access:
                base=t.prepare(bundle,Path('m'),Path('n'),wait_initramfs_in_initcall=True,without_boot_markers=True)
                p=t.prepare(bundle,Path('m'),Path('n'),wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_debug_logging=True)
            # 11 required tools (task 3.1 added "awk" for the bounded on-board touch summary) x 2 prepare() calls.
            self.assertEqual(original.call_count,2);self.assertEqual(access.call_count,22)
            self.assertNotIn('initrd_debug_logging',base);self.assertTrue(p['initrd_debug_logging'])
            self.assertEqual(p['bootargs'],base['bootargs']+' '+' '.join(t.INITRD_DEBUG_LOGGING))
            for key in ('system','helper_text','normal','manifest','kernel','pid1'):self.assertEqual(p[key],base[key])
            self.assertIn("assert not Path('/nix-path-registration').exists()",p['helper_text'])

    def test_exact_live_cmdline_includes_both_tokens_once(self):
        p=prepared();facts=f.facts()['bootargs']|{'cmdline':p['bootargs'].removeprefix('bootargs=')}
        t.validate_stage('bootargs',facts,p,p['normal'])
        for changed in (facts['cmdline'].replace(' rd.systemd.log_level=debug',''),facts['cmdline'].replace('=console','=kmsg'),facts['cmdline']+' rd.systemd.log_level=debug'):
            with self.assertRaises(t.Unknown):t.validate_stage('bootargs',facts|{'cmdline':changed},p,p['normal'])

    def test_real_pump_verbose_split_readiness_beyond_cap_preserves_complete_private_wire(self):
        stale=b'nixos login: root\n[root@nixos:~]# \n'
        banner=b'[    0.100000] Linux version 7.3.0-rc5 fixture\n'
        verbose=(b'[    5.000000] systemd[1]: fixture unit logging\n'*6000)
        chunks=[stale,banner[:25],banner[25:]]+[verbose[x:x+4096]for x in range(0,len(verbose),4096)]
        chunks += [b'nixos lo',b'gin: root\n[root@nixos:',b'~]# ']
        wire=f.PumpSession(chunks)
        self.assertTrue(t.wait_candidate(wire,clock=f.Clock()))
        self.assertGreater(len(wire.log.getvalue()),131072);self.assertLessEqual(len(wire.buffer),131072)
        self.assertEqual(wire.log.getvalue(),b''.join(chunks));self.assertEqual(wire.writes,[])

    def test_real_pump_unknown_banner_login_prompt_and_read_error_never_write(self):
        for chunks in ([b'nixos login: root\n[root@nixos:~]# '],
                       [b'Linux version 7.3.0-rc5 fixture\n',b'[root@nixos:~]# '],
                       [b'Linux version 7.3.0-rc5 fixture\nnixos login: root\n']):
            wire=f.PumpSession(chunks)
            self.assertFalse(t.wait_candidate(wire,timeout=2,clock=f.Clock()));self.assertEqual(wire.writes,[])
        wire=f.PumpSession([])
        wire.port.read=lambda n:(_ for _ in ()).throw(OSError('fixture read'))
        with self.assertRaises(OSError):t.wait_candidate(wire,timeout=2,clock=f.Clock())
        self.assertEqual(wire.writes,[])

    def test_full_boot_five_load_CRC_exact_printenv_and_unknown_no_further_input(self):
        p=prepared()
        class LoggingSession(f.FlowSession):
            def command(self,command,timeout):
                if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
                return super().command(command,timeout)
        wire=LoggingSession(None,SimpleNamespace(write=lambda data:None))
        t.boot(wire,p)
        self.assertEqual(sum(w.startswith(b'ext4load')for w in wire.writes),5)
        self.assertEqual(sum(w.startswith(b'crc32')for w in wire.writes),5)
        self.assertEqual([w for w in wire.writes if w.startswith(b'setenv bootargs')],[t.volatile_bootargs_command(p).encode()])
        self.assertEqual(wire.writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
        for failure in ('readiness','write'):
            wire=LoggingSession(None,SimpleNamespace(write=lambda data:None))
            oldline=wire.line
            def line(command,interrupt=True):
                oldline(command,interrupt)
                if command.startswith('bootm')and failure=='write':raise OSError('accepted write; unknown flush')
            wire.line=line
            with mock.patch.object(t,'wait_candidate',return_value=False):
                with self.assertRaises((t.Unknown,OSError)):t.boot(wire,p)
            self.assertEqual(wire.writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
            self.assertFalse(any(w.startswith(b'upload')for w in wire.writes))

    def test_saved_selection_restores_exact_args_and_old_states_default_false(self):
        p=prepared();values=f.facts();values['bootargs']['cmdline']=p['bootargs'].removeprefix('bootargs=')
        class Session(f.FlowSession):
            def command(self,command,timeout):
                if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
                return super().command(command,timeout)
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);root.chmod(0o700)
            args=SimpleNamespace(phase='begin',bundle=Path('/fixture/bundle'),manifest=root/'m',normal_report=root/'n',state=root/'state',log=root/'begin.log',result=root/'begin.result',real_touch=False,wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_debug_logging=True)
            f.FlowSession.values=values;f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p)as prepare_call,mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'):
                    self.assertTrue(t.run(args));state=json.loads(args.state.read_text());self.assertTrue(state['initrd_debug_logging'])
                    args.phase='finish';args.log=root/'finish.log';args.result=root/'finish.result';args.initrd_debug_logging=False;args.wait_initramfs_in_initcall=False;args.without_boot_markers=False
                    self.assertTrue(t.run(args));self.assertTrue(prepare_call.call_args.kwargs['initrd_debug_logging']);self.assertTrue(json.loads(args.result.read_text())['initrd_debug_logging'])
            finally:f.FlowSession.values=None
            state.pop('initrd_debug_logging');state['status']='candidate-ready';args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop'))as call:
                with self.assertRaises(ValueError):t.run(args)
            self.assertNotIn('initrd_debug_logging',call.call_args.kwargs)
            state['initrd_debug_logging']='false';args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare')as call,mock.patch.object(t.rd,'safe_log_path')as output:
                with self.assertRaises(ValueError):t.run(args)
                call.assert_not_called();output.assert_not_called()

    def test_unknown_run_persists_selection_facts_and_sends_no_postboot_input(self):
        p=prepared();values=f.facts()
        class Session(f.FlowSession):
            def command(self,command,timeout):
                if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
                return super().command(command,timeout)
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);root.chmod(0o700)
            args=SimpleNamespace(phase='begin',bundle=Path('/fixture/bundle'),manifest=root/'m',normal_report=root/'n',state=root/'state',log=root/'trial.log',result=root/'result',real_touch=False,wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_debug_logging=True)
            f.FlowSession.values=values;f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_candidate',side_effect=OSError('fixture read')),mock.patch('sys.stderr'):
                    self.assertFalse(t.run(args))
                wire=Session.instances[-1];self.assertEqual(wire.writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
                result=json.loads(args.result.read_text());self.assertTrue(result['initrd_debug_logging']);self.assertIsNone(result['normal_recovery'])
                self.assertFalse(args.state.exists())
            finally:f.FlowSession.values=None

    def test_CLI_begin_only_and_required_parent_options(self):
        for argv in (['finish'],['touch'],['begin','--wait-initramfs-in-initcall'],['begin','--without-boot-markers']):
            cmd=[sys.executable,str(Path(t.__file__)),*argv,'--initrd-debug-logging','--state','/missing/state','--log','/missing/log','--result','/missing/result']
            if argv[0]=='begin':cmd += ['--bundle','/missing/bundle','--manifest','/missing/manifest','--normal-report','/missing/report']
            result=subprocess.run(cmd,capture_output=True);self.assertEqual(result.returncode,2)
        for flag,expected in (([],False),(['--initrd-debug-logging'],True)):
            with mock.patch.object(sys,'argv',['trial','begin','--bundle','b','--manifest','m','--normal-report','n','--state','s','--log','l','--result','r','--wait-initramfs-in-initcall','--without-boot-markers',*flag]),mock.patch.object(t,'run',return_value=True)as run:
                self.assertEqual(t.main(),0);self.assertEqual(run.call_args.args[0].initrd_debug_logging,expected)


if __name__=='__main__':unittest.main()
