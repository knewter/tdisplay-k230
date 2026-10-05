"""Fixed info/kmsg selection; shared verbose-pump fixtures remain in debug tests."""
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

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('info_logging_fixtures',ROOT/'tests/test_mainline_initrd_info_logging.py')
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)
t,f,d=i.t,i.f,i.d


def selected(system=d.SYSTEM,original=d.ORIGINAL):
    return t.ordinary_bootargs(original,system,wait_initramfs_in_initcall=True,
                              without_boot_markers=True,initrd_info_kmsg_logging=True)


def prepared():
    p=i.prepared();p.pop('initrd_info_logging');p['initrd_info_kmsg_logging']=True
    p['bootargs']=p['bootargs'].replace('rd.systemd.log_target=console','rd.systemd.log_target=kmsg')
    p['diagnostic_controls']=t.diagnostic_controls(True,without_boot_markers=True,initrd_info_kmsg_logging=True)
    return p


def args_at(root,**changes):
    args=i.args_at(root,initrd_info_logging=False,initrd_info_kmsg_logging=True)
    for k,v in changes.items():setattr(args,k,v)
    return args


def session_for(p):
    class Session(f.FlowSession):
        def command(self,command,timeout):
            if command=='printenv bootargs':self.writes.append(command.encode());return(p['bootargs']+'\nK230# ').encode()
            return super().command(command,timeout)
    return Session


