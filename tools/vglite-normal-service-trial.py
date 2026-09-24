#!/usr/bin/env python3
"""Bounded opt-in normal shell VG-Lite broker trial; Pixman restored on exit."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

DROPIN=Path('/run/systemd/system/shell.service.d/90-k230-vglite-trial.conf')
SOCKET_UNIT=Path('/run/systemd/system/k230-vglite-broker.socket')
BROKER_UNIT=Path('/run/systemd/system/k230-vglite-broker.service')
LOCK=Path('/run/k230-vglite-service-trial.lock')
RESTORE_LOCK=Path('/run/k230-vglite-service-restore.lock')
OUTPUT=re.compile(r'/var/lib/k230/vglite-service-trial-[a-z0-9-]+')
STORE=re.compile(r'/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._/-]+')


def store_file(value):
    path=Path(value)
    if not STORE.fullmatch(value) or '..' in path.parts or not path.is_file():
        raise ValueError('expected an installed Nix store file')
    info=path.stat()
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('store file is not root-owned and immutable')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exec_identity(value):
    matches=re.findall(r'\bpath=([^;]+);\s*argv\[\]=([^;]+);\s*ignore_errors=([^;]+);',value)
    if len(matches)!=1:
        raise RuntimeError('normal ExecStart identity is unreadable')
    return tuple(part.strip() for part in matches[0])


def write_state(output, state):
    temp=output/('state.'+uuid.uuid4().hex+'.new')
    temp.write_text(json.dumps(state,indent=2)+'\n')
    temp.chmod(0o600)
    temp.replace(output/'state.json')


class System:
    def call(self, args, *, check=True, timeout=30):
        result=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f'{args[0]} failed with exit {result.returncode}')
        return result.stdout.strip()

    def active(self, unit):
        return subprocess.run(['systemctl','is-active','--quiet',unit],timeout=5).returncode == 0

    def prop(self, unit, key):
        return self.call(['systemctl','show',unit,'--property='+key,'--value'])


def owned_text(path, token, body):
    if path.exists() or path.is_symlink():
        raise RuntimeError('trial unit path already exists: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.parent.is_symlink():
        raise RuntimeError('trial unit parent is a symlink')
    path.write_text('# k230-vglite-trial-token='+token+'\n'+body)
    path.chmod(0o600)


def remove_owned(path, token):
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or not path.read_text().startswith('# k230-vglite-trial-token='+token+'\n'):
        raise RuntimeError('refusing to remove a non-owned unit: '+str(path))
    path.unlink()


class Trial:
    def __init__(self, output, wrapper, unwrapped, broker, python, config, seconds, system=None, force_pixman=False):
        self.output=Path(output);self.wrapper=Path(wrapper);self.unwrapped=Path(unwrapped)
        self.broker=Path(broker);self.python=Path(python);self.config=Path(config)
        self.seconds=seconds;self.system=system or System();self.token=uuid.uuid4().hex
        self.watchdog='k230-vglite-service-recovery-'+self.token[:12]
        self.force_pixman=force_pixman

    def preflight(self):
        if not OUTPUT.fullmatch(str(self.output)) or self.output.exists():
            raise ValueError('new protected trial output required')
        if not 30 <= self.seconds <= 180:
            raise ValueError('trial duration must be 30–180 seconds')
        for path in (self.wrapper,self.unwrapped,self.broker,self.python,self.config):
            store_file(str(path))
        if not self.system.active('shell.service') or not self.system.active('seatd.service'):
            raise RuntimeError('normal shell and seatd must be active')
        if self.system.prop('shell.service','User') != 'shell':
            raise RuntimeError('normal shell user changed')
        original=self.system.prop('shell.service','ExecStart')
        if str(self.config) not in exec_identity(original)[1]:
            raise RuntimeError('declared config differs from normal shell ExecStart')
        if self.system.active('k230-vglite-broker.socket') or self.system.active('k230-vglite-broker.service'):
            raise RuntimeError('broker already active')
        for path in (DROPIN,SOCKET_UNIT,BROKER_UNIT):
            if path.exists() or path.is_symlink():
                raise RuntimeError('trial unit path already exists: '+str(path))
        return original

    def _record_unlocked(self, **values):
        state=json.loads((self.output/'state.json').read_text())
        state.update(values)
        write_state(self.output,state)

    def guarded(self, action):
        # Recovery uses this lock too. Keep each possibly slow systemctl call
        # inside one guard, then give the watchdog a chance to take over.
        with RESTORE_LOCK.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            state=json.loads((self.output/'state.json').read_text())
            if state.get('token') != self.token or state.get('phase') not in \
                    ('prepared','armed','trial-units-ready','observed'):
                raise RuntimeError('trial was closed by recovery')
            return action()

    def record(self, **values):
        self.guarded(lambda: self._record_unlocked(**values))

    def prepare(self, original):
        self.output.mkdir(mode=0o700)
        copy=self.output/'runner.py';shutil.copyfile(__file__,copy);copy.chmod(0o600)
        state={'schema':1,'token':self.token,'phase':'prepared','created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
               'normal_exec':original,'normal_system':os.path.realpath('/run/current-system'),
               'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               'wrapper':str(self.wrapper),'unwrapped':str(self.unwrapped),'broker':str(self.broker),
               'python':str(self.python),'config':str(self.config),'seconds':self.seconds,
               'forced_pixman':self.force_pixman,
               'sha256':{'runner':digest(copy),'broker':digest(self.broker),'wrapper':digest(self.wrapper),
                         'unwrapped':digest(self.unwrapped),'config':digest(self.config)}}
        write_state(self.output,state)
        # Arm before any unit or normal-service mutation. The copied runner
        # survives an interrupted controller and is root-only.
        self.system.call(['systemd-run','--unit='+self.watchdog,'--on-active='+str(self.seconds+30)+'s',
                          '--timer-property=AccuracySec=1s','--property=Type=oneshot',
                          str(self.python),str(copy),'--restore','--output',str(self.output),'--token',self.token])
        if not self.system.active(self.watchdog+'.timer'):
            raise RuntimeError('independent recovery timer did not arm')
        self.record(phase='armed',watchdog=self.watchdog)

    def install(self):
        self.guarded(lambda: owned_text(SOCKET_UNIT,self.token,'[Socket]\nListenStream=/run/k230-vglite-broker.sock\nSocketUser=root\nSocketGroup=shell\nSocketMode=0660\nRemoveOnStop=yes\n[Install]\nWantedBy=sockets.target\n'))
        self.guarded(lambda: owned_text(BROKER_UNIT,self.token,
            '[Unit]\nRequires=k230-vglite-broker.socket\nAfter=k230-vglite-broker.socket\n[Service]\nType=simple\nUser=root\nGroup=root\n'
            'ExecStart='+str(self.python)+' '+str(self.broker)+' --unit shell.service --executable '+str(self.unwrapped)+' --user shell\n'
            'NoNewPrivileges=yes\nCapabilityBoundingSet=CAP_SYS_PTRACE\nDevicePolicy=closed\nDeviceAllow=/dev/vg_lite rw\n'
            'ProtectSystem=strict\nProtectHome=yes\nPrivateTmp=yes\nProtectKernelTunables=yes\n'
            'ProtectKernelModules=yes\nProtectControlGroups=yes\nRestrictNamespaces=yes\n'
            'RestrictAddressFamilies=AF_UNIX\nSystemCallFilter=~@debug\nUMask=0077\n'))
        self.guarded(lambda: owned_text(DROPIN,self.token,
            '[Unit]\nRequires=k230-vglite-broker.socket\nAfter=k230-vglite-broker.socket\n'
            '[Service]\nExecStart=\nExecStart='+str(self.wrapper)+' -V -c '+str(self.config)+'\n'
            'Environment=WLR_RENDERER=vglite K230_VGLITE_BROKER=/run/k230-vglite-broker.sock K230_VGLITE_ALLOW_UNPROVEN_CACHE='+('0' if self.force_pixman else '1')+'\n'
            'Restart=no\n'))
        self.guarded(lambda: self.system.call(['systemctl','daemon-reload']))
        self.guarded(lambda: self.system.call(['systemctl','start','k230-vglite-broker.socket']))
        if not self.system.active('k230-vglite-broker.socket'):
            raise RuntimeError('broker socket failed to arm')
        self.record(phase='trial-units-ready')

    def run(self):
        original=self.preflight()
        try:
            self.prepare(original)
            self.install()
            self.guarded(lambda: self.system.call(['systemctl','stop','shell.service']))
            if self.system.active('shell.service'):
                raise RuntimeError('normal shell did not stop')
            self.guarded(lambda: self.system.call(['systemctl','start','shell.service']))
            if not self.system.active('shell.service'):
                raise RuntimeError('trial shell did not start')
            pid=int(self.system.prop('shell.service','MainPID'))
            if pid <= 1 or os.path.realpath('/proc/'+str(pid)+'/exe') != str(self.unwrapped):
                raise RuntimeError('trial MainPID is not the expected compositor')
            scope=Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip()
            fd_owner=Path('/proc/'+str(pid)+'/fd').stat().st_uid
            self.record(phase='observed',main_pid=pid,ptrace_scope=scope,proc_fd_owner=fd_owner)
            if scope not in ('1','2','3') or fd_owner != 0:
                raise RuntimeError('normal-service ptrace or non-dumpability boundary failed')
            time.sleep(self.seconds)
            since=json.loads((self.output/'state.json').read_text())['created_at_utc']
            broker_log=self.system.call(['journalctl','-u','k230-vglite-broker.service','--since='+since,'--no-pager','-o','cat','-n','1000'])
            shell_log=self.system.call(['journalctl','-u','shell.service','--since='+since,'--no-pager','-o','cat','-n','10000'])
            grants=sum('VG-Lite descriptor granted to compositor MainPID '+str(pid) in line
                       for line in broker_log.splitlines())
            gpu=shell_log.count('VG-Lite full frame submitted')
            replay=shell_log.count('VG-Lite full pass replayed with Pixman')
            self.record(broker_grants_for_main_pid=grants,gpu_full_frames=gpu,pixman_replays=replay)
            if grants > 1 or (self.force_pixman and (replay == 0 or gpu != 0)) or \
                    (not self.force_pixman and (grants != 1 or gpu == 0)):
                raise RuntimeError('trial did not observe its required broker/render path')
        finally:
            if (self.output/'state.json').exists():
                restore(self.output,self.token,self.system)


def _restore(output, token, system=None):
    system=system or System();output=Path(output)
    state=json.loads((output/'state.json').read_text())
    if state.get('token') != token or state.get('phase') == 'restored':
        return
    # Refuse stale restoration if a different trial owns the current drop-in.
    for path in (DROPIN,SOCKET_UNIT,BROKER_UNIT):
        if path.is_symlink() or (path.exists() and not path.read_text().startswith('# k230-vglite-trial-token='+token+'\n')):
            raise RuntimeError('different trial owns runtime unit: '+str(path))
    if state.get('phase') in ('prepared','armed') and system.active('shell.service') and \
            not any(path.exists() for path in (DROPIN,SOCKET_UNIT,BROKER_UNIT)):
        state['phase']='restored'
        write_state(output,state)
        system.call(['systemctl','stop','k230-vglite-service-recovery-'+token[:12]+'.timer'],check=False)
        return
    state['phase']='restoring'
    write_state(output,state)
    system.call(['systemctl','stop','shell.service'],check=False)
    system.call(['systemctl','stop','k230-vglite-broker.socket','k230-vglite-broker.service'],check=False)
    if any(system.active(unit) for unit in ('shell.service','k230-vglite-broker.socket','k230-vglite-broker.service')):
        raise RuntimeError('trial compositor or broker did not stop')
    for path in (DROPIN,SOCKET_UNIT,BROKER_UNIT):remove_owned(path,token)
    system.call(['systemctl','daemon-reload'])
    system.call(['systemctl','reset-failed','shell.service'],check=False)
    system.call(['systemctl','start','shell.service'])
    if not system.active('shell.service') or not system.active('seatd.service'):
        raise RuntimeError('normal Pixman shell or seatd failed to restore')
    if exec_identity(state['normal_exec']) != exec_identity(system.prop('shell.service','ExecStart')):
        raise RuntimeError('normal ExecStart changed after restoration')
    state['phase']='restored';state['restored_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    write_state(output,state)
    system.call(['systemctl','stop',state.get('watchdog','')+'.timer'],check=False)


def restore(output, token, system=None):
    # The controller and independent watchdog may reach recovery together.
    # Only recovery holds this lock; it never waits for the trial's run lock.
    with RESTORE_LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        _restore(output,token,system)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--wrapper');p.add_argument('--unwrapped');p.add_argument('--broker')
    p.add_argument('--python');p.add_argument('--config');p.add_argument('--seconds',type=int,default=90)
    p.add_argument('--force-pixman',action='store_true')
    p.add_argument('--restore',action='store_true');p.add_argument('--token')
    a=p.parse_args(argv)
    if os.geteuid()!=0 or not platform.machine().startswith('riscv') or not OUTPUT.fullmatch(str(a.output)):
        p.error('reserved RISC-V root board and protected output required')
    if a.restore:
        if not a.token:p.error('restore requires token')
        restore(a.output,a.token)
        return 0
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not all((a.wrapper,a.unwrapped,a.broker,a.python,a.config)):
            p.error('wrapper, unwrapped, broker, python and config required')
        Trial(a.output,a.wrapper,a.unwrapped,a.broker,a.python,a.config,a.seconds,
              force_pixman=a.force_pixman).run()
    return 0


if __name__=='__main__':raise SystemExit(main())
