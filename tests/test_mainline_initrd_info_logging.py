"""One-value info/console child; common pump/unknown fixtures live in debug tests."""
import ast
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
spec = importlib.util.spec_from_file_location('debug_logging_fixtures', ROOT/'tests/test_mainline_initrd_debug_logging.py')
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
t, f = d.t, d.f


def selected(system=d.SYSTEM, original=d.ORIGINAL):
    return t.ordinary_bootargs(original, system, wait_initramfs_in_initcall=True,
                              without_boot_markers=True, initrd_info_logging=True)


def prepared():
    p = d.prepared()
    p['bootargs'] = p['bootargs'].replace('rd.systemd.log_level=debug', 'rd.systemd.log_level=info')
    p.pop('initrd_debug_logging')
    p['initrd_info_logging'] = True
    p['diagnostic_controls'] = t.diagnostic_controls(True, without_boot_markers=True, initrd_info_logging=True)
    return p


def args_at(root, **changes):
    return SimpleNamespace(**(dict(phase='begin',bundle=Path('/fixture/bundle'),manifest=root/'m',normal_report=root/'n',
        state=root/'state',log=root/'trial.log',result=root/'result',real_touch=False,
        wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_info_logging=True)|changes))


class InfoTests(unittest.TestCase):
    def test_fixed_one_value_355_arguments_373_transport_and_legacy_debug_values(self):
        debug = d.selected(); info = selected()
        self.assertEqual(info, debug.replace('rd.systemd.log_level=debug','rd.systemd.log_level=info'))
        self.assertEqual(len(info.removeprefix('bootargs=').encode()),355)
        p={'bootargs':info,'without_boot_markers':True,'initrd_info_logging':True,
           'diagnostic_controls':t.diagnostic_controls(True,without_boot_markers=True,initrd_info_logging=True)}
        self.assertEqual(t.volatile_bootargs_command(p),'setenv bootargs "'+info.removeprefix('bootargs=')+'"')
        self.assertEqual(len(t.volatile_bootargs_command(p).encode()),373)
        self.assertEqual(t.initrd_logging_controls(True),t.INITRD_DEBUG_LOGGING)
        self.assertEqual(t.initrd_logging_controls(info=True),t.INITRD_INFO_LOGGING)
        self.assertEqual(t.initrd_logging_controls(),())
        for wait,without,debug_mode in ((False,False,False),(True,False,False),(True,True,False),(True,True,True)):
            modes=dict(wait_initramfs_in_initcall=wait,without_boot_markers=without,initrd_debug_logging=debug_mode)
            old=t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**modes)
            self.assertEqual(old,t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**modes,initrd_info_logging=False))
        self.assertEqual(len(debug.removeprefix('bootargs=').encode()),356)

    def test_shared_capture_identity_load_recovery_functions_unchanged_from_reviewed_base(self):
        base=subprocess.run(['git','show','6bb1e8ee:tools/mainline-drm-system-trial.py'],cwd=ROOT,capture_output=True,check=True,text=True).stdout
        def functions(source):return{n.name:ast.dump(n,include_attributes=False)for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        old,new=functions(base),functions(Path(t.__file__).read_text())
        for name in ('wait_candidate','wait_normal','boot','exchange','report_command','validate_stage','identity','normal_check'):
            self.assertEqual(new[name],old[name],name)

    def test_typed_modes_conflicts_reject_before_prepare_outputs_and_UART(self):
        baseline=dict(phase='begin',initrd_info_logging=True,wait_initramfs_in_initcall=True,without_boot_markers=True)
        changes=[{'initrd_info_logging':v}for v in (None,0,1,'false')]
        changes += [{'phase':v}for v in ('touch','finish','survey')]
        changes += [{k:v}for k in ('wait_initramfs_in_initcall','without_boot_markers')for v in (False,None,1,'true')]
        changes += [{'initrd_debug_logging':v}for v in (True,None,1,'false')]
        for change in changes:
            with mock.patch.object(t,'prepare')as prepare,mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as session:
                with self.assertRaises(ValueError):t.run(SimpleNamespace(**(baseline|change)))
                prepare.assert_not_called();output.assert_not_called();session.assert_not_called()

    def test_selected_inherited_aliases_values_and_instrumentation_reject_before_output_UART(self):
        aliases=[prefix+'systemd.'+key for prefix in ('','rd.')for key in ('log_level','log-level','log_target','log-target')]
        aliases += ['rd.debug','rd.quiet','rd.systemd.debug-shell','systemd.unit','rd.systemd.mask','rd.udev.log-level',
                    'systemd.journald.forward-to-console','k230.uart_progress','nohlt','nohz','initcall-debug','clk-ignore-unused']
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);args=args_at(root,bundle=root)
            for name in aliases:
                for value in ('','=info','=debug','=console','=bad'):
                    (root/'bootargs.txt').write_text(d.ORIGINAL.rstrip()+' '+name+value+'\n')
                    with mock.patch.object(t.rd,'prepare_trial',return_value={'system':d.SYSTEM}),mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as session:
                        with self.assertRaises(ValueError):t.run(args)
                        output.assert_not_called();session.assert_not_called()

    def test_literal_transport_requires_exact_singletons_types_and_bound(self):
        p=prepared(); original=p['bootargs']
        for args in (original.replace('rd.systemd.log_level=info',''),original+' rd.systemd.log_level=info',
                     original.replace('=info','=debug'),original.replace('log_level','log-level'),
                     original.replace('=console','=kmsg'),original+' $x',original+';saveenv',original+'\n',original+' '+'a'*512):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'bootargs':args})
        for change in ({'initrd_debug_logging':True},{'initrd_info_logging':'false'},
                       {'without_boot_markers':False},{'diagnostic_controls':t.diagnostic_controls(True)}):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|change)

    def test_prepare_retains_default_debug_artifact_helpers_and_only_info_selection(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);(root/'bootargs.txt').write_text(d.ORIGINAL)
            original={'system':d.SYSTEM,'helper_text':'fixture helper','normal':{'fixture':True},'manifest':{'fixture':True}}
            with mock.patch.object(t.rd,'prepare_trial',side_effect=lambda*a:dict(original)),mock.patch.object(t.os,'access',return_value=True):
                debug=t.prepare(root,root/'m',root/'n',wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_debug_logging=True)
                info=t.prepare(root,root/'m',root/'n',wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_info_logging=True)
                base=t.prepare(root,root/'m',root/'n',wait_initramfs_in_initcall=True,without_boot_markers=True)
            self.assertNotIn('initrd_info_logging',debug);self.assertNotIn('initrd_info_logging',base)
            self.assertNotIn('initrd_debug_logging',info);self.assertTrue(info['initrd_info_logging'])
            for name in ('system','helper_text','normal','manifest','kernel','pid1'):self.assertEqual(info[name],debug[name])
            self.assertIn("assert not Path('/nix-path-registration').exists()",info['helper_text'])
            self.assertEqual(info['bootargs'],debug['bootargs'].replace('rd.systemd.log_level=debug','rd.systemd.log_level=info'))

    def test_exact_live_cmdline_guard_does_not_accept_debug_alias_or_duplicate(self):
        p=prepared();facts=f.facts()['bootargs']|{'cmdline':p['bootargs'].removeprefix('bootargs=')}
        t.validate_stage('bootargs',facts,p,p['normal'])
        for args in (facts['cmdline'].replace('=info','=debug'),facts['cmdline'].replace('log_level','log-level'),
                     facts['cmdline']+' rd.systemd.log_target=console',facts['cmdline'].replace(' rd.systemd.log_level=info','')):
            with self.assertRaises(t.Unknown):t.validate_stage('bootargs',facts|{'cmdline':args},p,p['normal'])

    def test_begin_finish_saved_info_and_old_state_defaults_and_bad_state_preopen(self):
        p=prepared();facts=f.facts();facts['bootargs']['cmdline']=p['bootargs'].removeprefix('bootargs=')
        class Session(f.FlowSession):
            def command(self,command,timeout):
                if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
                return super().command(command,timeout)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);root.chmod(0o700);args=args_at(root)
            f.FlowSession.values=facts;f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p)as prepare_call,mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'):
                    self.assertTrue(t.run(args));state=json.loads(args.state.read_text());self.assertTrue(state['initrd_info_logging']);self.assertFalse(state['initrd_debug_logging'])
                    args.phase='finish';args.log=root/'finish.log';args.result=root/'finish.result';args.initrd_info_logging=False;args.wait_initramfs_in_initcall=False;args.without_boot_markers=False
                    self.assertTrue(t.run(args));self.assertTrue(prepare_call.call_args.kwargs['initrd_info_logging'])
                    self.assertTrue(json.loads(args.result.read_text())['initrd_info_logging'])
            finally:f.FlowSession.values=None
            for phase in ('touch','finish'):
                args.phase=phase;args.real_touch=phase=='touch';state['status']='candidate-ready';args.state.write_text(json.dumps(state))
                with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop'))as call:
                    with self.assertRaises(ValueError):t.run(args)
                self.assertTrue(call.call_args.kwargs['initrd_info_logging'])
            state.pop('initrd_info_logging');args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop'))as call:
                with self.assertRaises(ValueError):t.run(args)
            self.assertNotIn('initrd_info_logging',call.call_args.kwargs)
            for value,debug in (('false',False),(True,True)):
                state['initrd_info_logging']=value;state['initrd_debug_logging']=debug;args.state.write_text(json.dumps(state))
                with mock.patch.object(t,'prepare')as call,mock.patch.object(t.rd,'safe_log_path')as paths,mock.patch.object(t.rd,'PrivateSession')as session:
                    with self.assertRaises(ValueError):t.run(args)
                    call.assert_not_called();paths.assert_not_called();session.assert_not_called()

    def test_unknown_run_preserves_info_facts_and_no_postboot_input(self):
        p=prepared()
        class Session(f.FlowSession):
            def command(self,command,timeout):
                if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
                return super().command(command,timeout)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);root.chmod(0o700);args=args_at(root)
            with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_candidate',side_effect=OSError('fixture unknown read')),mock.patch('sys.stderr'):
                self.assertFalse(t.run(args))
            self.assertEqual(Session.instances[-1].writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
            result=json.loads(args.result.read_text());self.assertTrue(result['initrd_info_logging']);self.assertIsNone(result['normal_recovery']);self.assertFalse(args.state.exists())

    def test_CLI_dependencies_exclusion_and_begin_only(self):
        for phase,flags in (('finish',[]),('touch',[]),('begin',[]),('begin',['--wait-initramfs-in-initcall']),
                            ('begin',['--wait-initramfs-in-initcall','--without-boot-markers','--initrd-debug-logging'])):
            argv=[sys.executable,str(Path(t.__file__)),phase,'--initrd-info-logging','--state','/missing/s','--log','/missing/l','--result','/missing/r',*flags]
            if phase=='begin':argv+=['--bundle','/missing/b','--manifest','/missing/m','--normal-report','/missing/n']
            self.assertEqual(subprocess.run(argv,capture_output=True).returncode,2)
        with mock.patch.object(sys,'argv',['trial','begin','--bundle','b','--manifest','m','--normal-report','n','--state','s','--log','l','--result','r','--wait-initramfs-in-initcall','--without-boot-markers','--initrd-info-logging']),mock.patch.object(t,'run',return_value=True)as run:
            self.assertEqual(t.main(),0);self.assertTrue(run.call_args.args[0].initrd_info_logging);self.assertFalse(run.call_args.args[0].initrd_debug_logging)


if __name__=='__main__':unittest.main()
