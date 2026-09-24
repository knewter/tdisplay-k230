#!/usr/bin/env python3
"""Bounded root observation inside a watchdog-owned VG-Lite shell trial."""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import secrets
import shlex
import socket
import stat
import struct
import subprocess
import sys

DEVICE=Path('/dev/vg_lite')
BROKER=Path('/run/k230-vglite-broker.sock')
SWAYSOCK=Path('/run/shell/sway-ipc.sock')
SOCKET_DIR=Path('/run')
PTR_SEIZE=0x4206
PTR_DETACH=17
SCHEMA=1


def status(pid):
    return dict(line.split(':',1) for line in (Path('/proc')/str(pid)/'status').read_text().splitlines() if ':' in line)


def uid_and_caps(pid):
    row=status(pid)
    return [int(x) for x in row['Uid'].split()],int(row['CapEff'].strip(),16)


def main_pid():
    result=subprocess.run(['systemctl','show','shell.service','--property=MainPID','--value'],
                          capture_output=True,text=True,check=True,timeout=3)
    return int(result.stdout.strip())


def device_fd_numbers(pid, device=DEVICE):
    info=device.stat()
    if not stat.S_ISCHR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o066:
        raise RuntimeError('device is not a private root character node')
    found=[]
    for path in (Path('/proc')/str(pid)/'fd').iterdir():
        try:entry=path.stat()
        except FileNotFoundError:continue
        if stat.S_ISCHR(entry.st_mode) and entry.st_rdev==info.st_rdev:
            found.append(int(path.name))
    return sorted(found)


def mapped_device(pid):
    return sum('/dev/vg_lite' in line for line in (Path('/proc')/str(pid)/'maps').read_text().splitlines())


def check_main(trial, expected_pid):
    if main_pid()!=expected_pid or expected_pid<=1:
        raise RuntimeError('trial MainPID changed')
    proc=Path('/proc')/str(expected_pid)
    if os.path.realpath(proc/'exe')!=trial['unwrapped']:
        raise RuntimeError('MainPID executable differs')
    shell=pwd.getpwnam('shell').pw_uid
    uids,caps=uid_and_caps(expected_pid)
    row=status(expected_pid)
    scope=int(Path('/proc/sys/kernel/yama/ptrace_scope').read_text())
    if uids!=[shell]*4 or caps!=0 or int(row['PPid'])!=1 or int(row['TracerPid'])!=0:
        raise RuntimeError('MainPID credentials or parent differ')
    if (proc/'fd').stat().st_uid!=0 or scope not in (1,2,3):
        raise RuntimeError('non-dumpability or Yama boundary differs')
    fds=device_fd_numbers(expected_pid)
    if len(fds)!=1:raise RuntimeError('expected one compositor VG-Lite descriptor')
    return {'main_pid':expected_pid,'main_uid':shell,'main_caps_zero':True,
            'main_fd_count':len(fds),'ptrace_scope':scope},fds[0]


