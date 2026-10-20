#!/usr/bin/env python3
"""Bounded connector-poll critical sections correlated with landscape DRM waits."""
import argparse
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

_spec = importlib.util.spec_from_file_location('holder_base', Path(__file__).with_name('landscape-hdmi-stall-trace.py'))
base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(base)
log, cap = base.log, base.cap
Error = base.TraceError
SCHEMA = 'landscape-drm-holder-v1'
FUNCTIONS = frozenset(('output_poll_execute', 'drm_helper_probe_detect', 'drm_helper_probe_detect_ctx',
    'detect_connector_status', 'lt9611_bridge_detect', 'drm_modeset_backoff', 'drm_modeset_drop_locks'))
FUNCTION_LINE = re.compile(r'^\s*.*?-(\d+)\s+(?:\(\s*\d+\)\s+)?\[(\d+)\].*?\s(\d+\.\d+):\s+(?:function:\s*)?([A-Za-z_][A-Za-z0-9_.$]*)(?:\s+<-([A-Za-z_][A-Za-z0-9_.$]*))?\s*$')


def export(raw, directory, target):
    count = 0; functions = []; previous = -1
    with raw.open() as src, (directory/'events.jsonl').open('w') as out:
        for line in src:
            if not line.strip() or line.lstrip().startswith('#'): continue
            match = FUNCTION_LINE.fullmatch(line.rstrip('\n'))
            if match:
                pid, cpu, stamp, symbol, parent = match.groups()
                if symbol not in FUNCTIONS: raise Error('unknown function payload; raw text is not exported')
                row = {'pid':int(pid),'cpu':int(cpu),'ts_ns':base.timestamp(stamp),'symbol':symbol,'parent':parent if parent in FUNCTIONS else '[other]'}
                functions.append(row)
            else:
                row = base.parse_line(line,target)
                if row is None: continue
                count += 1; out.write(json.dumps(row,separators=(',',':'))+'\n')
            if row['cpu'] != 0 or row['ts_ns'] < previous: raise Error('mixed CPU or trace order')
            previous = row['ts_ns']
            if count+len(functions) > base.MAX_EVENTS: raise Error('trace record bound exceeded')
    with (directory/'functions.jsonl').open('w') as out:
        for row in functions: out.write(json.dumps(row,separators=(',',':'))+'\n')
    return count,len(functions)


def function_bytes(directory):
    plain,packed = directory/'functions.jsonl',directory/'functions.jsonl.gz'
    if plain.exists() == packed.exists(): raise Error('exactly one function stream required')
    with (plain.open('rb') if plain.exists() else gzip.open(packed,'rb')) as src:
        data = src.read(base.MAX_RAW+1)
    if len(data) > base.MAX_RAW: raise Error('expanded function stream exceeds bound')
    return data


def checked_events(directory):
    events,meta = base.checked_events(directory)
    if meta.get('holder_schema') != SCHEMA: raise Error('holder trace schema differs')
    data = function_bytes(directory)
    if hashlib.sha256(data).hexdigest() != meta.get('functions_sha256'): raise Error('function stream identity differs')
    functions = [json.loads(line) for line in data.decode().splitlines()]
    previous = -1
    for row in functions:
        if (set(row) != {'pid','cpu','ts_ns','symbol','parent'} or
            any(type(row[k]) is not int for k in ('pid','cpu','ts_ns')) or row['pid'] <= 0 or
            row['cpu'] != 0 or row['ts_ns'] < previous or row['symbol'] not in FUNCTIONS or (row['parent']!='[other]' and row['parent'] not in FUNCTIONS)):
            raise Error('unknown/private/unordered function record')
        previous = row['ts_ns']
    if (len(functions) != meta.get('function_count') or len(events)+len(functions) > base.MAX_EVENTS or
        sum(s.get('entries',-base.MAX_EVENTS) for s in meta['stats'].values()) != len(events)+len(functions)):
        raise Error('ring entries differ from numeric and function streams')
    if meta.get('function_filter') != sorted(FUNCTIONS) or meta.get('current_tracer') != 'function':
        raise Error('function filter/tracer differs')
    start,end = (next(e['ts_ns'] for e in events if e['event']=='marker' and e['phase']==p) for p in ('start','end'))
    return events,[r for r in functions if start <= r['ts_ns'] <= end],meta


