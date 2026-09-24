#!/usr/bin/env python3
"""Paired cache-off/cache-on injected acceptance on the reserved normal board.

Stage beside the three published card session/acceptance/budget tools. Raw
captures and process logs remain private; fixed public reports retain failures.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

SYSTEM='/nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd'
PACKAGE='/nix/store/hxilq8jdlb0b8mj8jzmvhwsw9mwnr69y-k230-card-shell'
SWAY='/nix/store/6an3zjnjv5jbyxzh80cm0cnaajq6spx9-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
CONFIG='/nix/store/7amq3c8lnlvg82la2g4zxhiik716fgq9-k230-sway.conf'
CLIENT='/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client'


def write(path, value):
    temp=path.with_suffix('.new');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def runtime_directory(output, index):
    namespace=hashlib.sha256(str(output).encode()).hexdigest()[:16]
    return Path('/run/k230-card-shell-cache'+namespace+str(index))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',action='store_true',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if not re.fullmatch('[a-f0-9]{40}',args.revision):p.error('full source revision required')
    if not re.fullmatch('/var/lib/k230/card-scaled-cache-[a-z0-9-]+',str(args.output)) or args.output.exists():p.error('new protected output required')
    if os.geteuid()!=0 or not platform.machine().startswith('riscv') or os.path.realpath('/run/current-system')!=SYSTEM:raise RuntimeError('requires reserved normal RISC-V board')
    if Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0')!=b'LILYGO T-Display-K230':raise RuntimeError('wrong model')
    here=Path(__file__).resolve().parent
    session_module=load('session',here/'card-shell-board-session.py')
    analyzer=load('budget',here/'card-shell-benchmark.py')
    for artifact in (PACKAGE+'/bin/card-shell',SWAY,CONFIG,CLIENT):
        if not Path(artifact).is_file():raise RuntimeError('declared store artifact is not installed: '+artifact)
    os.umask(0o077)
    with open('/run/k230-card-scaled-cache.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        args.output.mkdir(mode=0o700)
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        result={'status':'INCOMPLETE','revision':args.revision,'boot_id':boot,'system':SYSTEM,'package':PACKAGE,'sway':SWAY,'client':CLIENT,'config':CONFIG,'evidence_class':'board-injected','workload':'same 13 acceptance cases and 24 drags per card count in each arm','runs':[],
                'producer_sha256':{name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in ('run-board.py','card-shell-board-session.py','card-shell-acceptance.py','card-shell-benchmark.py')}}
        try:
            for index,cache_policy in enumerate(('off','on'),1):
                write(args.output/'progress.json',{'state':'running','run':index,'scaled_cache':cache_policy,'finished_runs':len(result['runs'])})
                target=args.output/('run-'+str(index)+'-'+cache_policy);target.mkdir();public=target/'public';public.mkdir()
                runtime=runtime_directory(args.output,index)
                if not session_module.RUNTIME_PATH.fullmatch(str(runtime)):
                    raise RuntimeError('runtime must satisfy the session guard before arming')
                if runtime.exists():raise RuntimeError('preserve previous runtime directory')
                runtime.mkdir(mode=0o711);runtime.chmod(0o711)
                system=session_module.System();session=session_module.Session(runtime,system)
                observation={'run':index,'scaled_cache':cache_policy,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
                token=None
                try:
                    token=session.arm({'package':PACKAGE,'normal_config':CONFIG,'client':CLIENT,'source_revision':args.revision,'duration':540,'source_device':'/dev/input/event0','pixman_policy':'auto','scaled_cache':cache_policy})
                    session.start();session.input_device()
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        pids=system.sway_pids()
                        if len(pids)==1 and (runtime/'wayland/sway-ipc.sock').is_socket():
                            proc=Path('/proc')/str(pids[0])
                            if str((proc/'exe').resolve())!=SWAY:raise RuntimeError('wrong compositor executable')
                            observation['running_sway']=SWAY;break
                        time.sleep(.2)
                    else:raise RuntimeError('compositor did not become ready')
                    with (target/'process-private.log').open('w') as log:
                        run=subprocess.run([sys.executable,str(here/'card-shell-acceptance.py'),'--execute','--provenance','injected-touch','--runtime',str(runtime),'--output',str(target/'raw')],stdout=log,stderr=subprocess.STDOUT,timeout=480)
                    observation['acceptance_exit_code']=run.returncode
                    for name in ('acceptance.json','manifest.json','telemetry.log','client-one.jsonl','client-two.jsonl'):
                        shutil.copyfile(target/'raw'/name,public/name)
                    acceptance=json.loads((public/'acceptance.json').read_text())
                    observation['checks']=[r for r in acceptance['cases'] if 'case' in r]
                    manifest=json.loads((public/'manifest.json').read_text())
                    if manifest['package_store_path']!=PACKAGE or manifest['source_revision']!=args.revision:
                        raise RuntimeError('acceptance manifest differs from the paired package or revision')
                    report=analyzer.analyze((public/'telemetry.log').read_bytes(),True,json.loads((public/'manifest.json').read_text()))
                    write(public/'budget.json',report)
                    observation['budget_gate']=report['board_budget_gate'];observation['missing_evidence']=report['missing_evidence']
                    cache_rows=[line for line in (public/'telemetry.log').read_text().splitlines() if line.startswith('K230_CARD_SHELL scaled-cache ')]
                    observation['scaled_cache_rows']=len(cache_rows)
                    if cache_policy=='on' and not cache_rows:raise RuntimeError('enabled cache emitted no diagnostic rows')
                    if cache_policy=='off' and cache_rows:raise RuntimeError('disabled cache emitted diagnostic rows')
                except BaseException as error:
                    observation['error']=type(error).__name__+': '+str(error)
                    raise
                finally:
                    try:
                        if token:
                            session.restore(token)
                            observation['restored_shell_and_seatd']=system.active('shell.service') and system.active('seatd.service')
                            if observation['restored_shell_and_seatd']:system.call(['systemctl','stop',session.state['watchdog']+'.timer'],check=False)
                            session.collect(public/'session')
                            if json.loads((public/'session/session.json').read_text()).get('scaled_cache')!=cache_policy:
                                raise RuntimeError('session manifest differs from requested cache policy')
                    except BaseException as error:
                        observation['restore_or_collect_error']=type(error).__name__+': '+str(error)
                        raise
                    finally:
                        observation['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
                        write(public/'run.json',observation)
                        result['runs'].append(observation);write(args.output/'result.json',result)
                if not observation.get('restored_shell_and_seatd'):raise RuntimeError('normal session not restored')
                if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:raise RuntimeError('board rebooted during runs')
            result['status']='COLLECTED'
            result['all_interaction_checks_observed']=all(r['acceptance_exit_code']==0 and len(r['checks'])==13 and all(c['status']=='OBSERVED' for c in r['checks']) for r in result['runs'])
            result['both_budgets_pass']=all(r['budget_gate']=='PASS' for r in result['runs'])
            write(args.output/'progress.json',{'state':'completed','finished_runs':2})
        except BaseException as e:
            result['error']=type(e).__name__+': '+str(e)
            write(args.output/'progress.json',{'state':'failed','finished_runs':len(result['runs'])})
            raise
        finally:write(args.output/'result.json',result)


if __name__=='__main__':main()
