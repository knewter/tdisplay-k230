#!/usr/bin/env python3
"""Plan, execute, or collect product card acceptance. Execution uses verified uinput, never test-touch."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('card_session',HERE/'card-shell-board-session.py')
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
CAPTURES = ('normal','one-live','two-live','during-drag','expanded','private','unavailable','closing','close-timeout','close-exit','cards-back','apps','help','help-back','terminal','monitor','windows','home','keyboard','system','system-back')


def plan():
    return {'schema':1,'status':'PLANNED_ONLY','evidence_class':'no-device-access',
            'provenance':'injected-touch','panel_requested':[568,1232],'renderer_requested':'pixman',
            'format_requested':'RGB565','steps':list(CAPTURES),
            'benchmark_workloads':[1,2],'baseline_and_restored_seconds':3.2,
            'injection':'single-process native input_event writes to a verified virtual input device',
            'physical_touch':'UNVERIFIED','visual_acceptance':'requires captured board artifacts and separate review'}


def verify_device(device, sysroot=Path('/sys')):
    if not re.fullmatch(r'/dev/input/event[0-9]+',device or ''):
        raise ValueError('expected a specific input event device')
    path=sysroot/'class/input'/Path(device).name/'device/name'
    if path.read_text().strip()!=module.DEVICE_NAME:
        raise RuntimeError('input device is not the distinctly named injected fixture')
    if not str(path.resolve()).startswith(str(sysroot/'devices/virtual/input')+'/'):
        raise RuntimeError('refusing injection into a non-virtual input device')


def native_touch(device, x, y, x2=None, y2=None, held=None):
    """Write Linux input_event packets; kernel timestamps remain authoritative.

    One write per SYN frame avoids starting five evemu processes per movement.
    Absolute deadlines avoid accumulating process/sleep overhead. This is still
    software input, not physical touch or a guaranteed delivery rate.
    """
    verify_device(device)
    points=[(x,y)] if x2 is None else [(x,y),(x2,y2)]
    if any(not (0<=px<568 and 0<=py<1232) for px,py in points):
        raise ValueError('touch coordinates outside native panel')
    event=struct.Struct('@llHHi')
    def position(px,py):
        dx=px*1024//568;dy=py*2400//1232
        return [(3,53,dx),(3,54,dy),(3,0,dx),(3,1,dy)]
    fd=os.open(device,os.O_WRONLY|os.O_CLOEXEC)
    def frame(events):
        packet=b''.join(event.pack(0,0,*values) for values in [*events,(0,0,0)])
        if os.write(fd,packet)!=len(packet):raise OSError('short input-event write')
    try:
        frame([(3,47,0),(3,57,7),(3,48,3),(1,330,1),*position(x,y)])
        start=time.monotonic()
        if x2 is None:time.sleep(.08)
        else:
            for i in range(1,21):
                time.sleep(max(0,start+i*.01-time.monotonic()))
                frame(position(x+(x2-x)*i//20,y+(y2-y)*i//20))
        if held:held()
    finally:
        try:frame([(3,57,-1),(1,330,0)])
        finally:os.close(fd)


CLIENT_EVENTS={'start','commit','child_commit','configure','close_requested','close_refused','close_accepted',
               'keyboard_enter','keyboard_leave','key_press','connect_failed','protocol_missing','heartbeat',
               'connection_error','signal_exit','exit'}
CLIENT_COUNTS={'elapsed_ms','frames','callbacks','releases','child_frames','child_callbacks','child_releases',
               'callback_age_ms','child_callback_age_ms','max_callback_gap_ms','child_max_callback_gap_ms',
               'width','height','stride','key_presses'}

def client_export(rows,name):
    clean=[]
    for row in rows[:10000]:
        if row.get('app_id')!='k230.card.'+name or row.get('event') not in CLIENT_EVENTS:
            raise ValueError('unknown client observation')
        item={'event':row['event'],'app_id':row['app_id']}
        for key in CLIENT_COUNTS:
            if key in row:
                if type(row[key])!=int or row[key]<0:raise ValueError('invalid client counter')
                item[key]=row[key]
        clean.append(json.dumps(item))
    return '\n'.join(clean)+('\n' if clean else '')


def nodes(tree):
    yield tree
    for item in tree.get('nodes',[])+tree.get('floating_nodes',[]):
        yield from nodes(item)


class Acceptance:
    def __init__(self,state,runtime,injector,output):
        self.state=state;self.runtime=runtime;self.session=runtime/'wayland'
        self.injector=injector;self.output=output;self.records=[]
        self.system=module.System(state)
        self.environment=dict(os.environ,PATH=str(Path(state['tools']['evemu-event']).parent)+':'+state['dependency_path'],XDG_RUNTIME_DIR=str(self.session),
                              SWAYSOCK=str(self.session/'sway-ipc.sock'))
        displays=[p.name for p in self.session.glob('wayland-*') if p.is_socket()]
        if len(displays)!=1: raise RuntimeError('expected exactly one product Wayland display')
        self.environment['WAYLAND_DISPLAY']=displays[0]
        self.capture_dir=self.session/'captures';self.capture_dir.mkdir(mode=0o700,exist_ok=True)
        self.account=pwd.getpwnam('shell');os.chown(self.capture_dir,self.account.pw_uid,self.account.pw_gid)

    def ipc(self,command='',kind=0):
        payload=command.encode()
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(15);sock.connect(self.environment['SWAYSOCK'])
            sock.sendall(b'i3-ipc'+struct.pack('=II',len(payload),kind)+payload)
            def read(length):
                value=b''
                while len(value)<length:
                    part=sock.recv(length-len(value))
                    if not part: raise RuntimeError('compositor IPC closed')
                    value+=part
                return value
            header=read(14)
            if header[:6]!=b'i3-ipc':raise RuntimeError('invalid IPC header')
            length,_=struct.unpack('=II',header[6:])
            if length>8*1024*1024:raise RuntimeError('IPC reply exceeds evidence bound')
            result=json.loads(read(length))
        if kind==0 and not all(row.get('success') for row in result):
            raise RuntimeError('compositor command rejected')
        return result

    def wait(self,predicate,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if predicate():return True
            time.sleep(.1)
        return False

    def apps(self):
        return [n for n in nodes(self.ipc(kind=4)) if n.get('app_id')]

    def focused(self):
        return next((n['app_id'] for n in self.apps() if n.get('focused')),None)

    def check(self,name,passed):
        self.records.append({'case':name,'status':'OBSERVED' if passed else 'FAILED','monotonic_ns':time.monotonic_ns()})
        return passed

    def capture(self,name):
        if name not in CAPTURES:raise ValueError('unknown capture step')
        path=self.capture_dir/(name+'.png')
        subprocess.run([self.state['tools']['grim'],str(path)],env=self.environment,
                       user=self.account.pw_uid,group=self.account.pw_gid,extra_groups=[],check=True,timeout=15)
        self.output.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,self.output/path.name)
        self.records.append({'capture':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                             'status':'CAPTURED_REQUIRES_VISUAL_REVIEW','monotonic_ns':time.monotonic_ns()})

    def inject(self,x,y,x2=None,y2=None,capture=None,settle=1.5,held=None):
        if self.injector is None:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(native_touch,self.state['device'],x,y,x2,y2,held)
                if capture:
                    time.sleep(.1);self.capture(capture)
                future.result(timeout=20)
            time.sleep(settle)
            return
        if held:raise RuntimeError('legacy injector cannot prove held live surfaces')
        args=[self.state['tools']['sh'],str(self.injector),self.state['device'],str(x),str(y)]
        if x2 is not None:args.extend([str(x2),str(y2)])
        process=subprocess.Popen(args,env=self.environment,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            if capture:
                time.sleep(.15);self.capture(capture)
            if process.wait(timeout=20):raise RuntimeError('uinput injection failed')
        finally:
            if process.poll() is None:process.kill();process.wait()
        time.sleep(settle)

    def client_events(self,name):
        path=self.session/('client-'+name+'.jsonl')
        if not path.exists():return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]

    def frames(self,name):
        values=self.client_events(name)
        return (values[-1].get('frames',0),values[-1].get('child_frames',0)) if values else (0,0)

    def spawn(self,name,refuse=False):
        app='k230.card.'+name
        command=self.state['client']+' --app-id '+app+' --duration '+str(self.state['duration'])
        if refuse:command+=' --refuse-close'
        self.ipc('exec '+command+' > '+str(self.session/('client-'+name+'.jsonl')))
        if not self.wait(lambda:any(n['app_id']==app for n in self.apps())):
            raise RuntimeError('synthetic client did not map')

    def benchmark(self,count):
        self.ipc('card_shell benchmark injected');time.sleep(3.2)
        self.inject(284,1210,284,1090)
        def live():
            # Halfway between cards exposes both parent/child surfaces. Merely
            # peeking an adjacent border does not make its client visible.
            names=('one',) if count==1 else ('one','two')
            before={name:self.frames(name) for name in names}
            for name in names:
                self.check('live-root-and-child-'+str(count)+'-'+name,
                           self.wait(lambda:all(b>a for a,b in zip(before[name],self.frames(name))),2.5))
            self.capture('one-live' if count==1 else 'two-live')
        if count==1:live()
        else:self.inject(284,450,114,450,held=live,settle=.3)
        if count==2:self.inject(100,1200,settle=.3)
        # Fast native input is coalesced by the compositor. Collect enough
        # independent submitted frames and tracking intervals for the fixed
        # benchmark coverage minima; input-event count alone is insufficient.
        for index in range(24):
            start,end=(384,184) if index%2==0 else (184,384)
            self.inject(start,450,end,450,capture='during-drag' if count==2 and index==0 else None,settle=.3)
        self.inject(284,450)
        if count==2:self.capture('expanded')
        time.sleep(3.2);self.ipc('card_shell benchmark-stop')

    def journal(self):
        return self.system.call(['journalctl','_SYSTEMD_INVOCATION_ID='+self.state['invocation'],
                                 '--no-pager','-o','cat','--grep=K230_CARD_(BENCH|SHELL)','-n','20000']).stdout

    def live_mirror_count(self, card_id):
        # A new mirror for this exact card proves the compositor has applied
        # its unavailable-to-live classification. Count works regardless of
        # journal output order and excludes old mirrors from prior workloads.
        prefix=f'K230_CARD_SHELL mirror id={card_id} '
        return sum(line.startswith(prefix) for line in module.normalized_journal(self.journal()).splitlines())

    def restore_live_before_throw(self):
        one=[node for node in self.apps() if node['app_id']=='k230.card.one']
        if len(one)!=1:raise RuntimeError('close fixture card is not uniquely mapped')
        card_id=one[0]['id']
        prior_mirrors=self.live_mirror_count(card_id)
        self.ipc('[app_id="k230.card.one"] unmark k230_card_unavailable')
        if not self.wait(lambda:self.live_mirror_count(card_id)>prior_mirrors,3):
            raise RuntimeError('close fixture card did not become live before throw')

    def run(self):
        outputs=[o for o in self.ipc(kind=3) if o.get('active')]
        if len(outputs)!=1 or outputs[0].get('name')!='DSI-1' or outputs[0]['rect']['width']!=568 or outputs[0]['rect']['height']!=1232 or outputs[0].get('scale')!=1:
            raise RuntimeError('product output is not the native scale-one panel')
        self.capture('normal')
        existing=self.apps()
        if any(n['app_id']!='k230-terminal' for n in existing):
            raise RuntimeError('unexpected startup apps: refusing to close non-fixture work')
        for node in existing:self.ipc('[con_id='+str(node['id'])+'] kill')
        if not self.wait(lambda:not self.apps()):raise RuntimeError('fresh startup terminal did not close')
        self.spawn('one',True);self.benchmark(1)
        self.spawn('two');self.ipc('[app_id="k230.card.one"] focus');self.benchmark(2)
        self.check('actual-rgb565-pixman-session','backend=drm renderer=pixman width=568 height=1232 output_format=RGB565 input=injected' in self.journal())
        self.ipc('[app_id="k230.card.one"] focus');self.inject(480,90)
        self.ipc('[app_id="k230.card.one"] mark --add k230_card_private');time.sleep(.3);self.capture('private')
        self.ipc('[app_id="k230.card.one"] mark --add k230_card_unavailable')
        self.ipc('[app_id="k230.card.one"] unmark k230_card_private');time.sleep(.3);self.capture('unavailable')
        self.restore_live_before_throw()
        self.inject(284,500,284,250);self.capture('closing')
        requested=self.wait(lambda:any(e.get('event')=='close_requested' for e in self.client_events('one')),3)
        self.check('upward-throw-close-request',requested)
        if not requested:
            self.inject(440,1200)  # Independently test the persistent Close route.
        self.check('client-explicit-refusal',self.wait(lambda:any(e.get('event')=='close_refused' for e in self.client_events('one')),3))
        time.sleep(1.7);self.capture('close-timeout')
        self.check('separate-timeout-card-retained','message=6' in self.journal() and any(n['app_id']=='k230.card.one' for n in self.apps()))
        self.inject(284,1200);self.inject(440,1200)
        self.check('accepted-close-source-exits',self.wait(lambda:all(n['app_id']!='k230.card.two' for n in self.apps())))
        self.capture('close-exit');self.inject(480,90);self.capture('cards-back')
        # End our deliberately close-refusing fixture before normal controls.
        # Otherwise its floating window can obscure a correctly focused tiled
        # terminal. Verify both executable and owner before terminating it.
        for node in self.apps():
            if node['app_id']!='k230.card.one':continue
            process=Path('/proc')/str(node['pid'])
            if process.stat().st_uid!=self.account.pw_uid or (process/'exe').resolve()!=Path(self.state['client']).resolve():
                raise RuntimeError('refusing cleanup of an unrecognized fixture process')
            os.kill(node['pid'],signal.SIGTERM)
        if not self.wait(lambda:all(n['app_id']!='k230.card.one' for n in self.apps())):
            raise RuntimeError('refusing fixture remained over normal controls')
        # Existing controls are exercised by panel-coordinate uinput only.
        self.inject(120,28);self.capture('apps');self.inject(284,1000);self.capture('help')
        self.inject(284,1165);self.capture('help-back');self.inject(284,300)
        self.check('terminal-route',self.wait(lambda:self.focused()=='k230-terminal'));self.capture('terminal')
        self.inject(120,28);self.inject(284,550)
        self.check('monitor-route',self.wait(lambda:self.focused()=='k230-monitor'));self.capture('monitor')
        self.inject(480,90);self.inject(248,28);self.capture('windows');self.inject(298,28)
        self.check('windows-home-route',self.wait(lambda:self.focused()=='k230-terminal'));self.capture('home')
        before=max(w['rect']['height'] for w in self.ipc(kind=1))
        self.inject(376,28);self.capture('keyboard')
        after=max(w['rect']['height'] for w in self.ipc(kind=1));self.check('keyboard-reserves-content',after<before)
        self.inject(376,28);self.inject(480,90);self.inject(504,28);self.capture('system')
        self.inject(479,28);self.capture('system-back')
        self.check('normal-controls-recover-focus',self.focused()=='k230-terminal')
        self.write_report()

    def write_report(self):
        self.output.mkdir(parents=True,exist_ok=True)
        module.atomic_json(self.output/'acceptance.json',{'schema':1,'status':'FAILED' if any(x.get('status')=='FAILED' for x in self.records) else 'CAPTURED_REQUIRES_REVIEW',
          'evidence_class':'board-injected','provenance':'injected-touch','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
          'package_store_path':self.state['package'],'source_revision':self.state['source_revision'],'cases':self.records,
          'physical_touch':'UNVERIFIED','optical_latency':'UNVERIFIED','visual_privacy_and_control_review':'REQUIRED'})
        module.atomic_json(self.output/'manifest.json',{'schema':1,'environment':'board','board_model':'LILYGO T-Display-K230',
          'ownership':'coordinator-reserved','source_revision':self.state['source_revision'],'package_store_path':self.state['package'],
          'evidence_class':'board-injected','collected_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        for name in ('one','two'):
            (self.output/('client-'+name+'.jsonl')).write_text(client_export(self.client_events(name),name))
        (self.output/'telemetry.log').write_text(module.normalized_journal(self.journal()))


CASE_NAMES = {'live-root-and-child-1-one','live-root-and-child-2-one','live-root-and-child-2-two','actual-rgb565-pixman-session',
              'upward-throw-close-request','client-explicit-refusal','separate-timeout-card-retained',
              'accepted-close-source-exits','terminal-route','monitor-route','windows-home-route',
              'keyboard-reserves-content','normal-controls-recover-focus','interrupted-or-failed'}


def collect(source,output):
    """Offline named export; retain observations, never upgrade them to acceptance."""
    report=json.loads((source/'acceptance.json').read_text())
    manifest=json.loads((source/'manifest.json').read_text())
    if report.get('schema')!=1 or report.get('evidence_class')!='board-injected' or report.get('provenance')!='injected-touch':
        raise ValueError('not an executed injected acceptance report')
    if report.get('status') not in ('FAILED','CAPTURED_REQUIRES_REVIEW'):
        raise ValueError('invalid observation status')
    package=module.trusted(report.get('package_store_path',''))
    revision=report.get('source_revision','')
    if not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('invalid source revision')
    for key in ('created_at',):dt.datetime.fromisoformat(report[key])
    dt.datetime.fromisoformat(manifest['collected_at'])
    required={'schema':1,'environment':'board','board_model':'LILYGO T-Display-K230',
              'ownership':'coordinator-reserved','package_store_path':package,
              'source_revision':revision,'evidence_class':'board-injected'}
    if any(manifest.get(k)!=v for k,v in required.items()):raise ValueError('manifest disagrees with observation')
    clean={k:report[k] for k in ('schema','status','evidence_class','provenance','created_at','package_store_path','source_revision')}
    clean.update(physical_touch='UNVERIFIED',optical_latency='UNVERIFIED',visual_privacy_and_control_review='REQUIRED',cases=[])
    captures={}
    for row in report.get('cases',[]):
        stamp=row.get('monotonic_ns')
        if stamp is not None and (type(stamp)!=int or stamp<0):raise ValueError('invalid observation time')
        if row.get('case') in CASE_NAMES and row.get('status') in ('OBSERVED','FAILED'):
            item={k:row[k] for k in ('case','status')}
        elif row.get('capture') in {name+'.png' for name in CAPTURES} and row.get('status')=='CAPTURED_REQUIRES_VISUAL_REVIEW' and re.fullmatch(r'[a-f0-9]{64}',row.get('sha256','')):
            item={k:row[k] for k in ('capture','status','sha256')}
            captures[row['capture']]=row['sha256']
        else:raise ValueError('unknown observation record')
        if stamp is not None:item['monotonic_ns']=stamp
        clean['cases'].append(item)
    output.mkdir(parents=True,exist_ok=True)
    for name,digest in captures.items():
        path=source/name
        if path.stat().st_size>8*1024*1024:raise ValueError('capture exceeds bound')
        pixels=path.read_bytes()
        if pixels[:8]!=b'\x89PNG\r\n\x1a\n' or hashlib.sha256(pixels).hexdigest()!=digest:
            raise ValueError('capture signature or digest differs from observation')
        (output/name).write_bytes(pixels)
    for name in ('one','two'):
        source_log=source/('client-'+name+'.jsonl')
        if source_log.exists():
            if source_log.stat().st_size>8*1024*1024:raise ValueError('client log exceeds bound')
            rows=[json.loads(row) for row in source_log.read_text().splitlines()]
            (output/source_log.name).write_text(client_export(rows,name))
    module.atomic_json(output/'acceptance.json',clean)
    module.atomic_json(output/'manifest.json',{**required,'collected_at':manifest['collected_at']})
    telemetry=source/'telemetry.log'
    if telemetry.stat().st_size>16*1024*1024:raise ValueError('telemetry exceeds bound')
    (output/'telemetry.log').write_text(module.normalized_journal(telemetry.read_text()))


def execute(state,runtime,injector,output):
    recovery=module.Session(runtime,module.System(state))
    acceptance=None
    try:
        verify_device(state.get('device'))
        if injector is not None and (injector.is_symlink() or injector.stat().st_uid!=0 or injector.stat().st_mode & 0o022):
            raise RuntimeError('injector must be a reviewed root-owned script without group/other write access')
        acceptance=Acceptance(state,runtime,injector,output)
        try:acceptance.run()
        except BaseException:
            acceptance.records.append({'case':'interrupted-or-failed','status':'FAILED'})
            acceptance.write_report();raise
        return 1 if any(x.get('status')=='FAILED' for x in acceptance.records) else 0
    finally:
        recovery.restore(state['token'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--execute',action='store_true');modes.add_argument('--collect',type=Path,metavar='EXPORTED_DIRECTORY')
    modes.add_argument('--prepare',action='store_true')
    parser.add_argument('--provenance',choices=['injected-touch'],default='injected-touch')
    parser.add_argument('--runtime',type=Path,default=Path('/run/k230-card-shell'))
    parser.add_argument('--inject-script',type=Path,help='optional legacy process-per-event injector (not suitable for gesture timing)')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.collect:collect(args.collect,args.output);return 0
        if not args.execute:
            args.output.mkdir(parents=True,exist_ok=True);module.atomic_json(args.output/'acceptance-plan.json',plan());return 0
        if os.geteuid()!=0 or not platform.machine().startswith('riscv'):
            raise RuntimeError('execute requires the reserved RISC-V board root session')
        if not re.fullmatch(r'/run/k230-card-shell(?:-[a-z0-9]+)?',str(args.runtime)) or args.runtime.is_symlink() or args.runtime.stat().st_uid!=0 or args.runtime.stat().st_mode & 0o022:
            raise RuntimeError('runtime must be the protected root-owned reservation directory')
        state=json.loads((args.runtime/'state.json').read_text())
        if state.get('phase')!='active' or state.get('closed'):raise RuntimeError('no active reserved product session')
        def interrupted(signum,frame):raise KeyboardInterrupt
        signal.signal(signal.SIGINT,interrupted);signal.signal(signal.SIGTERM,interrupted)
        return execute(state,args.runtime,args.inject_script,args.output)

    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,KeyboardInterrupt) as error:
        print(type(error).__name__+': '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