def intervals(functions):
    """Conservative per-probe lock intervals within one polling invocation."""
    pending={};result=[];rejected=[]
    def reset(p):
        p.update(helper_ns=None,probe_ns=None,detect_ns=None,bridge_ns=None)
    def reject(pid,reason):
        if pid in pending:
            p=pending[pid];rejected.append({'pid':pid,'poll_ns':p['poll_ns'],'reason':reason})
            del pending[pid]
    for row in functions:
        pid,symbol,stamp=row['pid'],row['symbol'],row['ts_ns']
        if symbol=='output_poll_execute':
            if pid in pending and pending[pid]['probe_ns'] is not None:reject(pid,'next poll before probe completed')
            pending[pid]={'pid':pid,'poll_ns':stamp};reset(pending[pid])
        elif pid in pending:
            p=pending[pid]
            if symbol=='drm_helper_probe_detect':
                if p['helper_ns'] is not None or row['parent']!='output_poll_execute':reject(pid,'probe helper lacks polling caller')
                else:p['helper_ns']=stamp
            elif symbol=='drm_helper_probe_detect_ctx':
                # GCC may inline the tiny helper entirely. A direct polling
                # caller proves origin without requiring a missing entry.
                caller=(row['parent']=='output_poll_execute' or
                        (row['parent']=='drm_helper_probe_detect' and p['helper_ns'] is not None))
                if p['probe_ns'] is not None or not caller:reject(pid,'ambiguous probe caller/order')
                else:p['probe_ns']=stamp
            elif symbol=='detect_connector_status':
                if p['probe_ns'] is None or p['detect_ns'] is not None or row['parent']!='drm_helper_probe_detect_ctx':reject(pid,'ambiguous detection order')
                else:p['detect_ns']=stamp
            elif symbol=='lt9611_bridge_detect' and p['probe_ns'] is not None:
                if p['detect_ns'] is None or p['bridge_ns'] is not None:reject(pid,'ambiguous bridge order')
                else:p['bridge_ns']=stamp
            elif symbol=='drm_modeset_backoff' and p['probe_ns'] is not None:reject(pid,'lock backoff invalidates held interval')
            elif symbol=='drm_modeset_drop_locks' and p['probe_ns'] is not None:
                if p['bridge_ns'] is None or row['parent']!='drm_helper_probe_detect_ctx':reject(pid,'drop without complete LT9611 detect path')
                else:
                    result.append(dict(p,drop_ns=stamp,held_lower_bound_ms=(stamp-p['detect_ns'])/1e6));reset(p)
    for pid,p in list(pending.items()):
        if p['probe_ns'] is not None:reject(pid,'capture boundary before probe completed')
    return result,rejected


def function_ownership(path,state):
    actual = [s.split()[0] for s in (path/'set_ftrace_filter').read_text().splitlines() if s.strip() and not s.startswith('#')]
    if (sorted(actual) != state.get('function_filter') or
        (path/'current_tracer').read_text().strip() != state.get('function_tracer')):
        raise Error('function tracer/filter ownership changed')


def cleanup(state_path):
    state = json.loads(state_path.read_text())
    with state_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);path = base.owned_path(state)
        if path.exists() and state.get('function_tracer') is not None:
            function_ownership(path,state)
            (path/'tracing_on').write_text('0');(path/'current_tracer').write_text('nop')
        base.stop_owned(state)
        log.write_json(state_path.parent/'trace-cleanup.json',{'checked_at':base.now(),
            'instance_removed':True,'function_tracer_removed':True,'global_controls_unchanged':True,
            'global_after':base.global_state()})