def denial_child(pid, fd_number):
    shell=pwd.getpwnam('shell').pw_uid
    uids,caps=uid_and_caps(os.getpid())
    if uids!=[shell]*4 or caps!=0:raise RuntimeError('denial client has unexpected credentials')
    result={'shell_uid':shell,'caps_zero':True}
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
        peer.settimeout(2)
        peer.connect(str(BROKER))
        peer.sendall(b'VG1\n')
        data,ancillary,_,_=peer.recvmsg(1,socket.CMSG_SPACE(16))
        result['broker_denied']=data==b'' and not ancillary
        if ancillary:
            for _,kind,payload in ancillary:
                if kind==socket.SCM_RIGHTS:
                    for item in struct.iter_unpack('i',payload[:len(payload)//4*4]):os.close(item[0])
    for key,path in (('direct_denied',DEVICE),('proc_fd_denied',Path('/proc')/str(pid)/'fd'/str(fd_number))):
        flags=os.O_RDWR|os.O_CLOEXEC|(os.O_NOFOLLOW if key=='direct_denied' else 0)
        try:fd=os.open(path,flags)
        except PermissionError:result[key]=True
        else:
            os.close(fd);result[key]=False
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.ptrace(PTR_SEIZE,pid,None,None)==0:
        libc.ptrace(PTR_DETACH,pid,None,None)
        result['ptrace_denied']=False
    else:
        error=ctypes.get_errno()
        if error not in (1,13):raise RuntimeError('ptrace probe did not reach access decision')
        result['ptrace_denied']=True
    return result


def run_denial(pid,fd_number):
    account=pwd.getpwnam('shell')
    def drop():
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.prctl(38,1,0,0,0)!=0:os._exit(126)  # PR_SET_NO_NEW_PRIVS
    command=[sys.executable,'-I',str(Path(__file__).resolve()),'--denial-child',
             '--pid',str(pid),'--fd-number',str(fd_number)]
    completed=subprocess.run(command,preexec_fn=drop,capture_output=True,text=True,timeout=8)
    if completed.returncode:raise RuntimeError('same-UID denial helper failed')
    result=json.loads(completed.stdout)
    if not all(result.get(key) is True for key in ('caps_zero','broker_denied','direct_denied',
                                                   'proc_fd_denied','ptrace_denied')):
        raise RuntimeError('same-UID isolation denial failed')
    return result


def sway_command(command):
    payload=command.encode()
    if len(payload)>4096:raise RuntimeError('Sway command too long')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
        peer.settimeout(5);peer.connect(str(SWAYSOCK))
        peer.sendall(b'i3-ipc'+struct.pack('<II',len(payload),0)+payload)
        header=b''
        while len(header)<14:
            part=peer.recv(14-len(header))
            if not part:raise RuntimeError('short Sway IPC header')
            header+=part
        if len(header)!=14 or header[:6]!=b'i3-ipc':raise RuntimeError('invalid Sway IPC header')
        size,kind=struct.unpack('<II',header[6:])
        if kind!=0 or size>4096:raise RuntimeError('invalid Sway IPC response')
        body=b''
        while len(body)<size:
            part=peer.recv(size-len(body))
            if not part:raise RuntimeError('short Sway IPC response')
            body+=part
        rows=json.loads(body)
        if not isinstance(rows,list) or not rows or not all(row.get('success') is True for row in rows):
            raise RuntimeError('Sway refused app launch')


def ancestor_is_sway(pid,sway_pid):
    for _ in range(6):
        if pid==sway_pid:return True
        pid=int(status(pid)['PPid'])
        if pid<=1:break
    return False


def run_app_check(pid):
    nonce=secrets.token_hex(16)
    listener=SOCKET_DIR/('k230-vglite-isolation-'+nonce+'.sock')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(str(listener));listener.chmod(0o666)
        server.listen(1);server.settimeout(6)
        try:
            child=[sys.executable,'-I',str(Path(__file__).resolve()),'--app-child',
                   '--socket',str(listener),'--nonce',nonce]
            sway_command('exec -- '+shlex.join(child))
            peer,_=server.accept()
            with peer:
                peer.settimeout(3)
                cred_pid,cred_uid,_=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                message=b''
                while len(message)<len(nonce):
                    part=peer.recv(len(nonce)-len(message))
                    if not part:raise RuntimeError('short app-child identity token')
                    message+=part
                message=message.decode()
                if message!=nonce or cred_uid!=pwd.getpwnam('shell').pw_uid or not ancestor_is_sway(cred_pid,pid):
                    raise RuntimeError('app child is not the expected Sway-launched shell process')
                uids,caps=uid_and_caps(cred_pid)
                if uids!=[cred_uid]*4 or caps!=0:raise RuntimeError('app child credentials differ')
                fds=device_fd_numbers(cred_pid)
                maps=mapped_device(cred_pid)
                if fds or maps:raise RuntimeError('Sway-launched child retained VG-Lite access')
                peer.sendall(b'OK')
                return {'app_pid':cred_pid,'app_uid':cred_uid,'app_caps_zero':True,
                        'app_device_fds':len(fds),'app_device_mappings':maps,
                        'preexec_inspection':'UNVERIFIED'}
        finally:listener.unlink(missing_ok=True)


def broker_counts(trial, old_pid, current_pid):
    since=trial['created_at_utc']
    result=subprocess.run(['journalctl','-u','k230-vglite-broker.service','--since='+since,
                           '--no-pager','-o','cat','-n','1000'],capture_output=True,text=True,check=True,timeout=5)
    grants=[int(v) for v in re.findall(r'^VG-Lite descriptor granted to compositor MainPID ([0-9]+)$',result.stdout,re.M)]
    denied=sum(line.startswith('VG-Lite descriptor denied:') for line in result.stdout.splitlines())
    expected=[current_pid] if old_pid is None else [old_pid,current_pid]
    if sorted(grants)!=sorted(expected) or denied<1:
        raise RuntimeError('broker grant/denial journal does not match trial phase')
    return {'grant_count':len(grants),'denial_count':denied,'old_pid_grants':0 if old_pid is None else grants.count(old_pid),
            'current_pid_grants':grants.count(current_pid)}


def check_trial(trial_path,token,phase,expected_pid,old_pid,output):
    trial=json.loads((trial_path/'state.json').read_text())
    if trial.get('token')!=token or trial.get('phase')!='observed' or trial.get('main_pid')!=expected_pid:
        raise RuntimeError('trial token, phase or MainPID differs')
    if os.path.realpath('/run/current-system')!=trial['normal_system'] or \
       Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=trial['boot_id']:
        raise RuntimeError('system or boot changed during trial')
    if phase=='restarted' and (old_pid is None or old_pid==expected_pid or Path('/proc/'+str(old_pid)).exists()):
        raise RuntimeError('old compositor is still live or restart identity missing')
    main,fd=check_main(trial,expected_pid)
    denial=run_denial(expected_pid,fd)
    app=run_app_check(expected_pid)
    journal=broker_counts(trial,old_pid,expected_pid)
    final=json.loads((trial_path/'state.json').read_text())
    if final.get('token')!=token or final.get('phase')!='observed' or final.get('main_pid')!=expected_pid or main_pid()!=expected_pid:
        raise RuntimeError('watchdog restored or compositor changed during isolation check')
    report={'schema':SCHEMA,'status':'PASS','evidence_class':'physical-board-normal-service-isolation' if platform.machine().startswith('riscv') else 'host-fixture-only',
            'observed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'phase':phase,'boot_id':trial['boot_id'],'current_system':trial['normal_system'],
            'main':main,'same_uid_denials':denial,'postexec_app':app,'broker':journal,
            'limits':['Postexec fd and named device mapping check; preexec child mapping state is UNVERIFIED.',
                      'No protection from root or compromised compositor is claimed.']}
    if output.exists():raise RuntimeError('preserve prior isolation report')
    output.write_text(json.dumps(report,indent=2)+'\n');output.chmod(0o600)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial',type=Path);p.add_argument('--token');p.add_argument('--phase',choices=('initial','restarted'))
    p.add_argument('--expected-main-pid',type=int);p.add_argument('--old-main-pid',type=int)
    p.add_argument('--output',type=Path)
    p.add_argument('--denial-child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--app-child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--pid',type=int,help=argparse.SUPPRESS);p.add_argument('--fd-number',type=int,help=argparse.SUPPRESS)
    p.add_argument('--socket',type=Path,help=argparse.SUPPRESS);p.add_argument('--nonce',help=argparse.SUPPRESS)
    a=p.parse_args(argv)
    if a.denial_child:
        print(json.dumps(denial_child(a.pid,a.fd_number)));return 0
    if a.app_child:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as peer:
            peer.settimeout(4);peer.connect(str(a.socket));peer.sendall(a.nonce.encode())
            if peer.recv(2)!=b'OK':return 1
        return 0
    if os.geteuid()!=0 or not platform.machine().startswith('riscv'):
        p.error('root on the reserved RISC-V board required')
    if not all((a.trial,a.token,a.phase,a.expected_main_pid,a.output)) or not re.fullmatch('[0-9a-f]{32}',a.token):
        p.error('exact trial identity required')
    if a.output.parent!=a.trial or a.output.name!='isolation-'+a.phase+'.json':
        p.error('report must be within the protected trial output')
    os.umask(0o077)
    try:check_trial(a.trial,a.token,a.phase,a.expected_main_pid,a.old_main_pid,a.output)
    except Exception as error:
        if not a.output.exists():
            a.output.write_text(json.dumps({'schema':SCHEMA,'status':'FAIL','phase':a.phase,
                'observed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'error_type':type(error).__name__},indent=2)+'\n')
            a.output.chmod(0o600)
        raise
    return 0


if __name__=='__main__':raise SystemExit(main())
