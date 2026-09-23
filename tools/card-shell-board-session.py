#!/usr/bin/env python3
"""Reserved-board card session, with independent root recovery. No device I/O in prepare mode."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

UNIT = 'k230-card-shell.service'
INPUT_UNIT = 'k230-card-shell-input.service'
STORE = re.compile(r'^/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+(?:/[A-Za-z0-9+._/-]+)?$')
DEVICE_NAME = 'K230 injected touchscreen'
BENCH_KEYS = {'v','run','event','t_ns','clock','backend','renderer','width','height','output_format','input','cards','input_id','gesture_id','kind','source','frame_id','update_cpu_ns','final','presented','phase','cpu_ns','memory_bytes','scope'}
CARD_KEYS = {'id','class','cards','mode','actions','message','input','operation','accepted','focus','format','width','height','stride','commits','sampled','frame-done','output-presented','run','frame_id','total_cpu_ns','render_cpu_ns','input_cpu_ns'}
CARD_EVENTS = {'map','mirror','mirror-release','state','close-request','source-gone','unmap','restored','live','frame-cost'}


def trusted(path: str) -> str:
    if not STORE.fullmatch(path) or '..' in Path(path).parts:
        raise ValueError('expected an explicit Nix store path')
    return path


def pixman_policy_environment(policy):
    if policy not in ('auto', 'no-rvv'):
        raise ValueError('unknown Pixman dispatch policy')
    # Empty explicitly clears any inherited disable list without bypassing
    # Pixman's runtime hwprobe gate. Apply only to the transient compositor.
    return '--setenv=PIXMAN_DISABLE='+('rvv' if policy == 'no-rvv' else '')


def exec_identity(value: str) -> str:
    # systemctl includes mutable pid/start_time/stop_time/code/status fields in
    # ExecStart. Compare only the configured command, never that runtime state.
    commands=re.findall(r'\bpath=([^;]+);\s*argv\[\]=([^;]+);\s*ignore_errors=([^;]+);',value)
    if len(commands)!=1:
        raise RuntimeError('expected one readable normal ExecStart command')
    path,arguments,ignore=commands[0]
    return 'path='+path.strip()+'; argv[]='+arguments.strip()+'; ignore_errors='+ignore.strip()+';'


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def normalized_journal(text: str) -> str:
    """Export only fixed grammar; no arbitrary journal text, titles, paths or keys."""
    rows = []
    for line in text.splitlines():
        for prefix in ('K230_CARD_BENCH ', 'K230_CARD_SHELL '):
            start = line.find(prefix)
            if start < 0:
                continue
            row = line[start:]
            words = row[len(prefix):].split()
            if len(row) > 2048 or not words:
                continue
            if prefix.endswith('SHELL ') and '=' not in words[0]:
                if words.pop(0) not in CARD_EVENTS:
                    continue
            allowed = BENCH_KEYS if prefix.endswith('BENCH ') else CARD_KEYS
            fields = [word.split('=', 1) for word in words]
            if row.startswith('K230_CARD_SHELL frame-cost '):
                expected = {'run','frame_id','total_cpu_ns','render_cpu_ns','input_cpu_ns'}
                if len(fields) != len(expected) or {pair[0] for pair in fields} != expected or not all(len(pair) == 2 and re.fullmatch(r'[0-9]+', pair[1]) for pair in fields):
                    continue
            if fields and all(len(pair) == 2 and pair[0] in allowed and re.fullmatch(r'[A-Za-z0-9_.:-]+', pair[1]) for pair in fields):
                rows.append(row)
    return '\n'.join(rows) + ('\n' if rows else '')


class System:
    def __init__(self, saved=None):
        if saved:
            self.tools = {name:trusted(value) for name,value in saved["tools"].items()}
            self.python = trusted(saved["python"])
            return
        self.tools = {}
        for name in ('systemctl', 'systemd-run', 'journalctl', 'evemu-describe', 'evemu-device', 'evemu-event', 'sh', 'grim'):
            found = shutil.which(name)
            if not found:
                raise RuntimeError('missing board dependency: ' + name)
            self.tools[name] = trusted(str(Path(found).resolve()))
        self.python = trusted(str(Path(sys.executable).resolve()))

    def call(self, arguments, *, check=True, timeout=20):
        args = [self.tools.get(arguments[0], arguments[0]), *arguments[1:]]
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f'{Path(args[0]).name} failed with exit {result.returncode}')
        return result

    def prop(self, unit, name):
        result = self.call(['systemctl','show',unit,'--property='+name,'--value'], check=False)
        if result.returncode:
            # A transient unit may never have started or may already be collected.
            # Do not turn missing identity/configuration properties into success.
            if unit in (UNIT, INPUT_UNIT) and name in ('MainPID', 'ControlGroup'):
                missing = self.call(['systemctl','show',unit,'--property=LoadState','--value'], check=False)
                if missing.stdout.strip() == 'not-found':
                    return ''
            raise RuntimeError('cannot read required service property: '+name)
        value=result.stdout.strip()
        return exec_identity(value) if name=='ExecStart' else value

    def active(self, unit):
        return self.call(['systemctl','is-active','--quiet',unit], check=False).returncode == 0

    def sway_pids(self):
        result = []
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                if (proc/'comm').read_text().strip() == 'sway':
                    result.append(int(proc.name))
            except (FileNotFoundError, ProcessLookupError):
                pass
        return result

    def cgroup_empty(self, unit):
        group = self.prop(unit, 'ControlGroup')
        if not group:
            return True
        if not group.startswith('/') or '..' in Path(group).parts:
            return False
        events = Path('/sys/fs/cgroup'+group)/'cgroup.events'
        return not events.exists() or 'populated 0' in events.read_text().splitlines()

    def virtual_devices(self):
        found = set()
        for name in Path('/sys/class/input').glob('event*/device/name'):
            try:
                if name.read_text().strip() == DEVICE_NAME and str(name.resolve()).startswith('/sys/devices/virtual/input/'):
                    found.add('/dev/input/'+name.parents[1].name)
            except FileNotFoundError:
                pass
        return found

    def sleep(self, seconds):
        time.sleep(seconds)


class Session:
    def __init__(self, runtime: Path, system: System):
        self.runtime = runtime
        self.system = system
        self.state_path = runtime/'state.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def event(self, event):
        with (self.runtime/'session.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': event, 'monotonic_ns': time.monotonic_ns()})+'\n')

    def update(self, **values):
        self.state.update(values)
        atomic_json(self.state_path, self.state)

    def condition(self, token, input_only=False):
        current = json.loads(self.state_path.read_text())
        return (current.get('token') == token and not (self.runtime/('closed-'+token)).exists() and not current.get('closed') and
                not self.system.active('shell.service') and
                (self.system.active(UNIT) if input_only else not self.system.sway_pids()))

    def restore(self, token):
        current = json.loads(self.state_path.read_text())
        if current.get('token') != token:
            return  # A stale watchdog cannot affect a later reservation.
        self.state = current
        (self.runtime/('closed-'+token)).touch(mode=0o600)
        self.update(closed=True, phase='restoring')
        # No Conflicts= dependency: a late queued trial must not stop the restored
        # shell before its ExecCondition rejects the closed reservation.
        for unit in (UNIT, INPUT_UNIT):
            self.system.call(['systemctl','stop',unit], check=False)
            if self.system.active(unit) or self.system.prop(unit, 'MainPID') not in ('', '0') or not self.system.cgroup_empty(unit):
                self.event('cgroup_stop_failed')
                raise RuntimeError('experimental service did not stop')
        if self.system.prop('shell.service','ExecStart') != self.state['normal_exec']:
            self.event('normal_service_changed')
            raise RuntimeError('normal service definition changed during reservation')
        if not self.system.active('shell.service') and self.system.sway_pids():
            self.event('competing_compositor')
            raise RuntimeError('unowned compositor prevents restoration')
        self.system.call(['systemctl','start','shell.service'])
        if not self.system.active('shell.service') or not self.system.active('seatd.service'):
            raise RuntimeError('normal services failed to restore')
        self.update(phase='restored')
        self.event('normal_services_restored')

    def arm(self, plan):
        pixman_policy_environment(plan.get('pixman_policy', 'auto'))
        if not self.system.active('shell.service') or not self.system.active('seatd.service'):
            raise RuntimeError('normal shell and seatd must be active before reservation')
        if self.system.prop('shell.service','User') != 'shell':
            raise RuntimeError('normal shell service user differs from shell')
        normal = self.system.prop('shell.service','ExecStart')
        if not re.search(r'(?:^|\s)(?:-c|--config)\s+'+re.escape(plan['normal_config'])+r'(?:\s|;|$)', normal):
            raise RuntimeError('specified configuration is not the active normal service config')
        if self.state:
            if self.state.get('phase') != 'restored':
                raise RuntimeError('restore the previous reservation before starting another')
            for suffix in ('.timer','.service'):
                self.system.call(['systemctl','stop',self.state['watchdog']+suffix], check=False)
        token = uuid.uuid4().hex
        watchdog = 'k230-card-shell-recovery-'+token
        self.state = {**plan, 'schema':1, 'token':token, 'watchdog':watchdog, 'closed':False,
                      'phase':'armed', 'normal_exec':normal, 'invocation':None, 'device':None,
                      'tools':self.system.tools, 'python':self.system.python,
                      'created_at':dt.datetime.now(dt.timezone.utc).isoformat()}
        atomic_json(self.state_path, self.state)
        recovery = str(self.runtime/'runner.py')
        shutil.copyfile(__file__, recovery)
        Path(recovery).chmod(0o644)
        self.system.call(['systemd-run','--unit='+watchdog,'--on-active='+str(plan['duration']+45)+'s',
                          '--timer-property=AccuracySec=1s','--timer-property=OnUnitActiveSec=5s','--property=Type=oneshot','--property=User=root',
                          '--property=Restart=on-failure','--property=RestartSec=5s','--property=StartLimitIntervalSec=0',
                          self.system.python,recovery,'--internal-restore',token,'--runtime',str(self.runtime)])
        if not self.system.active(watchdog+'.timer'):
            raise RuntimeError('root recovery timer did not arm')
        self.event('root_watchdog_armed')
        return token

    def start(self):
        if (self.runtime/('closed-'+self.state['token'])).exists():
            raise RuntimeError('reservation already closed by recovery')
        self.system.call(['systemctl','reset-failed',UNIT,INPUT_UNIT], check=False)
        self.system.call(['systemctl','stop','shell.service'])
        if self.system.active('shell.service') or self.system.prop('shell.service','MainPID') != '0' or self.system.sway_pids():
            raise RuntimeError('normal or competing compositor still owns the session')
        self.event('normal_shell_stopped')
        session = self.runtime/'wayland'
        session.mkdir(mode=0o700, exist_ok=True)
        account = pwd.getpwnam('shell')
        os.chown(session, account.pw_uid, account.pw_gid)
        config = session/'sway.conf'
        # IPC splits commas before for_window receives its command list.
        # Keep this fixture-only rule in the configuration parsed at startup.
        config.write_text('include '+self.state['normal_config']+'\noutput DSI-1 mode 568x1232 transform normal scale 1 render_bit_depth 6\ninput type:touch map_to_output DSI-1\nfor_window [app_id="^k230[.]card[.](one|two)$"] floating enable, border none, resize set 520 1040, move position 24 96\n')
        config.chmod(0o644)
        environment = shlex.split(self.system.prop('shell.service','Environment'))
        path = next((item[5:] for item in environment if item.startswith('PATH=')), None)
        if not path:
            raise RuntimeError('normal shell dependency PATH is unavailable')
        for entry in path.split(':'):
            if entry not in ('/run/current-system/sw/bin','/run/wrappers/bin'):
                trusted(entry)
        guard = '+'+self.system.python+' '+str(self.runtime/'runner.py')+' --internal-guard '+self.state['token']+' --runtime '+str(self.runtime)
        self.update(dependency_path=path)
        self.system.call(['systemd-run','--unit='+UNIT,'--property=Type=exec','--property=User=shell','--property=Group=shell','--property=WorkingDirectory='+account.pw_dir,
                          '--property=KillMode=control-group','--property=TimeoutStopSec=10s',
                          '--property=RuntimeMaxSec='+str(self.state['duration'])+'s',
                          '--property=CPUAccounting=yes','--property=MemoryAccounting=yes',
                          '--property=StandardOutput=journal','--property=StandardError=journal',
                          '--property=LogRateLimitIntervalSec=0','--property=ExecCondition='+guard,
                          '--setenv=PATH='+path,'--setenv=XDG_RUNTIME_DIR='+str(session),
                          '--setenv=SWAYSOCK='+str(session/'sway-ipc.sock'),'--setenv=XDG_SEAT=seat0',
                          '--setenv=LIBSEAT_BACKEND=seatd','--setenv=WLR_RENDERER=pixman',
                          '--setenv=SWAY_K230_CARD_BENCH_CGROUP=1',
                          pixman_policy_environment(self.state.get('pixman_policy', 'auto')),
                          self.state['package']+'/bin/card-shell','--sway','--debug','--config',str(config)])
        invocation = self.system.prop(UNIT,'InvocationID')
        if not re.fullmatch(r'[a-f0-9]{32}', invocation):
            raise RuntimeError('missing compositor invocation identity')
        self.update(invocation=invocation, phase='active')
        self.event('product_session_started')

    def input_device(self):
        if not self.condition(self.state['token'], input_only=True):
            raise RuntimeError('product session closed before input setup')
        original = self.system.virtual_devices()
        descriptor = self.system.call(['evemu-describe',self.state['source_device']]).stdout
        descriptor, count = re.subn(r'^N:.*$', 'N: '+DEVICE_NAME, descriptor, flags=re.MULTILINE)
        if count != 1:
            raise RuntimeError('unexpected touchscreen descriptor')
        path = self.runtime/'touch.desc'
        path.write_text(descriptor)
        guard = '+'+self.system.python+' '+str(self.runtime/'runner.py')+' --internal-input-guard '+self.state['token']+' --runtime '+str(self.runtime)
        self.system.call(['systemd-run','--unit='+INPUT_UNIT,'--property=Type=exec','--property=User=root',
                          '--property=KillMode=control-group','--property=ExecCondition='+guard,'--property=RuntimeMaxSec='+str(self.state['duration']+30)+'s',
                          self.system.tools['evemu-device'],str(path)])
        for _ in range(100):
            new = self.system.virtual_devices()-original
            if len(new) == 1:
                self.update(device=new.pop())
                self.event('distinct_virtual_touch_ready')
                return
            self.system.sleep(.1)
        raise RuntimeError('distinct virtual touchscreen did not appear')

    def execute(self, plan, output):
        token = self.arm(plan)
        try:
            self.start()
            self.input_device()
            print(json.dumps({'status':'active','runtime':str(self.runtime),'device':self.state['device']}),flush=True)
            deadline=time.monotonic()+plan['duration']
            while self.system.active(UNIT) and time.monotonic()<deadline:
                if (self.runtime/('closed-'+token)).exists(): break
                self.system.sleep(.5)
            result=self.system.prop(UNIT,'Result')
            if result not in ('', 'success', 'timeout'):
                raise RuntimeError('product compositor failed: '+result)
        finally:
            self.restore(token)
            self.system.call(['systemctl','stop',self.state['watchdog']+'.timer'],check=False)
            self.collect(output)

    def collect(self, output):
        output.mkdir(parents=True, exist_ok=True)
        invocation = self.state.get('invocation')
        if invocation:
            if not re.fullmatch(r'[a-f0-9]{32}', invocation):
                raise RuntimeError('invalid journal invocation')
            journal = self.system.call(['journalctl','_SYSTEMD_INVOCATION_ID='+invocation,'--no-pager','-o','cat','--grep=K230_CARD_(BENCH|SHELL)','-n','20000']).stdout
            (output/'telemetry.log').write_text(normalized_journal(journal[:16*1024*1024]))
        # Protect internal ExecStart, dependency environment and service state.
        manifest = {key:self.state[key] for key in ('schema','package','source_revision','created_at','normal_config','phase','device','invocation','pixman_policy') if key in self.state}
        manifest.update(evidence_class='board-session-telemetry', physical_touch='UNVERIFIED', normal_controls='UNVERIFIED')
        atomic_json(output/'session.json', manifest)
        if (self.runtime/'session.jsonl').exists():
            shutil.copyfile(self.runtime/'session.jsonl', output/'session.jsonl')


def plan_from(args):
    if not re.fullmatch(r'[a-f0-9]{40}', args.revision or ''):
        raise ValueError('full source revision is required')
    if not 30 <= args.duration <= 600:
        raise ValueError('duration must be 30–600 seconds')
    if not re.fullmatch(r'/dev/input/event[0-9]+', args.source_device):
        raise ValueError('source device must be an explicit input event device')
    policy = getattr(args, 'pixman_policy', 'auto')
    pixman_policy_environment(policy)
    return {'pixman_policy':policy, 'package':trusted(args.package), 'normal_config':trusted(args.config), 'client':trusted(args.client),
            'source_revision':args.revision, 'duration':args.duration, 'source_device':args.source_device}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--restore', action='store_true')
    mode.add_argument('--collect', action='store_true')
    mode.add_argument('--internal-restore', metavar='TOKEN')
    mode.add_argument('--internal-guard', metavar='TOKEN')
    mode.add_argument('--internal-input-guard', metavar='TOKEN')
    parser.add_argument('--runtime', type=Path, default=Path('/run/k230-card-shell'))
    parser.add_argument('--package');parser.add_argument('--config');parser.add_argument('--client')
    parser.add_argument('--revision');parser.add_argument('--duration',type=int,default=300)
    parser.add_argument('--source-device',default='/dev/input/event0')
    parser.add_argument('--pixman-policy', choices=('auto','no-rvv'), default='auto')
    parser.add_argument('--output',type=Path,default=Path('card-shell-session'))
    args = parser.parse_args(argv)
    try:
        if args.prepare:
            plan = plan_from(args)
            args.output.mkdir(parents=True, exist_ok=True)
            atomic_json(args.output/'plan.json', {**plan,'status':'PLANNED_ONLY','board_commands_executed':False,
                        'normal_controls':'normal config included unchanged','root_watchdog':'armed before shell stop',
                        'physical_touch':'UNVERIFIED'})
            return 0
        if os.geteuid() != 0 or not platform.machine().startswith('riscv'):
            raise RuntimeError('execution requires the reserved RISC-V board root session')
        if not re.fullmatch(r'/run/k230-card-shell(?:-[a-z0-9]+)?', str(args.runtime)):
            raise ValueError('invalid protected runtime directory')
        os.umask(0o077)
        args.runtime.mkdir(mode=0o711, exist_ok=True)
        if args.runtime.is_symlink() or args.runtime.stat().st_uid != 0 or args.runtime.stat().st_mode & 0o022:
            raise RuntimeError('runtime is not a root-owned directory')
        args.runtime.chmod(0o711)
        saved = json.loads((args.runtime/'state.json').read_text()) if (args.internal_guard or args.internal_input_guard or args.internal_restore or args.collect or args.restore) else None
        system = System(saved)
        session = Session(args.runtime,system)
        if args.internal_input_guard:
            return 0 if session.condition(args.internal_input_guard, input_only=True) else 1
        if args.internal_guard:
            return 0 if session.condition(args.internal_guard) else 1
        if args.internal_restore or args.restore:
            session.restore(args.internal_restore or session.state['token'])
            return 0
        if args.collect:
            session.collect(args.output)
            return 0
        with (args.runtime/'operator.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            plan = plan_from(args)
            for path in (plan['package']+'/bin/card-shell',plan['client'],plan['normal_config']):
                if not Path(path).exists(): raise RuntimeError('declared store artifact is not installed')
            def interrupted(signum, frame): raise KeyboardInterrupt
            signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
            session.execute(plan,args.output)
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        print(type(error).__name__+': '+str(error),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
