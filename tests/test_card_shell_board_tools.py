#!/usr/bin/env python3
"""Host fault injection of the actual session orchestrator; no board evidence."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
H=load('session_tools','card-shell-board-session.py')
A=load('acceptance_tools','card-shell-acceptance.py')
STORE='/nix/store/'+'a'*32
PLAN={'package':STORE+'-card-shell','normal_config':STORE+'-k230-sway.conf','client':STORE+'-client/bin/card-composition-probe-client','source_revision':'a'*40,'duration':30,'source_device':'/dev/input/event0'}
class Fake:
    def __init__(self,fail=None):
        self.tools={x:STORE+'-tools/bin/'+x for x in ('systemctl','systemd-run','journalctl','evemu-describe','evemu-device','evemu-event','sh','grim')}
        self.python=STORE+'-python/bin/python3';self.units={'shell.service':True,'seatd.service':True};self.trace=[];self.fail=fail;self.device=False;self.normal='sway -V -c '+PLAN['normal_config'];self.populated=False
    def active(self,unit):return self.units.get(unit,False)
    def sway_pids(self):return [7] if self.fail=='competitor' else ([1] if self.active('shell.service') else [2] if self.active(H.UNIT) else [])
    def prop(self,unit,name):
        return {'User':'shell','ExecStart':self.normal,'MainPID':'1' if self.active(unit) else '0','Environment':'PATH='+STORE+'-tools/bin','InvocationID':'b'*32,'Result':'signal' if self.fail=='crash' else 'success'}.get(name,'')
    def cgroup_empty(self,unit):return not (self.fail in ('lingering','stop') and unit==H.UNIT)
    def virtual_devices(self):return {'/dev/input/event9'} if self.device else set()
    def sleep(self,value):self.units[H.UNIT]=False
    def call(self,args,check=True,timeout=20):
        self.trace.append(args)
        if args[0]=='evemu-describe':return subprocess.CompletedProcess(args,0,'N: Goodix\nI: 0018 0000 0000 0000\n','')
        if args[0]=='journalctl':return subprocess.CompletedProcess(args,0,'SECRET private-url\nK230_CARD_BENCH v=1 run=1 event=input input_id=1 gesture_id=1 kind=motion source=injected t_ns=2\nK230_CARD_SHELL token=secret\n','')
        if args[:2]==['systemctl','stop']:
            if args[2]=='shell.service' and self.fail=='interrupt-stop':raise KeyboardInterrupt
            if args[2]==H.UNIT and self.fail=='stop':return subprocess.CompletedProcess(args,1,'','')
            self.units[args[2]]=False
        if args[:2]==['systemctl','start']:
            if self.fail=='restore':raise RuntimeError('restore failure')
            assert not self.active(H.UNIT);self.units[args[2]]=True
        if args[0]=='systemd-run':
            unit=next(x[7:] for x in args if x.startswith('--unit='))
            if any(x.startswith('--on-active') for x in args):
                self.units[unit+'.timer']=self.fail!='watchdog'
                assert '--timer-property=OnUnitActiveSec=5s' in args
            elif unit==H.UNIT:
                assert not self.active('shell.service')
                assert any(x.startswith('--property=ExecCondition=+') for x in args)
                assert not any('Conflicts=' in x for x in args)
                assert '--property=KillMode=control-group' in args
                self.units[unit]=True
                if self.fail=='launch':raise RuntimeError('partial launch failure')
            elif unit==H.INPUT_UNIT:
                assert any(x.startswith('--property=ExecCondition=+') for x in args)
                self.units[unit]=True;self.device=True
                if self.fail=='input':raise RuntimeError('input failure')
        return subprocess.CompletedProcess(args,0,'','')
class SessionTests(unittest.TestCase):
    def test_frame_cost_export_accepts_only_complete_numeric_rows(self):
        row='K230_CARD_SHELL frame-cost run=1 frame_id=2 total_cpu_ns=20 render_cpu_ns=10 input_cpu_ns=7'
        raw='prefix '+row+'\n'+row.replace('render_cpu_ns=10','render_cpu_ns=private-token')+'\n'+row+' secret=secret\n'+row.replace(' input_cpu_ns=7','')+'\n'
        self.assertEqual(H.normalized_journal(raw),row+'\n')
    def test_repaint_export_rejects_missing_extra_duplicate_and_nonnumeric_fields(self):
        row='K230_CARD_SHELL repaint-cost run=1 frame_id=2 render_cpu_ns=10 prepare_cpu_ns=2 build_cpu_ns=5 commit_cpu_ns=3 attempts=2 failed_attempts=1'
        rejected=[row+' secret=private',row.replace(' build_cpu_ns=5',''),
                  row.replace('build_cpu_ns=5','build_cpu_ns=private-token'),
                  row.replace('build_cpu_ns=5','prepare_cpu_ns=5'),
                  row.replace('build_cpu_ns=5','build_cpu_ns=-5')]
        self.assertEqual(H.normalized_journal('prefix '+row+'\n'+'\n'.join(rejected)),row+'\n')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='board-tools-');self.root=Path(self.temp.name);self.runtime=self.root/'run';self.runtime.mkdir()
        self.account=patch.object(H.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid(),pw_dir=str(self.root)))
        self.account.start()
    def tearDown(self):self.account.stop();self.temp.cleanup()
    def run_session(self,fail=None):
        fake=Fake(fail);session=H.Session(self.runtime,fake)
        return session,fake
    def test_success_arms_before_stop_and_cleans_both_cgroups(self):
        session,fake=self.run_session();session.execute(PLAN,self.root/'export')
        trace=fake.trace;arm=next(i for i,x in enumerate(trace) if x[0]=='systemd-run' and any('--on-active=' in y for y in x))
        stop=trace.index(['systemctl','stop','shell.service']);self.assertLess(arm,stop)
        restart=trace.index(['systemctl','start','shell.service'])
        self.assertLess(trace.index(['systemctl','stop',H.UNIT]),restart)
        self.assertLess(trace.index(['systemctl','stop',H.INPUT_UNIT]),restart)
        self.assertEqual(session.state['phase'],'restored');self.assertFalse(fake.active(H.UNIT))
        log=(self.root/'export/telemetry.log').read_text();self.assertNotIn('SECRET',log);self.assertNotIn('token',log)
    def test_pixman_policy_applies_only_to_transient_service(self):
        for policy,value in [('auto',''),('no-rvv','rvv')]:
            with self.subTest(policy=policy):
                if (self.runtime/'state.json').exists():(self.runtime/'state.json').unlink()
                session,fake=self.run_session()
                session.execute({**PLAN,'pixman_policy':policy},self.root/policy)
                starts=[x for x in fake.trace if x[0]=='systemd-run' and '--unit='+H.UNIT in x]
                self.assertEqual(len(starts),1)
                self.assertEqual([x for x in starts[0] if x.startswith('--setenv=PIXMAN_DISABLE=')],['--setenv=PIXMAN_DISABLE='+value])
                self.assertEqual(json.loads((self.root/policy/'session.json').read_text())['pixman_policy'],policy)
                self.assertTrue(fake.active('shell.service'))
                self.assertFalse(any('set-environment' in x for x in fake.trace))
    def test_invalid_pixman_policy_never_arms_or_stops_shell(self):
        session,fake=self.run_session()
        with self.assertRaises(ValueError):session.arm({**PLAN,'pixman_policy':'force-rvv'})
        self.assertEqual(fake.trace,[])
        self.assertTrue(fake.active('shell.service'))
    def test_partial_launch_and_input_failure_restore(self):
        for fail in ('launch','input','crash'):
            with self.subTest(fail=fail):
                if (self.runtime/'state.json').exists():(self.runtime/'state.json').unlink()
                session,fake=self.run_session(fail)
                with self.assertRaises(RuntimeError):session.execute(PLAN,self.root/'export')
                self.assertTrue(fake.active('shell.service'));self.assertFalse(fake.active(H.UNIT))
    def test_interrupt_during_stop_restores(self):
        session,fake=self.run_session('interrupt-stop')
        with self.assertRaises(KeyboardInterrupt):session.execute(PLAN,self.root/'export')
        self.assertTrue(fake.active('shell.service'));self.assertEqual(session.state['phase'],'restored')
    def test_watchdog_failure_never_stops_normal(self):
        session,fake=self.run_session('watchdog')
        with self.assertRaises(RuntimeError):session.execute(PLAN,self.root/'export')
        self.assertNotIn(['systemctl','stop','shell.service'],fake.trace)
    def test_restore_failure_keeps_watchdog_armed(self):
        for fail in ('restore','stop','lingering'):
            with self.subTest(fail=fail):
                if (self.runtime/'state.json').exists():(self.runtime/'state.json').unlink()
                session,fake=self.run_session(fail)
                with self.assertRaises(RuntimeError):session.execute(PLAN,self.root/'export')
                self.assertTrue(fake.active(session.state['watchdog']+'.timer'))
    def test_independent_watchdog_recovers_dead_controller(self):
        session,fake=self.run_session();token=session.arm(PLAN);session.start()
        watchdog=H.Session(self.runtime,fake);watchdog.restore(token)
        self.assertTrue(fake.active('shell.service'));self.assertFalse(session.condition(token))
        with self.assertRaises(RuntimeError):session.start()
    def test_closed_marker_survives_stale_state_writer(self):
        session,fake=self.run_session();token=session.arm(PLAN);session.start()
        H.Session(self.runtime,fake).restore(token);session.update(phase='active',closed=False)
        self.assertFalse(session.condition(token))
    def test_stale_watchdog_does_nothing(self):
        session,fake=self.run_session();session.arm(PLAN);before=len(fake.trace)
        session.restore('c'*32);self.assertEqual(before,len(fake.trace))
    def test_changed_config_and_competitor_reject(self):
        session,fake=self.run_session('competitor');token=session.arm(PLAN)
        with self.assertRaises(RuntimeError):session.start()
        self.assertFalse(any(x[0]=='systemd-run' and '--unit='+H.UNIT in x for x in fake.trace))
        fake.normal='different configuration'
        with self.assertRaises(RuntimeError):session.restore(token)
    def test_planning_is_host_only(self):
        with patch.object(H,'System',side_effect=AssertionError('device access')):
            result=H.main(['--prepare','--package',PLAN['package'],'--config',PLAN['normal_config'],'--client',PLAN['client'],'--revision',PLAN['source_revision'],'--output',str(self.root/'plan')])
        self.assertEqual(result,0);self.assertFalse(json.loads((self.root/'plan/plan.json').read_text())['board_commands_executed'])
    def test_acceptance_plan_never_opens_device(self):
        with patch.object(A.socket,'socket',side_effect=AssertionError('socket')):
            self.assertEqual(A.main(['--prepare','--output',str(self.root/'accept')]),0)
        self.assertEqual(json.loads((self.root/'accept/acceptance-plan.json').read_text())['status'],'PLANNED_ONLY')
    def test_device_name_and_virtual_origin_required(self):
        sysroot=self.root/'sys';virtual=sysroot/'devices/virtual/input/input9';virtual.mkdir(parents=True)
        (virtual/'name').write_text(H.DEVICE_NAME+'\n');event=sysroot/'class/input/event9';event.mkdir(parents=True);(event/'device').symlink_to(virtual)
        A.verify_device('/dev/input/event9',sysroot)
        (virtual/'name').write_text('Goodix Berlin Capacitive TouchScreen\n')
        with self.assertRaises(RuntimeError):A.verify_device('/dev/input/event9',sysroot)
        physical=sysroot/'devices/platform/input0';physical.mkdir(parents=True);(physical/'name').write_text(H.DEVICE_NAME)
        (event/'device').unlink();(event/'device').symlink_to(physical)
        with self.assertRaises(RuntimeError):A.verify_device('/dev/input/event9',sysroot)
    def test_exec_identity_ignores_mutable_service_process_fields(self):
        prefix='{ path='+STORE+'-sway/bin/sway ; argv[]='+STORE+'-sway/bin/sway -c '+PLAN['normal_config']+' ; ignore_errors=no ; '
        before=prefix+'start_time=[yesterday] ; stop_time=[n/a] ; pid=120 ; code=(null) ; status=0/0 }'
        stopped=prefix+'start_time=[yesterday] ; stop_time=[today] ; pid=120 ; code=exited ; status=0/0 }'
        self.assertEqual(H.exec_identity(before),H.exec_identity(stopped))
        changed=stopped.replace(PLAN['normal_config'],STORE+'-other.conf')
        self.assertNotEqual(H.exec_identity(before),H.exec_identity(changed))
        with self.assertRaises(RuntimeError):H.exec_identity('unreadable configuration')
    def test_missing_transient_unit_property_is_allowed_only_if_not_found(self):
        system=object.__new__(H.System)
        system.call=lambda args,**kw:subprocess.CompletedProcess(args,1,'not-found\n' if '--property=LoadState' in args else '','')
        self.assertEqual(system.prop(H.INPUT_UNIT,'MainPID'),'')
        with self.assertRaises(RuntimeError):system.prop('shell.service','ExecStart')
        system.call=lambda args,**kw:subprocess.CompletedProcess(args,1,'','')
        with self.assertRaises(RuntimeError):system.prop(H.INPUT_UNIT,'ControlGroup')
    def test_input_guard_rejects_late_helper(self):
        session,fake=self.run_session();token=session.arm(PLAN);session.start()
        self.assertTrue(session.condition(token,input_only=True))
        H.Session(self.runtime,fake).restore(token)
        with self.assertRaises(RuntimeError):session.input_device()
        self.assertFalse(any('--unit='+H.INPUT_UNIT in x for x in fake.trace))
    def test_offline_collect_keeps_fixed_fields_and_checks_capture_digest(self):
        source=self.root/'source';source.mkdir();output=self.root/'collected'
        pixels=b'\x89PNG\r\n\x1a\nHOST SYNTHETIC FIXTURE'
        (source/'normal.png').write_bytes(pixels)
        report={'schema':1,'status':'CAPTURED_REQUIRES_REVIEW','evidence_class':'board-injected','provenance':'injected-touch',
                'package_store_path':PLAN['package'],'source_revision':PLAN['source_revision'],'created_at':'2026-09-23T00:00:00+00:00',
                'untrusted':'secret','physical_touch':'invented-pass','cases':[{'capture':'normal.png','status':'CAPTURED_REQUIRES_VISUAL_REVIEW',
                'sha256':A.hashlib.sha256(pixels).hexdigest(),'arbitrary':'secret'}]}
        manifest={'schema':1,'environment':'board','board_model':'LILYGO T-Display-K230','ownership':'coordinator-reserved',
                  'package_store_path':PLAN['package'],'source_revision':PLAN['source_revision'],'evidence_class':'board-injected',
                  'collected_at':'2026-09-23T00:00:00+00:00','arbitrary':'secret'}
        (source/'acceptance.json').write_text(json.dumps(report));(source/'manifest.json').write_text(json.dumps(manifest))
        (source/'telemetry.log').write_text('secret text\nK230_CARD_SHELL restored focus=1 message=0\n')
        with patch.object(A.socket,'socket',side_effect=AssertionError('device access')):A.collect(source,output)
        exported=(output/'acceptance.json').read_text()
        self.assertNotIn('secret',exported);self.assertNotIn('invented',exported);self.assertEqual(json.loads(exported)['physical_touch'],'UNVERIFIED')
        self.assertEqual((output/'telemetry.log').read_text(),'K230_CARD_SHELL restored focus=1 message=0\n')
        (source/'normal.png').write_bytes(pixels+b'changed')
        with self.assertRaises(ValueError):A.collect(source,output)
    def test_acceptance_success_error_and_interruption_restore_session(self):
        injector=types.SimpleNamespace(is_symlink=lambda:False,stat=lambda:types.SimpleNamespace(st_uid=0,st_mode=0o644))
        for failure in (None,RuntimeError('failed observation'),KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                if (self.runtime/'state.json').exists():(self.runtime/'state.json').unlink()
                session,fake=self.run_session();session.arm(PLAN);session.start();session.input_device()
                receiver=types.SimpleNamespace(records=[],write_report=lambda:None)
                def run():
                    if failure:raise failure
                receiver.run=run
                with patch.object(A.module,'System',return_value=fake),patch.object(A,'verify_device'),patch.object(A,'Acceptance',return_value=receiver):
                    if failure:
                        with self.assertRaises(type(failure)):A.execute(session.state,self.runtime,injector,self.root/'export')
                    else:self.assertEqual(A.execute(session.state,self.runtime,injector,self.root/'export'),0)
                self.assertTrue(fake.active('shell.service'));self.assertFalse(fake.active(H.UNIT));self.assertFalse(fake.active(H.INPUT_UNIT))
    def test_store_paths_reject_shell_text(self):
        for value in ('/tmp/probe',PLAN['package']+';reboot',PLAN['package']+'/../evil'):
            with self.assertRaises(ValueError):H.trusted(value)

    def test_native_drag_batches_frames_and_releases_contact(self):
        packets=[]
        with patch.object(A,'verify_device') as verify, patch.object(A.os,'open',return_value=91), \
             patch.object(A.os,'close') as close, patch.object(A.time,'sleep'), \
             patch.object(A.os,'write',side_effect=lambda fd,data:packets.append(data) or len(data)):
            A.native_touch('/dev/input/event9',284,500,284,250)
        verify.assert_called_once_with('/dev/input/event9');close.assert_called_once_with(91)
        event=A.struct.Struct('@llHHi')
        frames=[[row[2:] for row in event.iter_unpack(packet)] for packet in packets]
        self.assertEqual(len(frames),22)
        self.assertTrue(all(frame[-1]==(0,0,0) for frame in frames))
        self.assertIn((3,57,7),frames[0]);self.assertIn((1,330,1),frames[0])
        self.assertIn((3,54,250*2400//1232),frames[-2])
        self.assertEqual(frames[-1],[(3,57,-1),(1,330,0),(0,0,0)])

    def test_native_failure_releases_and_closes(self):
        writes=[]
        def write(fd,data):
            writes.append(data)
            if len(writes)==2:raise OSError('injected write failure')
            return len(data)
        with patch.object(A,'verify_device'), patch.object(A.os,'open',return_value=91), \
             patch.object(A.os,'close') as close, patch.object(A.time,'sleep'), \
             patch.object(A.os,'write',side_effect=write):
            with self.assertRaises(OSError):A.native_touch('/dev/input/event9',284,500,284,250)
        close.assert_called_once_with(91)
        self.assertEqual(list(A.struct.iter_unpack('@llHHi',writes[-1]))[-2][2:],(1,330,0))

    def test_native_refuses_invalid_coordinates_before_open(self):
        with patch.object(A,'verify_device'),patch.object(A.os,'open') as opened:
            for point in ((-1,20),(568,20),(20,1232)):
                with self.assertRaises(ValueError):A.native_touch('/dev/input/event9',*point)
            opened.assert_not_called()

    def test_throw_waits_for_new_mirror_of_close_fixture(self):
        fixture=object.__new__(A.Acceptance)
        fixture.apps=lambda:[{'app_id':'k230.card.one','id':7},{'app_id':'k230.card.two','id':9}]
        old='00:00:04.664 [INFO] [sway/card_shell.c:276] K230_CARD_SHELL mirror id=7 format=34325258 width=520 height=1040 stride=2080\n'
        other='00:00:04.666 [INFO] [sway/card_shell.c:276] K230_CARD_SHELL mirror id=9 format=34325258 width=520 height=1040 stride=2080\n'
        new='00:00:12.529 [INFO] [sway/card_shell.c:276] K230_CARD_SHELL mirror id=7 format=34325258 width=520 height=1040 stride=2080\n'
        journals=iter([old,other+old,new+other+old])  # journal may be newest first
        fixture.journal=lambda:next(journals)
        commands=[]
        fixture.ipc=lambda command:commands.append(command)
        observed=[]
        def wait(predicate,timeout):
            self.assertEqual(timeout,3)
            for _ in range(2):observed.append(predicate())
            return observed[-1]
        fixture.wait=wait
        fixture.restore_live_before_throw()
        self.assertEqual(observed,[False,True])
        self.assertEqual(commands,['[app_id="k230.card.one"] unmark k230_card_unavailable'])

    def test_throw_setup_fails_if_live_mirror_never_arrives(self):
        fixture=object.__new__(A.Acceptance)
        fixture.apps=lambda:[{'app_id':'k230.card.one','id':7}]
        fixture.journal=lambda:'00:00:04.664 [INFO] [sway/card_shell.c:276] K230_CARD_SHELL mirror id=7 format=34325258 width=520 height=1040 stride=2080\n'
        commands=[]
        fixture.ipc=lambda command:commands.append(command)
        fixture.wait=lambda predicate,timeout:predicate()
        with self.assertRaisesRegex(RuntimeError,'did not become live before throw'):
            fixture.restore_live_before_throw()
        self.assertEqual(len(commands),1)
if __name__=='__main__':unittest.main()
