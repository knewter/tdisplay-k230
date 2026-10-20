#!/usr/bin/env python3
"""Bounded, isolated sleeping-thread kernel stacks joined to HDMI frame stalls."""
import argparse
import bisect
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location('drm_wait_base', Path(__file__).with_name('landscape-hdmi-stall-trace.py'))
base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(base)
log, cap = base.log, base.cap
Error = base.TraceError
SCHEMA = 'landscape-drm-wait-v1'
CAPACITY = 50000
SYMBOL = re.compile(r'[A-Za-z_][A-Za-z0-9_.$]{0,191}')
STACK_HEADER = re.compile(r'^\s*.*?-(\d+)\s+(?:\(\s*\d+\)\s+)?\[(\d+)\].*?\s(\d+\.\d+):\s+(?:kernel_stack:\s*)?<stack trace>$')


def expression(pid):
    return f'prev_pid == {pid} && (prev_state == 1 || prev_state == 2)'


def trigger_remaining(text, pid, allow_absent=False):
    rows = [s.strip() for s in text.splitlines() if s.strip() and not s.startswith('#')]
    if not rows and allow_absent: return None
    if len(rows) != 1: raise Error('stack trigger missing or has foreign entries')
    match = re.fullmatch(r'stacktrace:(?:count=)?(\d+) if (.+)', rows[0])
    if (not match or re.sub(r'\s+', '', match[2]) != re.sub(r'\s+', '', expression(pid)) or
            not 0 <= int(match[1]) <= CAPACITY):
        raise Error('stack trigger ownership or count differs')
    return int(match[1])


def frame_symbol(line):
    match = re.fullmatch(r'\s*=>\s+(.+?)\s*', line)
    if not match: raise Error('invalid kernel stack frame')
    value = match[1]
    if re.fullmatch(r'(?:0x)?[0-9a-fA-F]{8,16}|\[<[^>]+>\]', value):
        return '[unresolved]'
    match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_.$]{0,191})(?:\+0x[0-9a-f]+/0x[0-9a-f]+)?(?: \[[A-Za-z0-9_.-]+\])?', value)
    if not match: raise Error('unknown stack payload; raw text is not exported')
    return match[1]


def export(raw, directory, pid):
    """Split strict numeric records and address-free symbols; never export raw lines."""
    numeric_count, stacks = 0, []
    pending = None
    previous = -1
    last_row = None
    def flush():
        nonlocal pending
        if pending is not None:
            if not pending['symbols']: raise Error('empty or truncated kernel stack')
            stacks.append(pending); pending = None
    with raw.open() as src, (directory/'events.jsonl').open('w') as numeric_out:
        for line in src:
            if not line.strip() or line.lstrip().startswith('#'): continue
            if line.lstrip().startswith('=>'):
                if pending is None: raise Error('orphan kernel stack frame')
                if len(pending['symbols']) >= 64: raise Error('kernel stack depth exceeds bound')
                pending['symbols'].append(frame_symbol(line)); continue
            flush()
            header = STACK_HEADER.fullmatch(line.rstrip('\n'))
            if header:
                target, cpu, stamp = int(header[1]), int(header[2]), base.timestamp(header[3])
                if (target != pid or cpu != 0 or stamp < previous or last_row is None or
                        last_row['event'] != 'switch' or last_row['prev_pid'] != pid or
                        last_row['prev_state'] not in ('S', 'D')):
                    raise Error('kernel stack lacks an adjacent target sleeping switch')
                pending = {'pid':pid,'cpu':0,'ts_ns':stamp,'switch_ts_ns':last_row['ts_ns'],'symbols':[]}
                previous = stamp; last_row = None; continue
            row = base.parse_line(line, pid)
            if row is None: continue
            if row['cpu'] != 0 or row['ts_ns'] < previous: raise Error('trace ordering changed')
            previous = row['ts_ns']; numeric_count += 1; last_row = row
            numeric_out.write(json.dumps(row,separators=(',',':'))+'\n')
            if numeric_count > base.MAX_EVENTS or len(stacks) > CAPACITY:
                raise Error('trace event bound exceeded')
    flush()
    with (directory/'stacks.jsonl').open('w') as out:
        for row in stacks: out.write(json.dumps(row,separators=(',',':'))+'\n')
    return numeric_count, len(stacks)