class KmsgTests(unittest.TestCase):
    def test_one_value_352_arguments_370_transport_and_old_profiles_unchanged(self):
        console=i.selected();kmsg=selected()
        self.assertEqual(kmsg,console.replace('rd.systemd.log_target=console','rd.systemd.log_target=kmsg'))
        self.assertEqual(sum(a!=b for a,b in zip(console.split(),kmsg.split())),1)
        self.assertEqual(len(kmsg.removeprefix('bootargs=').encode()),352)
        p=prepared();actual_p=p|{'bootargs':kmsg}
        self.assertEqual(t.volatile_bootargs_command(actual_p),'setenv bootargs "'+kmsg.removeprefix('bootargs=')+'"')
        self.assertEqual(len(t.volatile_bootargs_command(actual_p).encode()),370)
        for wait,without,debug,info in ((False,False,False,False),(True,False,False,False),(True,True,False,False),(True,True,True,False),(True,True,False,True)):
            modes=dict(wait_initramfs_in_initcall=wait,without_boot_markers=without,initrd_debug_logging=debug,initrd_info_logging=info)
            self.assertEqual(t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**modes),t.ordinary_bootargs(d.ORIGINAL,d.SYSTEM,**modes,initrd_info_kmsg_logging=False))
        self.assertEqual(t.initrd_logging_controls(info_kmsg=True),t.INITRD_INFO_KMSG_LOGGING)

    def test_all_unaffected_bodies_AST_equal_to_reviewed_base(self):
        source=subprocess.run(['git','show','b90a5318:tools/mainline-drm-system-trial.py'],cwd=ROOT,check=True,text=True,capture_output=True).stdout
        def functions(src):return{n.name:ast.dump(n,include_attributes=False)for n in ast.parse(src).body if isinstance(n,ast.FunctionDef)}
        old,new=functions(source),functions(Path(t.__file__).read_text())
        changed={'initrd_logging_controls','diagnostic_controls','ordinary_bootargs','prepare','volatile_bootargs_command','run','main'}
        for name in old.keys()-changed:self.assertEqual(new[name],old[name],name)

    def test_types_dependencies_phases_and_other_modes_fail_before_preparation_output_UART(self):
        baseline=dict(phase='begin',wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_info_kmsg_logging=True)
        changes=[{'initrd_info_kmsg_logging':v}for v in (None,0,1,'false')]
        changes += [{'phase':phase}for phase in ('touch','finish','survey')]
        changes += [{key:v}for key in ('wait_initramfs_in_initcall','without_boot_markers')for v in (False,None,1,'true')]
        changes += [{key:v}for key in ('initrd_debug_logging','initrd_info_logging')for v in (True,None,1,'false')]
        for change in changes:
            with mock.patch.object(t,'prepare')as prepare,mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as session:
                with self.assertRaises(ValueError):t.run(SimpleNamespace(**(baseline|change)))
                prepare.assert_not_called();output.assert_not_called();session.assert_not_called()

    def test_inherited_plain_rd_aliases_and_conflicts_fail_before_output_UART(self):
        aliases=[prefix+'systemd.'+key for prefix in ('','rd.')for key in ('log_level','log-level','log_target','log-target')]
        aliases+=['rd.debug','rd.quiet','rd.systemd.debug-shell','systemd.unit','rd.systemd.mask','rd.udev.log-level',
                  'systemd.journald.forward-to-console','k230.uart_progress','nohlt','nohz','initcall-debug','clk-ignore-unused']
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);args=args_at(root,bundle=root)
            for name in aliases:
                for suffix in ('','=info','=kmsg','=console','=bad'):
                    (root/'bootargs.txt').write_text(d.ORIGINAL.rstrip()+' '+name+suffix+'\n')
                    with mock.patch.object(t.rd,'prepare_trial',return_value={'system':d.SYSTEM}),mock.patch.object(t.rd,'safe_log_path')as output,mock.patch.object(t.rd,'PrivateSession')as session:
                        with self.assertRaises(ValueError):t.run(args)
                        output.assert_not_called();session.assert_not_called()

    def test_exact_literal_and_live_cmdline_reject_missing_alias_duplicate_or_changed_values(self):
        p=prepared();args=p['bootargs'];facts=f.facts()['bootargs']|{'cmdline':args.removeprefix('bootargs=')}
        t.validate_stage('bootargs',facts,p,p['normal'])
        for changed in (args.replace('=kmsg','=console'),args.replace('=info','=debug'),args.replace('log_target','log-target'),
                        args+' rd.systemd.log_target=kmsg',args.replace(' rd.systemd.log_target=kmsg','')):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'bootargs':changed})
            with self.assertRaises(t.Unknown):t.validate_stage('bootargs',facts|{'cmdline':changed.removeprefix('bootargs=')},p,p['normal'])
        for changed in (args+' $x',args+';saveenv',args+'\n',args+' '+'a'*512):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|{'bootargs':changed})
        for changes in ({'initrd_info_logging':True},{'initrd_debug_logging':True},{'initrd_info_kmsg_logging':'false'},
                        {'without_boot_markers':False},{'diagnostic_controls':t.diagnostic_controls(True)}):
            with self.assertRaises(ValueError):t.volatile_bootargs_command(p|changes)

    def test_prepare_retains_artifacts_helper_and_default_console_modes(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);(root/'bootargs.txt').write_text(d.ORIGINAL)
            original={'system':d.SYSTEM,'helper_text':'fixture helper','normal':{'fixture':True},'manifest':{'fixture':True}}
            with mock.patch.object(t.rd,'prepare_trial',side_effect=lambda*a:dict(original)),mock.patch.object(t.os,'access',return_value=True):
                console=t.prepare(root,root/'m',root/'n',wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_info_logging=True)
                kmsg=t.prepare(root,root/'m',root/'n',wait_initramfs_in_initcall=True,without_boot_markers=True,initrd_info_kmsg_logging=True)
                base=t.prepare(root,root/'m',root/'n')
            for name in ('system','helper_text','normal','manifest','kernel','pid1'):self.assertEqual(kmsg[name],console[name])
            self.assertEqual(kmsg['bootargs'],console['bootargs'].replace('rd.systemd.log_target=console','rd.systemd.log_target=kmsg'))
            self.assertNotIn('initrd_info_kmsg_logging',console);self.assertNotIn('initrd_info_kmsg_logging',base)
            self.assertNotIn('initrd_info_logging',kmsg);self.assertTrue(kmsg['initrd_info_kmsg_logging'])

    def test_mocked_begin_finish_typed_saved_resume_old_default_and_bad_state(self):
        p=prepared();facts=f.facts();facts['bootargs']['cmdline']=p['bootargs'].removeprefix('bootargs=')
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);root.chmod(0o700);args=args_at(root);Session=session_for(p)
            f.FlowSession.values=facts;f.FlowSession.fail_stage=None
            try:
                with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p)as call,mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'):
                    self.assertTrue(t.run(args));state=json.loads(args.state.read_text());self.assertTrue(state['initrd_info_kmsg_logging'])
                    self.assertFalse(state['initrd_debug_logging']);self.assertFalse(state['initrd_info_logging'])
                    args.phase='finish';args.log=root/'finish.log';args.result=root/'finish.result';args.initrd_info_kmsg_logging=False;args.wait_initramfs_in_initcall=False;args.without_boot_markers=False
                    self.assertTrue(t.run(args));self.assertTrue(call.call_args.kwargs['initrd_info_kmsg_logging'])
                    self.assertTrue(json.loads(args.result.read_text())['initrd_info_kmsg_logging'])
            finally:f.FlowSession.values=None
            for phase in ('touch','finish'):
                args.phase=phase;args.real_touch=phase=='touch';state['status']='candidate-ready';args.state.write_text(json.dumps(state))
                with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop'))as call:
                    with self.assertRaises(ValueError):t.run(args)
                self.assertTrue(call.call_args.kwargs['initrd_info_kmsg_logging'])
            state.pop('initrd_info_kmsg_logging');args.state.write_text(json.dumps(state))
            with mock.patch.object(t,'prepare',side_effect=ValueError('fixture stop'))as call:
                with self.assertRaises(ValueError):t.run(args)
            self.assertNotIn('initrd_info_kmsg_logging',call.call_args.kwargs)
            for field,value in (('initrd_info_kmsg_logging','false'),('initrd_debug_logging',True),('initrd_info_logging',True)):
                bad=state|{'initrd_info_kmsg_logging':True,field:value};args.state.write_text(json.dumps(bad))
                with mock.patch.object(t,'prepare')as call,mock.patch.object(t.rd,'safe_log_path')as paths,mock.patch.object(t.rd,'PrivateSession')as session:
                    with self.assertRaises(ValueError):t.run(args)
                    call.assert_not_called();paths.assert_not_called();session.assert_not_called()

    def test_unknown_run_no_postboot_input_preserves_kmsg_selection(self):
        p=prepared();Session=session_for(p)
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);root.chmod(0o700);args=args_at(root)
            with mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}),mock.patch.object(t,'prepare',return_value=p),mock.patch.object(t.rd,'PrivateSession',Session),mock.patch.object(t.rd,'LOCK_PATH',root/'lock'),mock.patch.object(t,'wait_candidate',side_effect=OSError('fixture unknown read')),mock.patch('sys.stderr'):
                self.assertFalse(t.run(args))
            wire=Session.instances[-1]
            self.assertEqual(sum(w.startswith(b'ext4load')for w in wire.writes),5)
            self.assertEqual(sum(w.startswith(b'crc32')for w in wire.writes),5)
            self.assertEqual(wire.writes[-1],b'bootm 0x8000000 0x9000000 0x8400000\r')
            result=json.loads(args.result.read_text());self.assertTrue(result['initrd_info_kmsg_logging']);self.assertIsNone(result['normal_recovery']);self.assertFalse(args.state.exists())

    def test_CLI_begin_dependencies_and_logging_exclusion(self):
        parents=['--wait-initramfs-in-initcall','--without-boot-markers']
        for phase,flags in (('finish',[]),('touch',[]),('begin',[]),('begin',parents[:1]),
                            ('begin',parents+['--initrd-debug-logging']),('begin',parents+['--initrd-info-logging'])):
            argv=[sys.executable,str(Path(t.__file__)),phase,'--initrd-info-kmsg-logging','--state','/missing/s','--log','/missing/l','--result','/missing/r',*flags]
            if phase=='begin':argv+=['--bundle','/missing/b','--manifest','/missing/m','--normal-report','/missing/n']
            self.assertEqual(subprocess.run(argv,capture_output=True).returncode,2)
        with mock.patch.object(sys,'argv',['trial','begin','--bundle','b','--manifest','m','--normal-report','n','--state','s','--log','l','--result','r',*parents,'--initrd-info-kmsg-logging']),mock.patch.object(t,'run',return_value=True)as run:
            self.assertEqual(t.main(),0);self.assertTrue(run.call_args.args[0].initrd_info_kmsg_logging)
            self.assertFalse(run.call_args.args[0].initrd_info_logging);self.assertFalse(run.call_args.args[0].initrd_debug_logging)


if __name__=='__main__':unittest.main()
