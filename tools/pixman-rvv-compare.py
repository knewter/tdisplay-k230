#!/usr/bin/env python3
"""Compare every declared Pixman pixel byte; QEMU and physical proof stay separate."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid

IDENTITY_FILE = Path(__file__).with_name('rvv-candidate-identity.py')
spec = importlib.util.spec_from_file_location('rvv_candidate_identity', IDENTITY_FILE)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)
EXPECTED={f'{s}-{d}-{mode}-w{w}' for s in ('rgb565','argb8888','xrgb8888') for d in ('rgb565','argb8888') for mode in ('copy','over','nearest','bilinear') for w in (1,7,15,16,17,31,64,568)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_case_set(binary, target, prefix, vector, corrupt=False, library=None):
    target.mkdir()
    env=os.environ.copy()
    env.pop('PIXMAN_DISABLE',None)
    if not vector: env['PIXMAN_DISABLE']='rvv'
    if library is not None:env['LD_DEBUG']='libs'
    command=prefix+[str(binary),str(target)]+(['--corrupt'] if corrupt else [])
    p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=90)
    if p.returncode:
        raise RuntimeError(f'pixel process exited {p.returncode}: '+p.stderr[-600:])
    if library is not None:identity.require_loaded_pixel_library(p.stderr,{'pixman_library':library})
    cases={}
    summaries=[]
    for line in p.stdout.splitlines():
        if line.startswith('K230_PIXELS_CASE '):
            item=json.loads(line.split(' ',1)[1])
            if item['case'] in cases:raise RuntimeError('duplicate case report')
            cases[item['case']]=item
        if line.startswith('K230_PIXELS_SUMMARY '):summaries.append(json.loads(line.split(' ',1)[1]))
    if set(cases)!=EXPECTED or len(summaries)!=1:raise RuntimeError('missing or unexpected pixel cases')
    summary=summaries[0]
    if summary['cases']!=len(EXPECTED) or summary['vector_dispatch_enabled']!=vector or summary['corrupt_control']!=corrupt:
        raise RuntimeError('incorrect case-set mode')
    if summary['implementation_depth']!=(4 if vector else 3):raise RuntimeError('unexpected dispatch chain')
    if bool(summary['rvv_fast_calls']+summary['rvv_combine_calls'])!=vector:raise RuntimeError('dispatch counters do not match mode')
    if sum(v['rvv_fast_calls'] for v in cases.values())!=summary['rvv_fast_calls'] or sum(v['rvv_combine_calls'] for v in cases.values())!=summary['rvv_combine_calls']:
        raise RuntimeError('dispatch counter totals differ')
    if {p.stem for p in target.glob('*.bin')}!=EXPECTED:raise RuntimeError('missing or extra pixel outputs')
    for name,item in cases.items():
        if (target/(name+'.bin')).stat().st_size!=item['bytes']:raise RuntimeError('pixel output size mismatch')
    return {'command':command,'summary':summary,'cases':cases}


def compare_files(left,right,names):
    results=[]
    for name in sorted(names):
        a=(left/(name+'.bin')).read_bytes();b=(right/(name+'.bin')).read_bytes()
        differences=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        same=a==b
        results.append({'case':name,'equal':same,'bytes':len(a),'other_bytes':len(b),
                        'left_sha256':hashlib.sha256(a).hexdigest(),'right_sha256':hashlib.sha256(b).hexdigest(),
                        'different_bytes':len(differences)+abs(len(a)-len(b)),'first_differences':differences[:8]})
    return results


def measure(args, candidate):
    binary=identity.file_for(candidate, 'pixel_probe')
    result={'status':'FAIL','evidence_class':'physical-board-pixman-pixels' if args.probe else 'qemu-user-pixman-pixels',
            'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'package':candidate['pixel_probe'],'probe_sha256':digest(binary),'library':candidate['pixman_library'],'library_sha256':digest(candidate['pixman_library']),
            'candidate_manifest_sha256':digest(args.manifest),'candidate_system':candidate['system'],'candidate_kernel':candidate['kernel'],
            'kernel_image_artifact_sha256':candidate['sha256']['kernel_image'],
            'checker_sha256':digest(__file__),'identity_helper_sha256':digest(IDENTITY_FILE),'token':args.token,
            'limits':['Instrumented callbacks prove dispatch and pixels, not renderer cost.',
                      'Kernel Image hash binds the system artifact, not the executing kernel in a one-time boot.',
                      'Declared integer RGB565/ARGB/XRGB cases only; no exhaustive Pixman or physical display claim.']}
    if args.probe:
        identity.require_board(candidate)
        model='LILYGO T-Display-K230'
        c=subprocess.run(['timeout','--kill-after=3s','15s',candidate['context_probe']],capture_output=True,text=True,timeout=22)
        context=json.loads(c.stdout)
        if c.returncode or context['status']!='PASS':raise RuntimeError('physical vector context gate did not pass')
        result.update(current_system=candidate['system'],model=model,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),context=context)
        prefix=[]
    else:
        if not args.qemu:raise RuntimeError('requires --board or --qemu')
        prefix=[args.qemu,'-cpu','rv64,v=true,vlen=128,elen=64']
    with tempfile.TemporaryDirectory(prefix='k230-pixman-pixels-',dir='/run' if args.probe else None) as tmp:
        root=Path(tmp)
        library=candidate['pixman_library'] if args.probe else None
        scalar=run_case_set(binary,root/'scalar',prefix,False,library=library)
        vector=run_case_set(binary,root/'vector',prefix,True,library=library)
        corrupt=run_case_set(binary,root/'corrupt',prefix,True,True,library=library)
        compared=compare_files(root/'scalar',root/'vector',EXPECTED)
        negative=compare_files(root/'vector',root/'corrupt',EXPECTED)
        changed=[x for x in negative if not x['equal']]
        control_pass=len(changed)==1 and changed[0]['case']=='rgb565-rgb565-copy-w1' and changed[0]['different_bytes']==1
        result.update(runs={'scalar':scalar,'vector':vector,'corrupt':corrupt},comparison=compared,
                      corrupt_control={'status':'PASS' if control_pass else 'FAIL','different_cases':changed},
                      differing_cases=sum(not x['equal'] for x in compared),case_count=len(compared))
        result['status']='PASS' if control_pass and all(x['equal'] for x in compared) else 'FAIL'
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',action='store_true')
    p.add_argument('--qemu',help='QEMU user binary; diagnostic execution only, never physical proof')
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--manifest-sha256',help=argparse.SUPPRESS)
    p.add_argument('--helper-sha256',help=argparse.SUPPRESS)
    p.add_argument('--output',type=Path)
    p.add_argument('--probe',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--token',help=argparse.SUPPRESS)
    args=p.parse_args(argv)
    if args.helper_sha256 and digest(IDENTITY_FILE)!=args.helper_sha256:
        raise RuntimeError('staged candidate identity helper hash differs')
    candidate=identity.load(args.manifest,expected_sha256=args.manifest_sha256)
    if str(args.package)!=candidate['pixel_probe']:p.error('pixel package differs from candidate manifest')
    if not args.probe:identity.require_pixel_linkage(candidate)
    if args.probe:
        if not args.token or not re.fullmatch('[a-f0-9]{32}',args.token):p.error('requires capture token')
        report=measure(args,candidate);print('K230_PIXELS_RESULT '+json.dumps(report,sort_keys=True),flush=True)
    else:
        if not args.output or args.output.exists():p.error('use a new output directory')
        if bool(args.board)==bool(args.qemu):p.error('choose exactly one of --board or --qemu')
        args.token=uuid.uuid4().hex
        args.output.mkdir(parents=True)
        if args.board:
            root=Path(__file__).resolve().parent;remote='/run/pixman-rvv-compare-'+args.token+'.py'
            remote_helper='/run/rvv-candidate-identity.py'
            remote_manifest='/run/rvv-candidate-'+args.token+'.json'
            cmd=shlex.join([candidate['python'],'-I',remote,'--probe','--token',args.token,'--package',str(args.package),
                            '--manifest',remote_manifest,'--manifest-sha256',digest(args.manifest),
                            '--helper-sha256',digest(IDENTITY_FILE)])
            with open('/tmp/k230-board.lock','a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                subprocess.run([sys.executable,str(root/'push-file.py'),'--src',str(Path(__file__).resolve()),'--dest',remote],capture_output=True,text=True,timeout=90,check=True)
                subprocess.run([sys.executable,str(root/'push-file.py'),'--src',str(IDENTITY_FILE),'--dest',remote_helper],capture_output=True,text=True,timeout=90,check=True)
                subprocess.run([sys.executable,str(root/'push-file.py'),'--src',str(args.manifest),'--dest',remote_manifest],capture_output=True,text=True,timeout=90,check=True)
                capture=subprocess.run([sys.executable,str(root/'console.py'),'--wait=45',cmd],capture_output=True,text=True,timeout=180,check=True).stdout
            lines=[l for l in capture.splitlines() if l.startswith('K230_PIXELS_RESULT ')]
            if len(lines)!=1:
                fd,private_path=tempfile.mkstemp(prefix='k230-pixman-rvv-',suffix='.serial.log')
                with os.fdopen(fd,'w') as out:out.write(capture)
                failure={'status':'FAIL','error':'missing or ambiguous board pixel report','private_capture':private_path,'capture_sha256':hashlib.sha256(capture.encode()).hexdigest()}
                (args.output/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
                raise RuntimeError('missing board pixel report; private capture retained at '+private_path)
            report=json.loads(lines[0].split(' ',1)[1])
            if report['token']!=args.token or report['candidate_manifest_sha256']!=digest(args.manifest) or report['identity_helper_sha256']!=digest(IDENTITY_FILE):
                raise RuntimeError('stale or mismatched pixel report')
            (args.output/'report.serial.log').write_text(lines[0]+'\n')
        else:report=measure(args,candidate)
        (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:report[k] for k in ['status','evidence_class','case_count','differing_cases']}))
    if report['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