def stack_bytes(directory):
    plain, packed = directory/'stacks.jsonl', directory/'stacks.jsonl.gz'
    if plain.exists() == packed.exists(): raise Error('exactly one symbol stream required')
    with (plain.open('rb') if plain.exists() else gzip.open(packed,'rb')) as src:
        data = src.read(base.MAX_RAW+1)
    if len(data) > base.MAX_RAW: raise Error('expanded symbol stream exceeds bound')
    return data


def checked(directory):
    events, meta = base.checked_events(directory)
    if meta.get('stack_schema') != SCHEMA: raise Error('kernel stack schema differs')
    data = stack_bytes(directory)
    if hashlib.sha256(data).hexdigest() != meta.get('stacks_sha256'):
        raise Error('kernel symbol identity differs')
    stacks = [json.loads(line) for line in data.decode().splitlines()]
    remaining = trigger_remaining(meta['trigger_after'],meta['pid'])
    # The kernel decrements this trigger even with tracing_on=0. This snapshot
    # is after export, so off-window invocations may consume additional count.
    # Exact completeness comes from the recorded S/D switches and ring entries.
    if (remaining <= 0 or len(stacks) != meta['stack_count'] or
            CAPACITY-remaining < len(stacks) or len(stacks) > CAPACITY):
        raise Error('stack trigger exhausted or event count differs')
    if sum(s.get('entries',-base.MAX_EVENTS) for s in meta['stats'].values()) != len(events)+len(stacks):
        raise Error('ring entries differ from numeric and kernel-stack records')
    trigger_remaining(meta['trigger_before'],meta['pid'])
    if trigger_remaining(meta['trigger_before'],meta['pid']) != CAPACITY:
        raise Error('stack trigger initial count differs')
    switches = {r['ts_ns']: r for r in events if r['event']=='switch' and
                r['prev_pid']==meta['pid'] and r['prev_state'] in ('S','D')}
    by_switch = {}; previous = -1
    for s in stacks:
        if (set(s) != {'pid','cpu','ts_ns','switch_ts_ns','symbols'} or
                any(type(s[k]) is not int for k in ('pid','cpu','ts_ns','switch_ts_ns')) or
                s['pid']!=meta['pid'] or s['cpu']!=0 or s['ts_ns']<previous or
                s['switch_ts_ns']>s['ts_ns'] or s['switch_ts_ns'] not in switches or
                s['switch_ts_ns'] in by_switch or type(s['symbols']) is not list or
                not 1<=len(s['symbols'])<=64 or
                any(type(v) is not str or (v!='[unresolved]' and not SYMBOL.fullmatch(v)) for v in s['symbols'])):
            raise Error('unknown/private/ambiguous kernel stack record')
        by_switch[s['switch_ts_ns']] = s; previous = s['ts_ns']
    if set(by_switch) != set(switches): raise Error('missing sleeping switch stack')
    # A captured stack must precede the next target switch-in, even when reading
    # an already exported stream rather than the adjacent raw representation.
    ins=[r['ts_ns'] for r in events if r['event']=='switch' and r['next_pid']==meta['pid']]
    for s in stacks:
        pos=bisect.bisect_left(ins,s['switch_ts_ns'])
        next_in=ins[pos] if pos<len(ins) else None
        if next_in is not None and s['ts_ns']>next_in:
            raise Error('kernel stack lies outside sleeping interval')
    return events, stacks, meta


def stop_owned(state, root=base.ROOT):
    path = base.owned_path(state, root)
    if path.exists():
        for event, expected in state['filters'].items():
            if (path/'events'/event/'filter').read_text().strip()!=expected:
                raise Error('trace event ownership changed')
        trigger = path/'events/sched/sched_switch/trigger'
        remaining = trigger_remaining(trigger.read_text(),state['target_pid'],allow_absent=True)
        (path/'tracing_on').write_text('0')
        if remaining is not None: trigger.write_text('!stacktrace')
        if trigger_remaining(trigger.read_text(),state['target_pid'],allow_absent=True) is not None:
            raise Error('owned stack trigger did not disappear')
    base.stop_owned(state,root)