class Session(base.Session):
    def prepare(self):
        if Path('/sys/devices/system/cpu/online').read_text().strip() != '0': raise Error('requires only CPU0 online')
        available = int(re.search(r'^MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)[1])
        if available < 128*1024: raise Error('insufficient free memory')
        base.atomic_json(self.state_path,self.state)
        unit = self.state['cleanup_unit']
        log.command('systemd-run','--quiet','--unit='+unit,'--on-active=600s',sys.executable,
                    str(Path(__file__).resolve()),'--cleanup',str(self.state_path))
        if log.command('systemctl','is-active',unit+'.timer') != 'active': raise Error('cleanup timer did not arm')
        self.path.mkdir();self.state['inode']=self.path.stat().st_ino;base.atomic_json(self.state_path,self.state)
        (self.path/'tracing_on').write_text('0');(self.path/'events/enable').write_text('0')
        (self.path/'trace_clock').write_text('mono');(self.path/'per_cpu/cpu0/buffer_size_kb').write_text('32768')
        total = int((self.path/'buffer_total_size_kb').read_text().split()[0])
        if total > 65536: raise Error('buffer exceeds64MiB')
        for event in base.EVENTS:
            expr = (f'prev_pid == {self.target} || next_pid == {self.target}' if event.endswith('sched_switch') else
                    f'pid == {self.target}' if event.endswith('sched_wakeup') else f'common_pid == {self.target}')
            control=self.path/'events'/event;(control/'filter').write_text(expr)
            self.state['filters'][event]=(control/'filter').read_text().strip()
            base.atomic_json(self.state_path,self.state);(control/'enable').write_text('1')
        (self.path/'set_ftrace_filter').write_text('\n'.join(sorted(FUNCTIONS)))
        (self.path/'current_tracer').write_text('function')
        self.state.update(function_filter=sorted(FUNCTIONS),function_tracer='function')
        base.atomic_json(self.state_path,self.state);function_ownership(self.path,self.state)
        if base.global_state()!=self.state['global_before']: raise Error('global controls changed')
        self.metadata={'schema':base.SCHEMA,'holder_schema':SCHEMA,'pid':self.target,'buffer_total_kb':total,
            'global_before':self.state['global_before'],'markers':{},'function_filter':sorted(FUNCTIONS),'current_tracer':'function'}

    def finish(self):
        self.marker('end');(self.path/'tracing_on').write_text('0');function_ownership(self.path,self.state)
        stats={}
        for f in sorted((self.path/'per_cpu').glob('cpu*/stats')):
            fields={}
            for line in f.read_text().splitlines():
                if ':' in line:
                    k,v=line.split(':',1)
                    if v.strip().isdecimal():fields[k.strip()]=int(v)
            stats[f.parent.name]=fields
        with (self.path/'trace').open('rb') as src:data=src.read(base.MAX_RAW+1)
        if len(data)>base.MAX_RAW:raise Error('raw trace exceeds bounded export')
        raw=self.directory/'raw.trace';raw.write_bytes(data);raw.chmod(0o600)
        count,functions=export(raw,self.directory,self.target)
        self.metadata.update(stats=stats,trace_clock=(self.path/'trace_clock').read_text().strip(),
            raw_sha256=log.digest(raw),raw_bytes=len(data),event_count=count,function_count=functions,
            events_sha256=log.digest(self.directory/'events.jsonl'),functions_sha256=log.digest(self.directory/'functions.jsonl'),
            tool_sha256=log.digest(Path(__file__)),base_tool_sha256=log.digest(Path(base.__file__)))
        log.write_json(self.directory/'trace.json',self.metadata);checked_events(self.directory)

    def close(self):
        cleanup(self.state_path);log.command('systemctl','stop',self.state['cleanup_unit']+'.timer')
        row=json.loads((self.directory/'trace-cleanup.json').read_text())
        row['cleanup_timer_active']=subprocess.run(['systemctl','is-active','--quiet',self.state['cleanup_unit']+'.timer']).returncode==0
        log.write_json(self.directory/'trace-cleanup.json',row)


def board_smoke(args):
    directory=base.new_directory(args.output);session=Session(directory,os.getpid())
    try:
        session.prepare();session.start()
        # Fixed 25s idle observation includes at least two nominal 10s poll periods.
        time.sleep(25);session.finish()
        events,functions,meta=checked_events(directory);held,rejected=intervals(functions)
        if not held:raise Error('smoke lacks a complete source-grounded poll/detect/bridge/drop interval')
        if not any(e['event']=='switch' and e.get('prev_state')=='S' for e in events):raise Error('smoke lacks harmless sleep scheduling')
        log.write_json(directory/'smoke.json',{'holder_schema':SCHEMA,'status':'QUALIFIED','created_at':base.now(),
            'kernel':log.command('uname','-r'),'machine':log.command('uname','-m'),'system':os.path.realpath('/run/current-system'),
            'tool_sha256':log.digest(Path(__file__)),'base_tool_sha256':log.digest(Path(base.__file__)),
            'event_count':len(events),'function_count':meta['function_count'],'held_intervals':held,'rejected_intervals':rejected})
    finally:base.safe_close(session)


def capture_run(directory, args, ipc, traced):
    directory.mkdir(mode=448)
    session = Session(directory, ipc.pid) if traced else None
    selected = log.control(ipc)
    log.idle_startup(ipc)
    subprocess.run(['sudo', '-u', 'shell', 'env', 'XDG_RUNTIME_DIR=/run/shell', '/run/current-system/sw/bin/k230-shell-rust', '--surface', 'hide'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    ipc.command('[app_id="k230-terminal"] focus')
    time.sleep(5)
    try:
        if session:
            session.prepare()
            session.start()
        code = cap.capture(argparse.Namespace(profile='landscape-1280x800', variant='candidate', input='injected', operator_confirmed_contacts=False, seconds=180, drags=24, source_revision=args.source_revision, output=directory / 'capture'))
        if session:
            session.finish()
        base.immutable(selected, log.control(ipc))
        log.write_json(directory / 'control.json', {'control': selected, 'traced': traced, 'capture_exit_code': code, 'tool_sha256': log.digest(Path(__file__)), 'fd_labels': base.fd_labels(ipc.pid)})
        if code:
            raise base.TraceError('capture incomplete; retain rejected attempt')
        row, context, samples = base.benchmark(directory / 'capture')
        return sum((s['wall_ms'] > 100 for s in samples))
    finally:
        if session:
            base.safe_close(session)

def board_run(args):
    smoke = json.loads((args.smoke / 'smoke.json').read_text())
    if smoke.get('status') != 'QUALIFIED' or smoke.get('kernel') != log.command('uname', '-r') or smoke.get('machine') != 'riscv64' or (smoke.get('system') != args.expected_system) or (smoke.get('tool_sha256') != log.digest(Path(__file__))) or (smoke.get('holder_schema') != SCHEMA or smoke.get('base_tool_sha256') != log.digest(Path(base.__file__))):
        raise base.TraceError('controller/clock/poll smoke does not match this trial')
    checked_events(args.smoke)
    smoke_cleanup = json.loads((args.smoke / 'trace-cleanup.json').read_text())
    if not smoke_cleanup.get('instance_removed') or smoke_cleanup.get('cleanup_timer_active') is not False:
        raise base.TraceError('smoke cleanup is incomplete')
    directory = base.new_directory(args.output)
    ipc = cap.IPC()
    original = log.control(ipc)
    log.idle_startup(ipc)
    globals_before = base.global_state()
    if original['system'] != args.expected_system or original['persistent_system'] != args.expected_system or original['executable_sha256'] != args.expected_executable_sha256 or (not original['debug_flag']):
        ipc.close()
        raise base.TraceError('installed runtime differs from explicit baseline')
    log.write_json(directory / 'original.json', original)
    log.write_json(directory / 'qualified-smoke.json', smoke)
    runs = []
    try:
        for name, traced in [('untraced', False), ('traced', True), ('traced-retry', True)]:
            if name == 'traced-retry' and tails:
                break
            print(json.dumps({'phase': 'starting', 'run': name}), flush=True)
            base.immutable(original, log.control(ipc))
            if base.global_state() != globals_before:
                raise base.TraceError('global tracer changed before workload')
            tails = capture_run(directory / name, args, ipc, traced)
            runs.append(name)
            print(json.dumps({'phase': 'captured', 'run': name, 'over_100ms': tails}), flush=True)
    finally:
        try:
            ipc.command('card_shell benchmark-stop')
            ipc.command('card_shell home')
            final = log.control(ipc)
            base.immutable(original, final)
            if base.global_state() != globals_before:
                raise base.TraceError('global controls changed during trial')
            log.write_json(directory / 'cleanup.json', {'checked_at': base.now(), 'control': final, 'global_before': globals_before, 'global_after': base.global_state(), 'home_command_succeeded': True, 'benchmark_stop_succeeded': True, 'idle_terminal': log.idle_startup(ipc), 'services': log.command('systemctl', 'is-active', 'shell.service', 'shell-ui.service').splitlines(), 'virtual_test_devices': sum(('injected' in r.get('name', '').lower() or 'fixture' in r.get('name', '').lower() for r in ipc.request(100)))})
        finally:
            ipc.close()
    log.write_json(directory / 'trial.json', {'schema': base.SCHEMA, 'holder_schema': SCHEMA, 'status': 'CAPTURED', 'runs': runs, 'source_revision': args.source_revision, 'tool_sha256': log.digest(Path(__file__))})


def overlap(held,sample):
    return [dict(h,overlap_ms=(min(h['drop_ns'],sample['end_ns'])-max(h['detect_ns'],sample['start_ns']))/1e6)
            for h in held if h['detect_ns']<sample['end_ns'] and h['drop_ns']>sample['start_ns']]


def report(directory):
    trial=json.loads((directory/'trial.json').read_text())
    if trial.get('holder_schema') != SCHEMA:raise Error('trial holder schema differs')
    # The base report qualifies runtime, 864 joins, syscall/scheduler ordering,
    # paired workload identities and restoration before attaching holder data.
    result=base.report(directory);result['schema']=SCHEMA
    smoke=json.loads((directory/'qualified-smoke.json').read_text())
    if smoke.get('tool_sha256')!=trial.get('tool_sha256') or smoke.get('holder_schema')!=SCHEMA:
        raise Error('capture and qualified smoke tool identities differ')
    result['report_tool_sha256']=log.digest(Path(__file__))
    for run in result['runs']:
        if run['control'].get('tool_sha256')!=trial.get('tool_sha256'):
            raise Error('paired capture tool identities differ')
        if run['name']=='untraced':continue
        events,functions,meta=checked_events(directory/run['name'])
        if meta.get('tool_sha256')!=trial.get('tool_sha256') or meta.get('base_tool_sha256')!=smoke.get('base_tool_sha256'):
            raise Error('trace exporter identity differs from qualified capture source')
        held,rejected=intervals(functions)
        if not held:raise Error('instrumented workload has no qualified poll critical sections')
        c=run['correlation'];c.update(poll_held_intervals=held,rejected_poll_intervals=rejected,
            held_interval_definition='detect_connector_status entry to drm_modeset_drop_locks entry in the same complete output_poll_execute/probe/LT9611 worker path; conservative connection_mutex-held interval grounded in pinned kernel source')
        _,_,samples=base.benchmark(directory/run['name']/'capture')
        calls,switches,_=base.intervals(events,meta['pid'],min(s['start_ns'] for s in samples),max(s['end_ns'] for s in samples))
        drm_fds={int(fd) for fd,label in run['control']['fd_labels'].items() if label=='DRM-card'}
        if not drm_fds:raise Error('capture lacks observed DRM descriptor labels')
        c['long_drm_calls']=[dict(call,poll_lock_overlap=overlap(held,call),
            off_cpu=[dict(off,poll_lock_overlap=overlap(held,off)) for off in switches
                     if off['start_ns']<call['end_ns'] and off['end_ns']>call['start_ns']])
            for call in calls if call['nr']==29 and call.get('fd') in drm_fds and call['wall_ms']>100]
        c['long_drm_calls_scope']='All complete >100ms DRM-fd ioctls in the trace, including input-idle periods; no arbitrary ioctl payload exported.'
        for sample in c['late_samples']:
            sample['poll_lock_overlap']=overlap(held,sample)
            for call in sample['syscalls']:call['poll_lock_overlap']=overlap(held,call)
            for off in sample['off_cpu']:off['poll_lock_overlap']=overlap(held,off)
    result['limits'] += ['Selected function entries identify a source-grounded conservative held-lock interval, not exact acquisition/release timestamps or mutex addresses.',
        'Poll detection time includes all work inside the interval; the internal I2C or bridge operation consuming that time remains unmeasured.',
        'Prior kernel sleep stacks locate these DRM call paths in modeset mutex acquisition; this run measures scheduler/syscalls and the polling critical section, without new kernel sleep stacks.']
    return result


class Fixtures(unittest.TestCase):
    def path(self,pid=99):
        return [dict(pid=pid,cpu=0,ts_ns=t,symbol=s,parent={'drm_helper_probe_detect':'output_poll_execute','drm_helper_probe_detect_ctx':'drm_helper_probe_detect','detect_connector_status':'drm_helper_probe_detect_ctx','drm_modeset_drop_locks':'drm_helper_probe_detect_ctx'}.get(s,'[other]')) for t,s in zip(
            (100,105,110,120,130,300),('output_poll_execute','drm_helper_probe_detect','drm_helper_probe_detect_ctx',
             'detect_connector_status','lt9611_bridge_detect','drm_modeset_drop_locks'))]

    def test_critical_section_and_pid(self):
        rows=self.path();rows.insert(2,dict(pid=50,cpu=0,ts_ns=107,symbol='drm_modeset_drop_locks',parent='[other]'))
        held,rejected=intervals(rows)
        self.assertEqual(len(held),1);self.assertEqual(rejected,[])
        self.assertEqual((held[0]['pid'],held[0]['detect_ns'],held[0]['drop_ns']),(99,120,300))

    def test_inlined_helper_and_two_connectors(self):
        rows=[dict(r,parent='output_poll_execute') if r['symbol']=='drm_helper_probe_detect_ctx' else r
              for r in self.path() if r['symbol']!='drm_helper_probe_detect']
        second=[dict(r,ts_ns=r['ts_ns']+300) for r in rows[1:]]
        held,rejected=intervals(rows+second)
        self.assertEqual(len(held),2);self.assertEqual(rejected,[])
        self.assertEqual([r['poll_ns'] for r in held],[100,100])

    def test_incomplete_ambiguous_backoff(self):
        bad=[self.path()[:-1],self.path()[:2]+self.path()[1:],
            self.path()[:3]+[dict(pid=99,cpu=0,ts_ns=115,symbol='drm_modeset_backoff',parent='drm_helper_probe_detect_ctx')]+self.path()[3:],
            [r for r in self.path() if r['symbol']!='lt9611_bridge_detect'],
            [dict(r,parent='[other]') for r in self.path()]]
        for rows in bad:
            with self.subTest(rows=rows):
                held,rejected=intervals(rows);self.assertFalse(held);self.assertTrue(rejected)

    def test_overlap_boundaries(self):
        held,_=intervals(self.path())
        self.assertEqual(overlap(held,dict(start_ns=150,end_ns=200))[0]['overlap_ms'],.00005)
        self.assertEqual(overlap(held,dict(start_ns=300,end_ns=400)),[])

    def test_export_rejects_payload_and_redacts(self):
        raw=('private-99 [000] .... 1.000000: function: output_poll_execute <-process_one_work\n'
             'private-10 [000] .... 1.100000: sys_enter: NR 29 (a, c03864bc, deadbeef, 0, 0, 0)\n'
             'private-10 [000] .... 1.200000: sys_exit: NR 29 = 0\n')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'raw';p.write_text(raw)
            self.assertEqual(export(p,d,10),(2,1))
            public=(d/'events.jsonl').read_text()+(d/'functions.jsonl').read_text()
            self.assertNotIn('private',public);self.assertNotIn('deadbeef',public);self.assertNotIn('process_one_work',public)
            for unsafe in ['secret_text','output_poll_execute args=secret','0xffffffffdeadbeef']:
                p.write_text('private-99 [000] .... 1.000000: '+unsafe+'\n')
                with self.assertRaises(Error):export(p,d,10)

    def fixture(self,d):
        raw=('task-10 [000] .... 1.000000: tracing_mark_write: K230_STALL start before_ns=999999900\n'
             'task-99 [000] .... 1.050000: function: output_poll_execute <-process_one_work\n'
             'task-10 [000] .... 1.100000: sys_enter: NR 29 (a, c03864bc, deadbeef, 0, 0, 0)\n'
             'task-10 [000] .... 1.200000: sys_exit: NR 29 = 0\n'
             'task-10 [000] .... 2.000000: tracing_mark_write: K230_STALL end before_ns=1999999900\n')
        (d/'raw').write_text(raw);export(d/'raw',d,10)
        meta={'schema':base.SCHEMA,'holder_schema':SCHEMA,'pid':10,'trace_clock':'[mono]',
            'event_count':4,'function_count':1,'function_filter':sorted(FUNCTIONS),'current_tracer':'function',
            'events_sha256':log.digest(d/'events.jsonl'),'functions_sha256':log.digest(d/'functions.jsonl'),
            'stats':{'cpu0':{'entries':5,'overrun':0,'commit overrun':0,'dropped events':0}},
            'markers':{'start':{'before_ns':999999900,'after_ns':1000000100},
                       'end':{'before_ns':1999999900,'after_ns':2000000100}}}
        log.write_json(d/'trace.json',meta);return meta

    def test_strict_hash_schema_loss_clock_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);meta=self.fixture(d);self.assertEqual(len(checked_events(d)[1]),1)
            changes=[('function_count',2),('function_filter',[]),('current_tracer','nop'),
                     ('functions_sha256','0'*64),('holder_schema','other'),
                     ('stats',{'cpu0':{'entries':5,'overrun':1,'commit overrun':0,'dropped events':0}}),
                     ('stats',{'cpu0':{'entries':6,'overrun':0,'commit overrun':0,'dropped events':0}}),
                     ('trace_clock','[local]')]
            for key,value in changes:
                log.write_json(d/'trace.json',dict(meta,**{key:value}))
                with self.subTest(key=key),self.assertRaises(Error):checked_events(d)
            log.write_json(d/'trace.json',meta)
            row=json.loads((d/'functions.jsonl').read_text());row['pointer']='secret'
            (d/'functions.jsonl').write_text(json.dumps(row)+'\n');meta['functions_sha256']=log.digest(d/'functions.jsonl')
            log.write_json(d/'trace.json',meta)
            with self.assertRaises(Error):checked_events(d)

    def test_gzip_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d)
            data=(d/'functions.jsonl').read_bytes();(d/'functions.jsonl.gz').write_bytes(gzip.compress(data,mtime=0))
            with self.assertRaises(Error):checked_events(d)
            (d/'functions.jsonl').unlink();self.assertEqual(len(checked_events(d)[1]),1)

    def test_cleanup_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'set_ftrace_filter').write_text('\n'.join(sorted(FUNCTIONS)))
            (d/'current_tracer').write_text('function\n');state={'function_filter':sorted(FUNCTIONS),'function_tracer':'function'}
            function_ownership(d,state)
            (d/'set_ftrace_filter').write_text('somebody_else\n')
            with self.assertRaises(Error):function_ownership(d,state)


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--self-test',action='store_true');g.add_argument('--board-smoke',action='store_true')
    g.add_argument('--board-run',action='store_true');g.add_argument('--report',type=Path);g.add_argument('--cleanup',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--smoke',type=Path);p.add_argument('--source-revision')
    p.add_argument('--expected-system');p.add_argument('--expected-executable-sha256');args=p.parse_args()
    try:
        if args.self_test:
            r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures));return 0 if r.wasSuccessful() else 1
        if args.cleanup:cleanup(args.cleanup)
        elif args.report:
            if args.output is None:p.error('--report needs --output')
            log.write_json(args.output,report(args.report))
        elif args.board_smoke:
            if args.output is None:p.error('--board-smoke needs new --output')
            board_smoke(args)
        else:
            if (args.output is None or args.smoke is None or not re.fullmatch('[0-9a-f]{40}',args.source_revision or '') or
                not re.fullmatch('[0-9a-f]{64}',args.expected_executable_sha256 or '') or
                not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+',args.expected_system or '')):
                p.error('trial needs qualified smoke, source/system/executable and new output')
            board_run(args)
    except (Error,log.TrialError,cap.CaptureError,base.baseline.perf.InvalidTrace,OSError,EOFError,
            KeyError,ValueError,subprocess.SubprocessError) as error:
        print('drm-holder: '+str(error),file=sys.stderr);return 2
    return 0


if __name__=='__main__':sys.exit(main())
