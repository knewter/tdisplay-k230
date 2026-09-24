"""Host lifecycle tests of the bounded normal-service broker trial."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[2]/'tools/vglite-normal-service-trial.py'
spec=importlib.util.spec_from_file_location('normal_trial',SOURCE)
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)


class Manager:
    def __init__(self):
        self.events=[];self.units={'shell.service','seatd.service'}
        self.normal='path=/nix/store/normal/bin/sway; argv[]=/nix/store/normal/bin/sway -V -c /nix/store/config; ignore_errors=no; start_time=[now];'
    def active(self,unit):return unit in self.units
    def prop(self,unit,key):
        if key=='User':return 'shell'
        if key=='ExecStart':return self.normal.replace('start_time=[now]','start_time=[later]')
        if key=='MainPID':return '777'
        raise AssertionError((unit,key))
    def call(self,args,**kwargs):
        self.events.append(args)
        if args[0]=='systemd-run':
            name=next(x.split('=',1)[1] for x in args if x.startswith('--unit='))
            self.units.add(name+'.timer')
        if args[:2]==['systemctl','start']:
            self.units.update(args[2:])
        if args[:2]==['systemctl','stop']:
            self.units.difference_update(args[2:])
        return ''


class NormalServiceTrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='vglite-normal-trial-')
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.paths=[base/'dropin.conf',base/'broker.socket',base/'broker.service']
        patches=[patch.object(T,'DROPIN',self.paths[0]),patch.object(T,'SOCKET_UNIT',self.paths[1]),
                 patch.object(T,'BROKER_UNIT',self.paths[2]),patch.object(T,'OUTPUT',__import__('re').compile(str(base/'out'))),
                 patch.object(T,'RESTORE_LOCK',base/'restore.lock'),
                 patch.object(T,'store_file',side_effect=lambda value:Path(value))]
        for item in patches:item.start();self.addCleanup(item.stop)
        self.manager=Manager()
        for name in ('wrapper','unwrapped','broker','python','config'):
            (base/name).write_text(name)
        self.manager.normal=self.manager.normal.replace('/nix/store/config',str(base/'config'))
        self.trial=T.Trial(base/'out',base/'wrapper',base/'unwrapped',base/'broker',
                           base/'python',base/'config',30,self.manager)

    def test_watchdog_arms_before_unit_mutation_and_restores_original(self):
        original=self.trial.preflight()
        self.trial.prepare(original)
        self.assertTrue(self.manager.active(self.trial.watchdog+'.timer'))
        self.assertFalse(any(path.exists() for path in self.paths))
        self.trial.install()
        self.assertEqual(self.manager.events[0][0],'systemd-run')
        self.assertEqual(self.manager.events[0][-5:],
                         ['--restore','--output',str(self.trial.output),'--token',self.trial.token])
        self.assertIn('CapabilityBoundingSet=CAP_SYS_PTRACE',self.paths[2].read_text())
        self.assertIn('ExecStart='+str(self.trial.wrapper)+' -V -c '+str(self.trial.config),self.paths[0].read_text())
        self.assertIn('WLR_RENDERER=vglite',self.paths[0].read_text())
        with patch.object(T.os,'geteuid',return_value=0),\
             patch.object(T.platform,'machine',return_value='riscv64'),\
             patch.object(T,'System',return_value=self.manager):
            self.assertEqual(T.main(['--restore','--output',str(self.trial.output),
                                     '--token',self.trial.token]),0)
        self.assertTrue(self.manager.active('shell.service'))
        self.assertTrue(self.manager.active('seatd.service'))
        self.assertFalse(any(path.exists() for path in self.paths))
        self.assertEqual(json.loads((self.trial.output/'state.json').read_text())['phase'],'restored')

    def test_stale_token_cannot_remove_newer_trial_units(self):
        self.trial.prepare(self.manager.normal);self.trial.install()
        T.restore(self.trial.output,'wrong-token',self.manager)
        self.assertTrue(all(path.exists() for path in self.paths))
        self.assertFalse(any(args[:2]==['systemctl','stop'] for args in self.manager.events))

    def test_foreign_unit_blocks_restoration_before_stopping_shell(self):
        self.trial.prepare(self.manager.normal);self.trial.install()
        self.paths[0].write_text('# another owner\n')
        with self.assertRaisesRegex(RuntimeError,'different trial owns'):
            T.restore(self.trial.output,self.trial.token,self.manager)
        self.assertTrue(self.manager.active('shell.service'))

    def test_failed_setup_before_unit_install_leaves_normal_shell_running(self):
        self.trial.prepare(self.manager.normal)
        T.restore(self.trial.output,self.trial.token,self.manager)
        self.assertTrue(self.manager.active('shell.service'))
        self.assertFalse(any(args[:2]==['systemctl','stop'] and 'shell.service' in args
                             for args in self.manager.events))

    def test_partial_unit_install_is_token_cleaned(self):
        self.trial.prepare(self.manager.normal)
        real=T.owned_text
        calls=[]
        def fail_second(path,token,body):
            calls.append(path)
            if len(calls)==2:raise RuntimeError('injected unit write failure')
            return real(path,token,body)
        with patch.object(T,'owned_text',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'injected unit'):
                self.trial.install()
        T.restore(self.trial.output,self.trial.token,self.manager)
        self.assertFalse(any(path.exists() for path in self.paths))
        self.assertTrue(self.manager.active('shell.service'))

    def test_exec_identity_ignores_runtime_pid_fields(self):
        self.assertEqual(T.exec_identity(self.manager.normal),T.exec_identity(self.manager.prop('shell.service','ExecStart')))

    def test_forced_pixman_is_same_broker_renderer_with_cache_gate_off(self):
        self.trial.force_pixman=True
        self.trial.prepare(self.manager.normal);self.trial.install()
        text=self.paths[0].read_text()
        self.assertIn('WLR_RENDERER=vglite',text)
        self.assertIn('K230_VGLITE_ALLOW_UNPROVEN_CACHE=0',text)
        self.assertEqual(json.loads((self.trial.output/'state.json').read_text())['forced_pixman'],True)

    def test_preflight_failure_never_mutates_services(self):
        self.manager.units.remove('seatd.service')
        with self.assertRaisesRegex(RuntimeError,'normal shell and seatd'):
            self.trial.preflight()
        self.assertEqual(self.manager.events,[])
        self.assertFalse(self.trial.output.exists())


if __name__=='__main__':unittest.main()