def cleanup(state_path):
    state = json.loads(state_path.read_text())
    with state_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX); stop_owned(state)
        result={'checked_at':base.now(),'instance_removed':True,'stack_trigger_removed':True,
                'global_controls_unchanged':True,'global_after':base.global_state()}
        log.write_json(state_path.parent/'trace-cleanup.json',result)


class Session(base.Session):
    def prepare(self):
        if Path('/sys/devices/system/cpu/online').read_text().strip()!='0':
            raise Error('bounded stack capture requires only CPU0')
        available=int(re.search(r'^MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)[1])
        if available < 128*1024: raise Error('insufficient memory for stack trace')
        base.atomic_json(self.state_path,self.state)
        unit=self.state['cleanup_unit']
        log.command('systemd-run','--quiet','--unit='+unit,'--on-active=600s',
                    sys.executable,str(Path(__file__).resolve()),'--cleanup',str(self.state_path))
        if log.command('systemctl','is-active',unit+'.timer')!='active':
            raise Error('independent stack cleanup did not arm')
        self.path.mkdir();self.state['inode']=self.path.stat().st_ino
        base.atomic_json(self.state_path,self.state)
        (self.path/'tracing_on').write_text('0');(self.path/'events/enable').write_text('0')
        (self.path/'trace_clock').write_text('mono')
        (self.path/'per_cpu/cpu0/buffer_size_kb').write_text('32768')
        total=int((self.path/'buffer_total_size_kb').read_text().split()[0])
        if total>65536:raise Error('stack trace allocation exceeds64MiB')
        for option in ('sym-addr','sym-offset','userstacktrace'):
            (self.path/'options'/option).write_text('0')
        for event in base.EVENTS:
            expr=(f'prev_pid == {self.target} || next_pid == {self.target}' if event.endswith('sched_switch') else
                  f'pid == {self.target}' if event.endswith('sched_wakeup') else f'common_pid == {self.target}')
            control=self.path/'events'/event;(control/'filter').write_text(expr)
            self.state['filters'][event]=(control/'filter').read_text().strip()
            base.atomic_json(self.state_path,self.state);(control/'enable').write_text('1')
        trigger=self.path/'events/sched/sched_switch/trigger'
        if trigger_remaining(trigger.read_text(),self.target,allow_absent=True) is not None:
            raise Error('new instance already has stack trigger')
        trigger.write_text(f'stacktrace:{CAPACITY} if '+expression(self.target))
        before=trigger.read_text();trigger_remaining(before,self.target)
        if base.global_state()!=self.state['global_before']:raise Error('global tracing changed')
        self.metadata={'schema':base.SCHEMA,'stack_schema':SCHEMA,'pid':self.target,
            'buffer_total_kb':total,'global_before':self.state['global_before'],'markers':{},'trigger_before':before}

    def finish(self):
        self.marker('end');(self.path/'tracing_on').write_text('0')
        stats={}
        for f in sorted((self.path/'per_cpu').glob('cpu*/stats')):
            fields={}
            for line in f.read_text().splitlines():
                if ':' in line:
                    key,value=line.split(':',1)
                    if value.strip().isdecimal():fields[key.strip()]=int(value)
            stats[f.parent.name]=fields
        with (self.path/'trace').open('rb') as src:data=src.read(base.MAX_RAW+1)
        raw=self.directory/'raw.trace';raw.write_bytes(data);raw.chmod(0o600)
        if len(data)>base.MAX_RAW:raise Error('raw stack trace exceeds bound')
        count,stacks=export(raw,self.directory,self.target)
        self.metadata.update(stats=stats,trace_clock=(self.path/'trace_clock').read_text().strip(),
            trigger_after=(self.path/'events/sched/sched_switch/trigger').read_text(),
            raw_sha256=log.digest(raw),raw_bytes=len(data),event_count=count,stack_count=stacks,
            events_sha256=log.digest(self.directory/'events.jsonl'),stacks_sha256=log.digest(self.directory/'stacks.jsonl'),
            tool_sha256=log.digest(Path(__file__)),base_tool_sha256=log.digest(Path(base.__file__)))
        log.write_json(self.directory/'trace.json',self.metadata);checked(self.directory)

    def close(self):
        cleanup(self.state_path)
        log.command('systemctl','stop',self.state['cleanup_unit']+'.timer')
        row=json.loads((self.directory/'trace-cleanup.json').read_text())
        row['cleanup_timer_active']=subprocess.run(['systemctl','is-active','--quiet',self.state['cleanup_unit']+'.timer']).returncode==0
        log.write_json(self.directory/'trace-cleanup.json',row)


def board_smoke(args):
    directory=base.new_directory(args.output);session=Session(directory,os.getpid())
    try:
        session.prepare();session.start();time.sleep(.05);session.finish()
        events,stacks,meta=checked(directory)
        if not any('hrtimer_nanosleep' in s['symbols'] for s in stacks):
            raise Error('harmless sleep stack is unresolved or lacks expected kernel wait')
        log.write_json(directory/'smoke.json',{'schema':SCHEMA,'status':'QUALIFIED','created_at':base.now(),
            'kernel':log.command('uname','-r'),'machine':log.command('uname','-m'),
            'system':os.path.realpath('/run/current-system'),'tool_sha256':log.digest(Path(__file__)),
            'base_tool_sha256':log.digest(Path(base.__file__)),'event_count':len(events),'stack_count':len(stacks),
            'observed_sleep_symbol':'hrtimer_nanosleep'})
    finally:base.safe_close(session)


def capture_run(directory,args,ipc,traced):
    # Reuse the exact established workload with explicit local binding; no
    # module mutation or global tracing change is needed.
    directory.mkdir(mode=0o700);session=Session(directory,ipc.pid) if traced else None
    selected=log.control(ipc);log.idle_startup(ipc)
    subprocess.run(['sudo','-u','shell','env','XDG_RUNTIME_DIR=/run/shell','/run/current-system/sw/bin/k230-shell-rust','--surface','hide'],
        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    ipc.command('[app_id="k230-terminal"] focus');time.sleep(5)
    try:
        if session:session.prepare();session.start()
        code=cap.capture(argparse.Namespace(profile='landscape-1280x800',variant='candidate',input='injected',
            operator_confirmed_contacts=False,seconds=180,drags=24,source_revision=args.source_revision,output=directory/'capture'))
        if session:session.finish()
        base.immutable(selected,log.control(ipc))
        log.write_json(directory/'control.json',{'control':selected,'traced':traced,'capture_exit_code':code,
            'tool_sha256':log.digest(Path(__file__)),'fd_labels':base.fd_labels(ipc.pid)})
        if code:raise Error('capture incomplete; rejected attempt retained')
        return sum(s['wall_ms']>100 for s in base.benchmark(directory/'capture')[2])
    finally:
        if session:base.safe_close(session)


def board_run(args):
    smoke=json.loads((args.smoke/'smoke.json').read_text())
    if (smoke.get('schema')!=SCHEMA or smoke.get('status')!='QUALIFIED' or
            smoke.get('kernel')!=log.command('uname','-r') or smoke.get('machine')!='riscv64' or
            smoke.get('system')!=args.expected_system or smoke.get('tool_sha256')!=log.digest(Path(__file__)) or
            smoke.get('base_tool_sha256')!=log.digest(Path(base.__file__))):
        raise Error('stack controller smoke differs from trial')
    checked(args.smoke)
    cleaned=json.loads((args.smoke/'trace-cleanup.json').read_text())
    if not cleaned.get('stack_trigger_removed') or cleaned.get('cleanup_timer_active') is not False:
        raise Error('stack smoke cleanup incomplete')
    directory=base.new_directory(args.output);ipc=cap.IPC()
    original=log.control(ipc);log.idle_startup(ipc);globals_before=base.global_state()
    if (original['system']!=args.expected_system or original['persistent_system']!=args.expected_system or
            original['executable_sha256']!=args.expected_executable_sha256 or not original['debug_flag']):
        ipc.close();raise Error('installed runtime differs from explicit baseline')
    log.write_json(directory/'original.json',original);log.write_json(directory/'qualified-smoke.json',smoke);runs=[]
    try:
        for name,traced in [('untraced',False),('traced',True),('traced-retry',True)]:
            if name=='traced-retry' and tails:break
            print(json.dumps({'phase':'starting','run':name}),flush=True)
            base.immutable(original,log.control(ipc))
            if base.global_state()!=globals_before:raise Error('global tracing changed before workload')
            tails=capture_run(directory/name,args,ipc,traced);runs.append(name)
            print(json.dumps({'phase':'captured','run':name,'over_100ms':tails}),flush=True)
    finally:
        try:
            ipc.command('card_shell benchmark-stop');ipc.command('card_shell home')
            final=log.control(ipc);base.immutable(original,final)
            if base.global_state()!=globals_before:raise Error('global tracing changed during trial')
            log.write_json(directory/'cleanup.json',{'checked_at':base.now(),'control':final,
                'global_before':globals_before,'global_after':base.global_state(),'home_command_succeeded':True,
                'benchmark_stop_succeeded':True,'idle_terminal':log.idle_startup(ipc),
                'services':log.command('systemctl','is-active','shell.service','shell-ui.service').splitlines(),
                'virtual_test_devices':sum('injected' in r.get('name','').lower() or 'fixture' in r.get('name','').lower() for r in ipc.request(100))})
        finally:ipc.close()
    log.write_json(directory/'trial.json',{'schema':base.SCHEMA,'stack_schema':SCHEMA,'status':'CAPTURED',
        'runs':runs,'source_revision':args.source_revision,'tool_sha256':log.digest(Path(__file__))})


def report(directory):
    if (directory/'trial.json').exists():
        manifest=json.loads((directory/'trial.json').read_text())
        if manifest.get('stack_schema')!=SCHEMA:raise Error('trial stack schema differs')
        result=base.report(directory)
    else:
        result=recovered_report(directory)
    result['schema']=SCHEMA
    for run in result['runs']:
        if run['name']=='untraced':continue
        d=directory/run['name'];events,stacks,meta=checked(d)
        by_switch={s['switch_ts_ns']:s for s in stacks}
        c=run['correlation'];c['stack_count']=len(stacks);c['trigger_remaining']=trigger_remaining(meta['trigger_after'],meta['pid'])
        c['trigger_invocations_outside_recorded_stream']=CAPACITY-c['trigger_remaining']-len(stacks)
        c['counter_scope']='Counter continues while recording is off; exact stream completeness uses ring entries and one stack per recorded S/D switch.'
        for sample in c['late_samples']:
            for off in sample['off_cpu']:
                if off['state'] in ('S','D'):off['kernel_stack']=by_switch[off['start_ns']]
        c['limits'].append('A sleeping stack locates the captured wait; it does not identify a lock holder or prove connector-poll causality.')
    result['limits'].append('Kernel symbol-only exports; unresolved frames remain explicit. No poll/default change.')
    result['report_tool_sha256']=log.digest(Path(__file__))
    return result


def recovered_report(directory):
    """Validate retained complete captures after the old counter checker failed.

    Never manufacture an original success manifest or missing control record.
    Preserve the nonzero driver status and distinguish the final observation.
    """
    recovery=json.loads((directory/'recovery.json').read_text())
    if (recovery.get('original_driver_exit_code')!=2 or recovery.get('original_rejection')!=
            'stack trigger exhausted or event count differs' or recovery.get('runs')!=['untraced','traced'] or
            not re.fullmatch('[0-9a-f]{64}',recovery.get('capture_tool_sha256',''))):
        raise Error('unrecognized postprocessing recovery')
    original=json.loads((directory/'original.json').read_text())
    cleaned=json.loads((directory/'cleanup.json').read_text());base.immutable(original,cleaned['control'])
    if (cleaned['global_before']!=cleaned['global_after'] or cleaned.get('home_command_succeeded') is not True or
            cleaned.get('benchmark_stop_succeeded') is not True or cleaned.get('services')!=['active','active'] or
            cleaned.get('virtual_test_devices')!=0):raise Error('recovered trial cleanup incomplete')
    reference=None;result=[]
    for name in recovery['runs']:
        d=directory/name;row,context,samples=base.benchmark(d/'capture')
        capture_context=json.loads((d/'capture/context.json').read_text())
        if row['source_revision']!=recovery['source_revision'] or capture_context.get('status')!='CAPTURED':
            raise Error('recovered capture is incomplete or has mixed source')
        key={k:row[k] for k in ('source_revision','runtime_identity','physical_geometry','logical_geometry','format','input_class')}
        key.update({k:context[k] for k in ('collector_sha256','injected_workload','output')})
        if reference is None:reference=key
        elif key!=reference:raise Error('recovered workloads differ')
        entry={'name':name,'benchmark':row,'latency':log.distribution([s['wall_ms'] for s in samples])}
        if name=='untraced':
            control=json.loads((d/'control.json').read_text());base.immutable(original,control['control'])
            if control['capture_exit_code']!=0 or control['traced'] is not False:
                raise Error('untraced baseline did not finish normally')
            entry['control']=control
        else:
            if (d/'control.json').exists():raise Error('unexpected original traced control in recovery')
            meta=json.loads((d/'trace.json').read_text())
            if meta['tool_sha256']!=recovery['capture_tool_sha256']:raise Error('recovery capture source differs')
            if original['executable_sha256'] not in json.dumps(row['runtime_identity']):
                raise Error('recovered benchmark executable differs from original/final control')
            c=json.loads((d/'trace-cleanup.json').read_text())
            if (c.get('stack_trigger_removed') is not True or c.get('instance_removed') is not True or
                    c.get('global_controls_unchanged') is not True or c.get('cleanup_timer_active') is not False):
                raise Error('recovered stack cleanup incomplete')
            entry['control_observation']={'original_and_final_controls_match':True,
                'final_control':cleaned['control'],'observed_at':cleaned['checked_at'],
                'capture_context_status':capture_context['status'],'original_traced_control_record_written':False,
                'limit':'The old checker failed after capture and export, before the per-run control record; runtime identity/output come from the capture collector and matching original/final controls.'}
            entry['correlation']=base.correlate(d,samples)
        result.append(entry)
    return {'created_at':base.now(),'status':'MEASURED_AFTER_POSTPROCESSING_RECOVERY',
        'performance_acceptance':'NOT_EVALUATED','recovery':recovery,'report_tool_sha256':log.digest(Path(__file__)),
        'runs':result,'limits':['Original board driver exited 2; its checker rejection is preserved, not relabeled as exit 0.',
        'Offline revalidation retains original captures, timestamps, counts and hashes; no extra hardware run.',
        'Paired direct-IPC main-thread hardware diagnostic; no native/finger/optical or portrait acceptance.',
        'Tracing overhead and syscall wall time require interpretation, not automatic causal labels.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test',action='store_true');group.add_argument('--board-smoke',action='store_true')
    group.add_argument('--board-run',action='store_true');group.add_argument('--report',type=Path);group.add_argument('--cleanup',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--smoke',type=Path)
    parser.add_argument('--source-revision');parser.add_argument('--expected-system');parser.add_argument('--expected-executable-sha256')
    args=parser.parse_args()
    try:
        if args.self_test:
            result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures));return 0 if result.wasSuccessful() else 1
        if args.cleanup:cleanup(args.cleanup)
        elif args.report:
            if args.output is None:parser.error('--report needs --output')
            log.write_json(args.output,report(args.report))
        elif args.board_smoke:
            if args.output is None:parser.error('--board-smoke needs new --output')
            board_smoke(args)
        else:
            if (args.output is None or args.smoke is None or not re.fullmatch('[0-9a-f]{40}',args.source_revision or '') or
                    not re.fullmatch('[0-9a-f]{64}',args.expected_executable_sha256 or '') or
                    not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+',args.expected_system or '')):
                parser.error('trial needs qualified smoke, explicit source/system/executable, new output')
            board_run(args)
    except (Error,log.TrialError,cap.CaptureError,base.baseline.perf.InvalidTrace,OSError,EOFError,
            KeyError,ValueError,subprocess.SubprocessError) as error:
        print('drm-wait: '+str(error),file=sys.stderr);return 2
    return 0


class Fixtures(unittest.TestCase):
    def raw(self):
        return ('task-10 [000] .... 1.000000: tracing_mark_write: K230_STALL start before_ns=999999900\n'
            'task-10 [000] .... 1.100000: sys_enter: NR 29 (7, c03864bc, abcdef, 0, 0, 0)\n'
            'task-10 [000] .... 1.110000: sched_switch: prev_comm=private prev_pid=10 prev_prio=120 prev_state=D ==> next_comm=private next_pid=99 next_prio=120\n'
            'task-10 [000] .... 1.110001: <stack trace>\n => schedule+0x2/0x40\n => dma_fence_wait [drm]\n'
            'task-99 [000] .... 1.300000: sched_wakeup: comm=private pid=10 prio=120 target_cpu=0\n'
            'task-99 [000] .... 1.320000: sched_switch: prev_comm=private prev_pid=99 prev_prio=120 prev_state=R ==> next_comm=private next_pid=10 next_prio=120\n'
            'task-10 [000] .... 1.330000: sys_exit: NR 29 = 0\n'
            'task-10 [000] .... 2.000000: tracing_mark_write: K230_STALL end before_ns=1999999900\n')

    def fixture(self,d):
        raw=d/'raw.trace';raw.write_text(self.raw());count,stacks=export(raw,d,10)
        meta=base.Fixtures().fixture(d)
        export(raw,d,10)
        meta.update(event_count=count,events_sha256=log.digest(d/'events.jsonl'),stack_schema=SCHEMA,
            stack_count=stacks,stacks_sha256=log.digest(d/'stacks.jsonl'),
            trigger_before=f'stacktrace:{CAPACITY} if '+expression(10),trigger_after=f'stacktrace:{CAPACITY-stacks} if '+expression(10))
        meta['stats']['cpu0']['entries']=count+stacks
        log.write_json(d/'trace.json',meta);return meta

    def test_symbol_export_and_unresolved_addresses(self):
        self.assertEqual(frame_symbol(' => dma_fence_wait+0x8/0x24 [drm]'),'dma_fence_wait')
        self.assertEqual(frame_symbol(' => ffffffff80112233'),'[unresolved]')
        for bad in (' => password=abc',' => /private/path',' => symbol arbitrary text','not a frame'):
            with self.subTest(bad=bad),self.assertRaises(Error):frame_symbol(bad)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);events,stacks,_=checked(d)
            self.assertEqual(stacks[0]['symbols'],['schedule','dma_fence_wait'])
            self.assertNotIn('private',(d/'events.jsonl').read_text()+(d/'stacks.jsonl').read_text())

    def test_raw_stack_adjacency_and_truncation(self):
        for mutation in ('orphan','empty','mixedpid','runnable','late','payload'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);raw=self.raw()
                if mutation=='orphan':raw=' => schedule\n'+raw
                elif mutation=='empty':raw=raw.replace(' => schedule+0x2/0x40\n => dma_fence_wait [drm]\n','')
                elif mutation=='mixedpid':raw=raw.replace('task-10 [000] .... 1.110001','task-11 [000] .... 1.110001')
                elif mutation=='runnable':raw=raw.replace('prev_state=D','prev_state=R+')
                elif mutation=='late':raw=raw.replace('1.110001','1.400001')
                else:raw=raw.replace(' => dma_fence_wait [drm]',' => secret=private')
                (d/'raw.trace').write_text(raw)
                with self.assertRaises(Error):export(d/'raw.trace',d,10)

    def test_missing_duplicate_private_stacks_and_trigger_exhaustion(self):
        for mutation in ('missing','duplicate','private','late','exhausted','foreign','loss','clock'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);meta=self.fixture(d);stacks=[json.loads(s) for s in (d/'stacks.jsonl').read_text().splitlines()]
                if mutation=='missing':stacks=[]
                elif mutation=='duplicate':stacks*=2
                elif mutation=='private':stacks[0]['address']='ffffffff80112233'
                elif mutation=='late':stacks[0]['ts_ns']=1400000000
                elif mutation=='exhausted':meta['trigger_after']='stacktrace:0 if '+expression(10)
                elif mutation=='foreign':meta['trigger_after']='stacktrace:49999 if '+expression(11)
                elif mutation=='loss':meta['stats']['cpu0']['overrun']=1
                else:meta['trace_clock']='[local] mono'
                (d/'stacks.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in stacks))
                meta['stacks_sha256']=log.digest(d/'stacks.jsonl');meta['stack_count']=len(stacks)
                if mutation in ('missing','duplicate'):meta['trigger_after']=f'stacktrace:{CAPACITY-len(stacks)} if '+expression(10)
                log.write_json(d/'trace.json',meta)
                with self.assertRaises(Error):checked(d)

    def test_compressed_identity_expansion_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);plain=d/'stacks.jsonl';data=plain.read_bytes()
            packed=d/'stacks.jsonl.gz';packed.write_bytes(gzip.compress(data,mtime=0))
            with self.assertRaises(Error):checked(d)
            plain.unlink();self.assertEqual(len(checked(d)[1]),1)
            with mock.patch.object(base,'MAX_RAW',10),self.assertRaises(Error):checked(d)
            packed.write_bytes(gzip.compress(data+b' ',mtime=0))
            with self.assertRaises(Error):checked(d)

    def test_trigger_ownership_precedes_mutation(self):
        self.assertEqual(trigger_remaining('stacktrace:count=50000 if '+expression(10),10),50000)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name='k230-stall-'+'a'*16;p=root/'instances'/name;p.mkdir(parents=True)
            control=p/'events/sched/sched_switch';control.mkdir(parents=True)
            (control/'filter').write_text('ours');(control/'trigger').write_text('stacktrace:49999 if '+expression(11))
            (p/'tracing_on').write_text('1')
            state={'instance':name,'inode':p.stat().st_ino,'target_pid':10,'filters':{'sched/sched_switch':'ours'}}
            with self.assertRaises(Error):stop_owned(state,root)
            self.assertEqual((p/'tracing_on').read_text(),'1')
            (control/'trigger').write_text('stacktrace:49999 if '+expression(10));(control/'filter').write_text('foreign')
            with self.assertRaises(Error):stop_owned(state,root)
            self.assertEqual((p/'tracing_on').read_text(),'1')

    def test_counter_may_advance_off_window_but_coverage_cannot_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);meta=self.fixture(d)
            meta['trigger_after']='stacktrace:count=49990 if '+expression(10)
            log.write_json(d/'trace.json',meta);self.assertEqual(len(checked(d)[1]),1)
            meta['stats']['cpu0']['entries']+=1;log.write_json(d/'trace.json',meta)
            with self.assertRaises(Error):checked(d)
            meta['stats']['cpu0']['entries']-=1
            meta['trigger_after']='stacktrace:count=50000 if '+expression(10)
            log.write_json(d/'trace.json',meta)
            with self.assertRaises(Error):checked(d)

    def test_recovery_rejects_unknown_original_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            log.write_json(d/'recovery.json',{'original_driver_exit_code':0})
            with self.assertRaises(Error):recovered_report(d)

    def test_smoke_failure_cleans_owned_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            class Fake:
                def __init__(self,directory,target):self.state_path=directory/'state'
                def prepare(self):self.state_path.touch()
                def start(self):calls.append('start')
                def close(self):calls.append('close')
            with mock.patch(__name__+'.Session',Fake),mock.patch('time.sleep',side_effect=OSError('fixture')):
                with self.assertRaises(OSError):board_smoke(argparse.Namespace(output=Path(tmp)/'new'))
            self.assertEqual(calls,['start','close'])

    def test_base_clock_loss_and_frame_guards(self):
        suite=unittest.TestSuite(base.Fixtures(name) for name in ('test_clock_loss_and_public_schema_guards',
            'test_partial_events_only_outside_qualified_window','test_real_benchmark_parser_keeps_frame_join_gate'))
        result=unittest.TestResult();suite.run(result);self.assertTrue(result.wasSuccessful(),result.errors+result.failures)


if __name__=='__main__':raise SystemExit(main())
