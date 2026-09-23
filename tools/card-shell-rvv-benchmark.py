#!/usr/bin/env python3
"""Run matched card workloads ON the reserved board; --prepare is host-only.

Stage this file with card-shell-board-session.py, card-shell-acceptance.py and
card-shell-benchmark.py. The ordinary session is restored after every run;
the operator separately returns from the trial kernel after collecting evidence.
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

HERE=Path(__file__).resolve().parent
SYSTEM='/nix/store/fm8136gg0mfqywdz0hqnxlr8kq2wqflr-nixos-system-nixos-26.11.20260919.20b1ddd'
PACKAGE='/nix/store/lgpv6h5j0d7yiwilnfamnvxrh6m4cgpm-k230-card-shell'
CONFIG='/nix/store/7amq3c8lnlvg82la2g4zxhiik716fgq9-k230-sway.conf'
CLIENT='/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client'
CONTEXT='/nix/store/4gn2z5fi5szrnflhzjsr1kq3f1b39wqx-k230-rvv-context-probe-riscv64-unknown-linux-gnu-0.1/bin/k230-rvv-context-probe'
LIBRARY='/nix/store/brhzfimak2r3c23lmn80y1g6ww6nmb1r-pixman-riscv64-unknown-linux-gnu-0.46.4'
SWAY='/nix/store/9brnyamw2hcfb7yx5zajf0aqcgfsdyyv-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
FILES=('card-shell-rvv-benchmark.py','card-shell-board-session.py','card-shell-acceptance.py','card-shell-benchmark.py')


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    temp=path.with_suffix('.new')
    temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def order(repeats):
    if type(repeats)!=int or not 1<=repeats<=3:raise ValueError('repeats must be 1–3 matched pairs')
    return [(pair,policy) for pair in range(1,repeats+1)
            for policy in (('no-rvv','auto') if pair%2 else ('auto','no-rvv'))]


def environment():
    result={'online_cpus':Path('/sys/devices/system/cpu/online').read_text().strip()}
    frequency=Path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
    def optional_number(path):
        try:return int(path.read_text())
        except (OSError,ValueError):return None
    result['cpu0_frequency_khz']=optional_number(frequency)
    result['thermal_millidegrees']={p.parent.name:optional_number(p) for p in Path('/sys/class/thermal').glob('thermal_zone[0-9]*/temp')}
    return result


def observe_runtime(system,runtime,policy):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        pids=system.sway_pids()
        if len(pids)==1 and (runtime/'wayland/sway-ipc.sock').is_socket():
            proc=Path('/proc')/str(pids[0])
            if str((proc/'exe').resolve())!=SWAY:raise RuntimeError('unexpected compositor executable')
            env=dict(item.split(b'=',1) for item in (proc/'environ').read_bytes().split(b'\0') if b'=' in item)
            expected=b'rvv' if policy=='no-rvv' else b''
            if env.get(b'PIXMAN_DISABLE')!=expected:raise RuntimeError('compositor dispatch policy differs from requested policy')
            group=system.prop('k230-card-shell.service','ControlGroup')
            if '0::'+group not in (proc/'cgroup').read_text().splitlines():raise RuntimeError('compositor is outside the trial cgroup')
            mapped=sorted({line.split()[-1] for line in (proc/'maps').read_text().splitlines() if '/libpixman-1.so' in line})
            if mapped and all(p.startswith(LIBRARY+'/lib/') for p in mapped):
                return {'pid':pids[0],'executable':SWAY,'pixman_policy':policy,
                        'pixman_disable':expected.decode(),'mapped_pixman_files':mapped,
                        'mapping_and_policy_verified':True,
                        'limit':'Uninstrumented renderer: mapped library and process policy observed; callback counters belong to the separate pixel test.'}
        time.sleep(.2)
    raise RuntimeError('trial compositor runtime identity did not become ready')


def compact_budget(report):
    if report['missing_evidence'] or len(report['runs'])!=2:raise RuntimeError('incomplete card workload evidence')
    if {run['session']['cards'] for run in report['runs']}!={1,2}:raise RuntimeError('requires exactly one- and two-card workloads')
    result={}
    for run in report['runs']:
        if run['missing_evidence'] or run['status'] not in ('PASS','FAIL'):raise RuntimeError('incomplete workload metrics')
        result[str(run['session']['cards'])]={'status':run['status'],'submitted_frames':run['submitted_frames'],
                                            'metrics':run['metrics'],'resources':run['resources']}
    return {'board_budget_gate':report['board_budget_gate'],'workloads':result}


def summarize(runs,repeats):
    expected=order(repeats)
    if [(r['pair'],r['policy']) for r in runs]!=expected:raise RuntimeError('missing, duplicated or reordered comparison run')
    for key in ('boot_id','current_system','package','client_sha256','producer_sha256','library_sha256'):
        if len({r[key] for r in runs})!=1:raise RuntimeError('comparison identity changed: '+key)
    if not all(r['measurement_complete'] and r['restored_shell_and_seatd'] for r in runs):raise RuntimeError('incomplete run or restoration')
    for run in runs:
        actual=run['runtime']
        if not actual['mapping_and_policy_verified'] or actual['pixman_policy']!=run['policy'] or actual['pixman_disable']!=('rvv' if run['policy']=='no-rvv' else ''):
            raise RuntimeError('observed dispatch policy differs from paired mode')
    pairs=[]
    for pair in range(1,repeats+1):
        group={r['policy']:r for r in runs if r['pair']==pair}
        pairs.append({'pair':pair,'no_rvv':group['no-rvv']['budget'],'auto_rvv':group['auto']['budget']})
    return {'measurement_status':'COMPLETE','all_card_budgets_pass':all(r['budget']['board_budget_gate']=='PASS' for r in runs),
            'all_interaction_checks_observed':all(r['interaction_exit_code']==0 and r['interaction_failures']==[] for r in runs),
            'pairs':pairs,'limits':['Three pairs are a small serial comparison, not a confidence interval.',
                'Input is injected; presentation feedback is not optical measurement or real-finger acceptance.',
                'A complete measurement may still fail every product performance budget.']}


def one_run(args,pair,policy,modules,boot_id):
    session_module,analyzer=modules
    target=args.output/f'pair-{pair}-{policy}';target.mkdir()
    public=target/'public';public.mkdir()
    runtime=Path('/run/k230-card-shell-rvv'+str(pair)+policy.replace('-',''))
    runtime.mkdir(mode=0o711,exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid!=0 or runtime.stat().st_mode&0o022:raise RuntimeError('untrusted runtime directory')
    # Match the existing CLI setup: root metadata stays private, but the shell
    # account must traverse this parent to its separately owned Wayland dir.
    runtime.chmod(0o711)
    system=session_module.System();session=session_module.Session(runtime,system)
    plan={'package':PACKAGE,'normal_config':CONFIG,'client':CLIENT,'source_revision':args.revision,
          'duration':540,'source_device':'/dev/input/event0','pixman_policy':policy}
    observation={'pair':pair,'policy':policy,'measurement_complete':False,'boot_id':boot_id,
                 'current_system':SYSTEM,'package':PACKAGE,'client_sha256':sha(CLIENT),
                 'producer_sha256':{file:sha(HERE/file) for file in FILES},
                 'library_sha256':sha(Path(LIBRARY)/'lib/libpixman-1.so'),
                 'environment_before':environment(),'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    observation['producer_files_sha256']=observation['producer_sha256']
    observation['producer_sha256']=hashlib.sha256(json.dumps(observation['producer_files_sha256'],sort_keys=True).encode()).hexdigest()
    token=None
    try:
        token=session.arm(plan);session.start();session.input_device()
        observation['runtime']=observe_runtime(system,runtime,policy)
        time.sleep(1.5)
        command=[sys.executable,str(HERE/'card-shell-acceptance.py'),'--execute','--provenance','injected-touch','--runtime',str(runtime),'--output',str(target/'raw')]
        with (target/'acceptance-process-private.log').open('w') as log:
            completed=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=480)
        observation['interaction_exit_code']=completed.returncode
        raw=target/'raw'
        for name in ('acceptance.json','manifest.json','telemetry.log','client-one.jsonl','client-two.jsonl'):
            shutil.copyfile(raw/name,public/name)
        acceptance=json.loads((public/'acceptance.json').read_text())
        observation['interaction_failures']=[row['case'] for row in acceptance['cases'] if row.get('status')=='FAILED']
        report=analyzer.analyze((public/'telemetry.log').read_bytes(),True,json.loads((public/'manifest.json').read_text()))
        write(public/'budget.json',report)
        observation['budget']=compact_budget(report)
        observation['measurement_complete']=True
    finally:
        try:
            if token:
                session.restore(token)
                observation['restored_shell_and_seatd']=system.active('shell.service') and system.active('seatd.service')
                if observation['restored_shell_and_seatd']:
                    system.call(['systemctl','stop',session.state['watchdog']+'.timer'],check=False)
        except BaseException as error:
            observation['restoration_error']=type(error).__name__+': '+str(error)
            raise
        finally:
            observation['environment_after']=environment()
            observation['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            write(public/'run.json',observation)
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot_id:raise RuntimeError('board rebooted during comparison')
    return observation


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--board',action='store_true')
    modes.add_argument('--prepare',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    sequence=order(args.repeats)
    if not re.fullmatch('[a-f0-9]{40}',args.revision):parser.error('requires full source revision')
    if args.output.exists():parser.error('use a new output directory; preserve previous runs')
    plan={'source_revision':args.revision,'repeats':args.repeats,'sequence':sequence,
          'system':SYSTEM,'package':PACKAGE,'config':CONFIG,'client':CLIENT,
          'workload':'unchanged card-shell-acceptance.py: one/two live cards, 24 drags each, thirteen interaction checks',
          'capture_provenance':'injected-touch; native captures remain private and unreviewed',
          'default_image_changed':False}
    if args.prepare:
        args.output.mkdir(parents=True)
        write(args.output/'plan.json',{**plan,'status':'PLANNED_ONLY','board_commands_executed':False})
        return 0
    if os.geteuid()!=0 or not platform.machine().startswith('riscv'):raise RuntimeError('--board runs only on the reserved physical RISC-V board as root')
    if not re.fullmatch(r'/var/lib/k230/rvv-benchmark-[a-z0-9-]+',str(args.output)):raise RuntimeError('use a new protected /var/lib/k230/rvv-benchmark-NAME directory')
    if os.path.realpath('/run/current-system')!=SYSTEM:raise RuntimeError('matching trial system is not running')
    if Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0')!=b'LILYGO T-Display-K230':raise RuntimeError('wrong physical model')
    os.umask(0o077)
    with open('/run/k230-rvv-benchmark.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        args.output.mkdir(mode=0o700,parents=True)
        write(args.output/'plan.json',plan)
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        result={'measurement_status':'INCOMPLETE','plan':plan,'boot_id':boot_id,'runs':[]}
        try:
            c=subprocess.run(['timeout','--kill-after=3s','15s',CONTEXT],capture_output=True,text=True,timeout=22)
            result['context']=json.loads(c.stdout)
            if c.returncode or result['context']['status']!='PASS':raise RuntimeError('physical vector context gate did not pass')
            modules=(load('rvv_session','card-shell-board-session.py'),load('rvv_budget','card-shell-benchmark.py'))
            for pair,policy in sequence:
                write(args.output/'progress.json',{'state':'running','pair':pair,'policy':policy,'finished_runs':len(result['runs']),'boot_id':boot_id})
                run=one_run(args,pair,policy,modules,boot_id)
                result['runs'].append(run)
                write(args.output/'result.json',result)
            result.update(summarize(result['runs'],args.repeats))
            write(args.output/'progress.json',{'state':'completed','finished_runs':len(result['runs']),'boot_id':boot_id})
            return 0
        except BaseException as error:
            result['error_type']=type(error).__name__;result['error']=str(error)
            write(args.output/'progress.json',{'state':'failed','finished_runs':len(result['runs']),'error_type':type(error).__name__,'boot_id':boot_id})
            raise
        finally:
            result['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
            write(args.output/'result.json',result)


if __name__=='__main__':raise SystemExit(main())
