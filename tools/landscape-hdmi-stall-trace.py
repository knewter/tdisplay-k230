#!/usr/bin/env python3
"""Correlate bounded, isolated numeric kernel events with HDMI frame stalls."""
import argparse
import errno
import fcntl
import gzip
import hashlib
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
import uuid

import importlib.util
_spec = importlib.util.spec_from_file_location('stall_logging', Path(__file__).with_name('landscape-hdmi-logging.py'))
log = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(log)
cap, baseline = log.capture, log.baseline
SCHEMA = 'landscape-hdmi-stall-trace-v1'
ROOT = Path('/sys/kernel/tracing')
GLOBAL = ('current_tracer', 'tracing_on', 'trace_clock', 'events/enable', 'set_event_pid', 'set_ftrace_pid')
EVENTS = ('raw_syscalls/sys_enter', 'raw_syscalls/sys_exit', 'sched/sched_switch', 'sched/sched_wakeup')
MAX_RAW = 64 * 1024 * 1024
MAX_EVENTS = 1_000_000
LINE = re.compile(r'^\s*.*?-(\d+)\s+(?:\(\s*\d+\)\s+)?\[(\d+)\].*?\s(\d+\.\d+):\s+(\w+):\s*(.*)$')


class TraceError(RuntimeError):
    pass


def now():
    return log.datetime.now(log.timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_suffix('.new')
    log.write_json(temporary, value); temporary.replace(path)


def global_state(root=ROOT):
    return {name: log.digest(root/name) for name in GLOBAL}


def timestamp(value):
    sec, fraction = value.split('.')
    if not fraction.isdecimal() or len(fraction) > 9:
        raise TraceError('invalid trace timestamp precision')
    return int(sec) * 1_000_000_000 + int(fraction.ljust(9, '0'))


def parse_line(line, target):
    if not line.strip() or line.lstrip().startswith('#'):
        return None
    match = LINE.fullmatch(line.rstrip('\n'))
    if not match:
        raise TraceError('unrecognized or lost trace record; raw text is not exported')
    pid, cpu, stamp, kind, body = match.groups()
    row = {'pid': int(pid), 'cpu': int(cpu), 'ts_ns': timestamp(stamp)}
    if kind == 'sys_enter':
        m = re.fullmatch(r'NR (\d+) \(([^()]*)\)', body)
        if not m or row['pid'] != target:
            raise TraceError('unexpected syscall entry or PID')
        args = [a.strip() for a in m[2].split(',')]
        if len(args) != 6 or any(not re.fullmatch('[0-9a-fA-F]+', a) for a in args):
            raise TraceError('syscall register fields are not numeric')
        row.update(event='enter', nr=int(m[1]))
        # Target ABI is independently proved by the harmless controller smoke.
        # Never export pointer/register values for unrelated syscall arguments.
        if row['nr'] in (29, 64, 66):
            row['fd'] = int(args[0], 16)
            if row['nr'] == 29: row['command'] = int(args[1], 16)
            elif row['nr'] == 64: row['count'] = int(args[2], 16)
            else: row['iov_count'] = int(args[2], 16)
    elif kind == 'sys_exit':
        m = re.fullmatch(r'NR (\d+) = (-?\d+)', body)
        if not m or row['pid'] != target:
            raise TraceError('unexpected syscall exit or PID')
        nr, result = int(m[1]), int(m[2])
        row.update(event='exit', nr=nr)
        if nr in (29,64,66):
            row['ret']=result
        else:
            # mmap/brk and other calls may return pointers. Preserve only the
            # errno category for unrelated calls, never an arbitrary address.
            row['result_error']=-result if -4095<=result<0 else 0
    elif kind == 'sched_switch':
        m = re.search(r'\bprev_pid=(\d+) prev_prio=\d+ prev_state=([RSDTtXZPI+|]+) ==> .*?\bnext_pid=(\d+) next_prio=\d+$', body)
        if not m or target not in (int(m[1]), int(m[3])):
            raise TraceError('unexpected scheduler switch or target')
        row.update(event='switch', prev_pid=int(m[1]), prev_state=m[2], next_pid=int(m[3]))
    elif kind == 'sched_wakeup':
        m = re.search(r'\bpid=(\d+) prio=\d+ target_cpu=(\d+)$', body)
        if not m or int(m[1]) != target:
            raise TraceError('unexpected wakeup target')
        row.update(event='wake', wake_pid=int(m[1]), target_cpu=int(m[2]))
    elif kind == 'tracing_mark_write':
        m = re.fullmatch(r'K230_STALL (start|end) before_ns=(\d+)', body)
        if not m: raise TraceError('unrecognized trace marker; no arbitrary payload export')
        row.update(event='marker', phase=m[1], before_ns=int(m[2]))
    else:
        raise TraceError('unexpected event; do not export arbitrary payloads')
    return row


def export(raw_path, safe_path, target):
    count = 0; previous = -1
    with raw_path.open() as src, safe_path.open('w') as out:
        for line in src:
            row = parse_line(line, target)
            if row is None: continue
            if row['cpu'] != 0 or row['ts_ns'] < previous:
                raise TraceError('CPU or timestamp order changed')
            previous = row['ts_ns']; count += 1
            if count > MAX_EVENTS: raise TraceError('too many trace events')
            out.write(json.dumps(row, separators=(',', ':'))+'\n')
    return count


def public_reexport(private_directory, public_directory):
    """Re-export original bytes without changing clocks, events or loss proof."""
    metadata=json.loads((private_directory/'trace.json').read_text())
    raw=private_directory/'raw.trace'
    if log.digest(raw)!=metadata['raw_sha256']:
        raise TraceError('private raw trace identity differs')
    public_directory.mkdir(parents=True,exist_ok=True)
    count=export(raw,public_directory/'events.jsonl',metadata['pid'])
    if count!=metadata['event_count']:
        raise TraceError('re-export changed event count')
    metadata.update(original_numeric_sha256=metadata['events_sha256'],
        events_sha256=log.digest(public_directory/'events.jsonl'),
        public_export_tool_sha256=log.digest(Path(__file__)),
        public_export_note='Unknown syscall returns retain only errno category; pointer-valued returns are omitted. Capture timestamps, event count and loss statistics are unchanged.')
    log.write_json(public_directory/'trace.json',metadata)
    checked_events(public_directory)


def owned_path(state, root=ROOT):
    name = state.get('instance')
    if not isinstance(name, str) or not re.fullmatch(r'k230-stall-[0-9a-f]{16}', name):
        raise TraceError('unsafe trace instance identity')
    path = root/'instances'/name
    if path.is_symlink(): raise TraceError('trace instance is a symlink')
    if path.exists() and state.get('inode') != path.stat().st_ino:
        raise TraceError('trace instance ownership changed')
    return path


def stop_owned(state, root=ROOT):
    path = owned_path(state, root)
    if path.exists():
        for event, expected in state.get('filters', {}).items():
            if event not in EVENTS or (path/'events'/event/'filter').read_text().strip() != expected:
                raise TraceError('owned trace filter changed; preserve the instance')
        (path/'tracing_on').write_text('0')
        for event in EVENTS: (path/'events'/event/'enable').write_text('0')
        path.rmdir()  # tracefs removes its virtual control files, no recursive deletion
    if global_state(root) != state['global_before']:
        raise TraceError('global tracing state changed; do not overwrite it')


def cleanup(state_path):
    state = json.loads(state_path.read_text())
    with state_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop_owned(state)
        result = {'checked_at': now(), 'instance_removed': True,
                  'global_controls_unchanged': True, 'global_after': global_state()}
        log.write_json(state_path.parent/'trace-cleanup.json', result)
        return result


class Session:
    def __init__(self, directory, target):
        self.directory, self.target = directory, target
        self.state_path = directory/'trace-state.json'
        name = 'k230-stall-' + uuid.uuid4().hex[:16]
        self.state = {'schema': SCHEMA, 'instance': name, 'target_pid': target,
                      'inode': None, 'filters': {}, 'global_before': global_state(),
                      'cleanup_unit': name + '-cleanup'}
        self.path = ROOT/'instances'/name

    def prepare(self):
        if Path('/sys/devices/system/cpu/online').read_text().strip() != '0':
            raise TraceError('this bounded trace requires only CPU0 online')
        available = int(re.search(r'^MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text(), re.M)[1])
        if available < 128 * 1024: raise TraceError('insufficient free memory for bounded trace')
        atomic_json(self.state_path, self.state)
        unit = self.state['cleanup_unit']
        log.command('systemd-run', '--quiet', '--unit='+unit, '--on-active=600s',
                    sys.executable, str(Path(__file__).resolve()), '--cleanup', str(self.state_path))
        if log.command('systemctl','is-active',unit+'.timer') != 'active':
            raise TraceError('independent trace cleanup did not arm')
        self.path.mkdir()  # exclusive; never borrow an existing instance
        self.state['inode'] = self.path.stat().st_ino; atomic_json(self.state_path, self.state)
        (self.path/'tracing_on').write_text('0')
        (self.path/'events/enable').write_text('0')
        (self.path/'trace_clock').write_text('mono')
        (self.path/'per_cpu/cpu0/buffer_size_kb').write_text('32768')
        total = int((self.path/'buffer_total_size_kb').read_text().split()[0])
        if total > 65536: raise TraceError('trace buffer exceeded64MiB cap')
        for event in EVENTS:
            expr = (f'prev_pid == {self.target} || next_pid == {self.target}' if event.endswith('sched_switch') else
                    f'pid == {self.target}' if event.endswith('sched_wakeup') else f'common_pid == {self.target}')
            control = self.path/'events'/event
            (control/'filter').write_text(expr)
            self.state['filters'][event] = (control/'filter').read_text().strip()
            atomic_json(self.state_path, self.state)
            (control/'enable').write_text('1')
        if global_state() != self.state['global_before']:
            raise TraceError('isolated trace setup changed global controls')
        self.metadata = {'schema': SCHEMA, 'pid': self.target, 'buffer_total_kb': total,
                         'global_before': self.state['global_before'], 'markers': {}}

    def marker(self, phase):
        before = time.monotonic_ns()
        (self.path/'trace_marker').write_text(f'K230_STALL {phase} before_ns={before}\n')
        self.metadata['markers'][phase] = {'before_ns': before, 'after_ns': time.monotonic_ns()}

    def start(self):
        (self.path/'tracing_on').write_text('1'); self.marker('start')

    def finish(self):
        self.marker('end'); (self.path/'tracing_on').write_text('0')
        stats = {}
        for f in sorted((self.path/'per_cpu').glob('cpu*/stats')):
            fields = {}
            for line in f.read_text().splitlines():
                if ':' in line:
                    key, value = line.split(':',1)
                    if value.strip().isdecimal(): fields[key.strip()] = int(value)
            stats[f.parent.name] = fields
        self.metadata.update(stats=stats, trace_clock=(self.path/'trace_clock').read_text().strip())
        raw = self.directory/'raw.trace'
        with (self.path/'trace').open('rb') as src:
            data = src.read(MAX_RAW+1)
        if len(data) > MAX_RAW: raise TraceError('raw trace exceeds bounded export')
        raw.write_bytes(data); raw.chmod(0o600)
        count = export(raw, self.directory/'events.jsonl', self.target)
        self.metadata.update(raw_sha256=log.digest(raw), raw_bytes=len(data), event_count=count,
                             events_sha256=log.digest(self.directory/'events.jsonl'), tool_sha256=log.digest(Path(__file__)))
        log.write_json(self.directory/'trace.json', self.metadata)

    def close(self):
        cleanup(self.state_path)
        log.command('systemctl','stop',self.state['cleanup_unit']+'.timer')
        row = json.loads((self.directory/'trace-cleanup.json').read_text())
        row['cleanup_timer_active'] = subprocess.run(['systemctl','is-active','--quiet',self.state['cleanup_unit']+'.timer']).returncode == 0
        log.write_json(self.directory/'trace-cleanup.json', row)


def checked_events(directory):
    meta = json.loads((directory/'trace.json').read_text())
    if meta.get('schema') != SCHEMA or '[mono]' not in meta.get('trace_clock',''):
        raise TraceError('trace clock/schema is not qualified')
    payload = event_bytes(directory)
    if hashlib.sha256(payload).hexdigest() != meta.get('events_sha256'):
        raise TraceError('numeric trace identity differs')
    for fields in meta['stats'].values():
        for key in ('overrun', 'commit overrun', 'dropped events'):
            if fields.get(key) != 0: raise TraceError('trace loss or missing loss statistics')
    if not meta['stats']: raise TraceError('missing CPU trace statistics')
    events = load_safe_events(directory, payload)
    if len(events) != meta['event_count'] or len(events) > MAX_EVENTS:
        raise TraceError('trace record count differs')
    previous = -1
    for row in events:
        if row['cpu'] != 0 or row['ts_ns'] < previous: raise TraceError('trace ordering changed')
        if row['event'] in ('enter','exit') and row['pid']!=meta['pid']:
            raise TraceError('mixed syscall target PID')
        if row['event']=='switch' and meta['pid'] not in (row['prev_pid'],row['next_pid']):
            raise TraceError('mixed scheduler target PID')
        if row['event']=='wake' and row['wake_pid']!=meta['pid']:
            raise TraceError('mixed wakeup target PID')
        previous = row['ts_ns']
    for phase in ('start','end'):
        markers = [r for r in events if r['event']=='marker' and r['phase']==phase]
        bound = meta['markers'][phase]
        if (len(markers)!=1 or markers[0]['before_ns']!=bound['before_ns'] or
                not bound['before_ns']-1000 <= markers[0]['ts_ns'] <= bound['after_ns']+1000):
            raise TraceError('monotonic trace marker is missing or outside its bracket')
    return events, meta


def intervals(events, target, first, last):
    calls, switches, partial = [], [], []
    pending = off = None
    for row in events:
        t = row['ts_ns']; kind=row['event']
        if kind=='enter':
            if pending is not None: raise TraceError('unclosed syscall before another entry')
            pending=row
        elif kind=='exit':
            if pending is None:
                if t>=first: raise TraceError('unmatched syscall exit inside qualified window')
                partial.append({'event':'initial_syscall_exit','ts_ns':t}); continue
            if row['nr']!=pending['nr']: raise TraceError('syscall entry/exit mismatch')
            calls.append({**pending,'start_ns':pending['ts_ns'],'end_ns':t,'ret':row.get('ret'),
                          'result_error':row.get('result_error'),
                          'wall_ms':(t-pending['ts_ns'])/1e6});pending=None
        elif kind=='switch':
            if row['prev_pid']==target:
                if off is not None: raise TraceError('duplicate switch-out')
                off={'start_ns':t,'state':row['prev_state'],'wakeup_ns':None,'descheduled_to_pid':row['next_pid']}
            if row['next_pid']==target:
                if off is None:
                    if t>=first: raise TraceError('unmatched switch-in inside qualified window')
                    partial.append({'event':'initial_switch_in','ts_ns':t});continue
                wait=(t-off['start_ns']) if off['state'].startswith('R') else (t-off['wakeup_ns'] if off['wakeup_ns'] is not None else None)
                switches.append({**off,'end_ns':t,'wall_ms':(t-off['start_ns'])/1e6,
                                 'runnable_wait_ms':None if wait is None else wait/1e6});off=None
        elif kind=='wake' and off is not None and off['wakeup_ns'] is None:
            off['wakeup_ns']=t
    for label, item in (('final_syscall_enter',pending),('final_switch_out',off)):
        if item is not None:
            t=item.get('start_ns',item.get('ts_ns'))
            if t<=last: raise TraceError('partial event overlaps qualified presentation window')
            partial.append({'event':label,'ts_ns':t})
    return calls, switches, partial


def benchmark(directory):
    row, context = baseline.load(directory,1)
    if row['drag_count']!=24 or row['input_to_present_ms']['sample_count']!=864:
        raise TraceError('requires exactly24 complete35-move drags')
    item=json.loads((directory/'metadata.json').read_text())['runs'][0]
    records,_,costs=baseline.perf.parse_log((directory/item['log']).read_bytes(),item['run'])
    submits={r['input_id']:r for r in records if r['event']=='submit'}
    presents={r['frame_id']:r for r in records if r['event']=='present'};samples=[]
    for r in records:
        if r['event']!='input':continue
        sub=submits[r['input_id']];pres=presents[sub['frame_id']]
        samples.append({'input_id':r['input_id'],'frame_id':sub['frame_id'],'start_ns':r['t_ns'],
            'submit_ns':sub['t_ns'],'end_ns':pres['t_ns'],'wall_ms':(pres['t_ns']-r['t_ns'])/1e6,
            'build_cpu_ms':costs[sub['frame_id']]/1e6})
    return row,context,samples


def correlate(directory, samples):
    events,meta=checked_events(directory)
    first=min(s['start_ns'] for s in samples);last=max(s['end_ns'] for s in samples)
    if not meta['markers']['start']['after_ns']<=first<=last<=meta['markers']['end']['before_ns']:
        raise TraceError('trace does not bracket the complete benchmark')
    calls,switches,partial=intervals(events,meta['pid'],first,last)
    late=[]
    def overlapping(items,s):
        return [r for r in items if r['start_ns']<s['end_ns'] and r['end_ns']>s['start_ns']]
    for s in samples:
        if s['wall_ms']<=100:continue
        syscalls=sorted(overlapping(calls,s),key=lambda r:r['wall_ms'],reverse=True)
        off=sorted(overlapping(switches,s),key=lambda r:r['wall_ms'],reverse=True)
        late.append({**s,'syscalls':syscalls[:12],'off_cpu':off[:12]})
    return {'late_samples':late,'complete_syscall_spans':len(calls),'complete_switch_spans':len(switches),
            'boundary_partial_events':partial,'trace':meta,
            'limits':['Syscall wall time includes scheduling delays; it is not kernel CPU time.',
                      'Only the compositor main thread is traced; no finger or optical claim.']}


def new_directory(path):
    path=path.resolve()
    if path.exists() or path==ROOT or ROOT in path.parents:
        raise TraceError('output must be a new private directory outside tracefs')
    path.mkdir(parents=True,mode=0o700)
    return path


def safe_close(session):
    if session.state_path.exists(): session.close()


def board_smoke(args):
    directory=new_directory(args.output)
    session=Session(directory,os.getpid())
    fd=os.open('/dev/null',os.O_WRONLY)
    try:
        session.prepare();session.start()
        written=os.write(fd,b'K230-ABI')
        vectored=os.writev(fd,[b'K230',b'-ABI'])
        try: fcntl.ioctl(fd,0);ioctl_return=0
        except OSError as error: ioctl_return=-error.errno
        session.finish()
        events,meta=checked_events(directory)
        def proof(nr,field,value):
            matches=[r for r in events if r['event']=='enter' and r['nr']==nr and r.get('fd')==fd and r.get(field)==value]
            if len(matches)!=1: raise TraceError('harmless target-ABI operation was not uniquely traced')
            start=events.index(matches[0]);end=next((r for r in events[start+1:] if r['event']=='exit'),None)
            if end is None or end['nr']!=nr: raise TraceError('ABI operation lacks its exit')
            return end['ret']
        if proof(64,'count',8)!=written or proof(66,'iov_count',2)!=vectored or proof(29,'command',0)!=ioctl_return:
            raise TraceError('target syscall ABI differs from the selected numeric mapping')
        log.write_json(directory/'smoke.json',{'schema':SCHEMA,'status':'QUALIFIED','checked_at':now(),
            'kernel':log.command('uname','-r'),'machine':log.command('uname','-m'),
            'system':str(Path('/run/current-system').resolve()),'tool_sha256':log.digest(Path(__file__)),
            'abi':{'write':64,'writev':66,'ioctl':29},'probe_fd':fd,'write_return':written,
            'writev_return':vectored,'ioctl_return':ioctl_return,'event_count':meta['event_count']})
    finally:
        os.close(fd);safe_close(session)


def immutable(left,right):
    for key in ('pid','debug_flag','verbose_flag','arguments_without_logging','config_sha256',
                'executable_sha256','system','persistent_system','environment','output'):
        if key not in left or key not in right or left[key]!=right[key]:raise TraceError('live control changed or missing: '+key)


def capture_run(directory,args,ipc,traced):
    directory.mkdir(mode=0o700)
    session=Session(directory,ipc.pid) if traced else None
    selected=log.control(ipc);log.idle_startup(ipc)
    subprocess.run(['sudo','-u','shell','env','XDG_RUNTIME_DIR=/run/shell',
        '/run/current-system/sw/bin/k230-shell-rust','--surface','hide'],check=True,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    ipc.command('[app_id="k230-terminal"] focus')
    time.sleep(5)
    try:
        if session: session.prepare();session.start()
        code=cap.capture(argparse.Namespace(profile='landscape-1280x800',variant='candidate',input='injected',
            operator_confirmed_contacts=False,seconds=180,drags=24,source_revision=args.source_revision,
            output=directory/'capture'))
        if session: session.finish()
        immutable(selected,log.control(ipc))
        log.write_json(directory/'control.json',{'control':selected,'traced':traced,'capture_exit_code':code,
            'tool_sha256':log.digest(Path(__file__)),'fd_labels':fd_labels(ipc.pid)})
        if code: raise TraceError('capture incomplete; retain rejected attempt')
        row,context,samples=benchmark(directory/'capture')
        return sum(s['wall_ms']>100 for s in samples)
    finally:
        if session:safe_close(session)


def fd_labels(pid):
    result={}
    for p in Path('/proc',str(pid),'fd').iterdir():
        try: target=os.readlink(p)
        except OSError:continue
        if re.fullmatch(r'/dev/dri/card\d+',target):result[p.name]='DRM-card'
        elif p.name in ('1','2') and target.startswith('socket:'):result[p.name]='journal-stream'
    return result


def board_run(args):
    smoke=json.loads((args.smoke/'smoke.json').read_text())
    if (smoke.get('status')!='QUALIFIED' or smoke.get('kernel')!=log.command('uname','-r') or
            smoke.get('machine')!='riscv64' or smoke.get('system')!=args.expected_system or
            smoke.get('tool_sha256')!=log.digest(Path(__file__)) or
            smoke.get('abi')!={'write':64,'writev':66,'ioctl':29}):
        raise TraceError('controller/clock/ABI smoke does not match this trial')
    checked_events(args.smoke)
    smoke_cleanup=json.loads((args.smoke/'trace-cleanup.json').read_text())
    if not smoke_cleanup.get('instance_removed') or smoke_cleanup.get('cleanup_timer_active') is not False:
        raise TraceError('smoke cleanup is incomplete')
    directory=new_directory(args.output);ipc=cap.IPC()
    original=log.control(ipc);log.idle_startup(ipc);globals_before=global_state()
    if (original['system']!=args.expected_system or original['persistent_system']!=args.expected_system or
            original['executable_sha256']!=args.expected_executable_sha256 or not original['debug_flag']):
        ipc.close();raise TraceError('installed runtime differs from explicit baseline')
    log.write_json(directory/'original.json',original);log.write_json(directory/'qualified-smoke.json',smoke)
    runs=[]
    try:
        for name,traced in [('untraced',False),('traced',True),('traced-retry',True)]:
            if name=='traced-retry' and tails:break
            print(json.dumps({'phase':'starting','run':name}),flush=True)
            immutable(original,log.control(ipc))
            if global_state()!=globals_before:raise TraceError('global tracer changed before workload')
            tails=capture_run(directory/name,args,ipc,traced);runs.append(name)
            print(json.dumps({'phase':'captured','run':name,'over_100ms':tails}),flush=True)
    finally:
        try:
            ipc.command('card_shell benchmark-stop');ipc.command('card_shell home')
            final=log.control(ipc);immutable(original,final)
            if global_state()!=globals_before:raise TraceError('global controls changed during trial')
            log.write_json(directory/'cleanup.json',{'checked_at':now(),'control':final,
                'global_before':globals_before,'global_after':global_state(),'home_command_succeeded':True,
                'benchmark_stop_succeeded':True,'idle_terminal':log.idle_startup(ipc),
                'services':log.command('systemctl','is-active','shell.service','shell-ui.service').splitlines(),
                'virtual_test_devices':sum('injected' in r.get('name','').lower() or 'fixture' in r.get('name','').lower() for r in ipc.request(100))})
        finally:ipc.close()
    log.write_json(directory/'trial.json',{'schema':SCHEMA,'status':'CAPTURED','runs':runs,
        'source_revision':args.source_revision,'tool_sha256':log.digest(Path(__file__))})


def event_bytes(directory):
    plain, packed = directory/'events.jsonl', directory/'events.jsonl.gz'
    if plain.exists() == packed.exists():
        raise TraceError('exactly one plain or compressed numeric trace is required')
    opener = plain.open if plain.exists() else lambda mode: gzip.open(packed, mode)
    with opener('rb') as src:
        payload = src.read(MAX_RAW + 1)
    if len(payload) > MAX_RAW:
        raise TraceError('expanded numeric trace exceeds bounds')
    return payload


def load_safe_events(directory, payload=None):
    # Exporter provenance is checked separately; enforce the public schema too.
    rows=[]
    if payload is None: payload = event_bytes(directory)
    for line in payload.decode('utf-8').splitlines():
        if len(line)>1024 or len(rows)>=MAX_EVENTS:raise TraceError('numeric trace exceeds bounds')
        r=json.loads(line);base={'pid','cpu','ts_ns','event'}
        extras={'enter':{'nr'},'exit':{'nr'},'switch':{'prev_pid','prev_state','next_pid'},
                'wake':{'wake_pid','target_cpu'},'marker':{'phase','before_ns'}}
        if r.get('event') not in extras:raise TraceError('unknown numeric trace event')
        required=base|extras[r['event']]
        if r['event']=='enter' and r.get('nr') in (29,64,66):
            required|={'fd',({29:'command',64:'count',66:'iov_count'}[r['nr']])}
        if r['event']=='exit':required|={'ret' if r.get('nr') in (29,64,66) else 'result_error'}
        if set(r)!=required:raise TraceError('unexpected or private numeric event fields')
        for k,v in r.items():
            if k in ('event','phase','prev_state'):continue
            if type(v) is not int:raise TraceError('numeric event contains a noninteger field')
        if r['event']=='marker' and r['phase'] not in ('start','end'):
            raise TraceError('unknown marker phase')
        if r['event']=='switch' and not re.fullmatch('[RSDTtXZPI+|]+',str(r['prev_state'])):
            raise TraceError('unknown scheduler state')
        rows.append(r)
    return rows


def report(directory):
    trial=json.loads((directory/'trial.json').read_text())
    if trial.get('schema')!=SCHEMA or trial.get('status')!='CAPTURED' or trial.get('runs') not in (
            ['untraced','traced'],['untraced','traced','traced-retry']):
        raise TraceError('invalid paired trial manifest')
    original=json.loads((directory/'original.json').read_text());result=[];reference=None
    for name in trial['runs']:
        d=directory/name;control=json.loads((d/'control.json').read_text());immutable(original,control['control'])
        if control['capture_exit_code']!=0 or control['traced']!=(name!='untraced'):
            raise TraceError('workload control is incomplete')
        row,context,samples=benchmark(d/'capture')
        key={k:row[k] for k in ('source_revision','runtime_identity','physical_geometry','logical_geometry','format','input_class')}
        key.update({k:context[k] for k in ('collector_sha256','injected_workload','output')})
        if reference is None:reference=key
        elif key!=reference:raise TraceError('mixed benchmark identity or workload')
        entry={'name':name,'benchmark':row,'latency':log.distribution([s['wall_ms'] for s in samples]),
               'control':control}
        if name!='untraced':
            entry['correlation']=correlate(d,samples)
            cleaned=json.loads((d/'trace-cleanup.json').read_text())
            if (cleaned.get('instance_removed') is not True or cleaned.get('global_controls_unchanged') is not True or
                    cleaned.get('cleanup_timer_active') is not False):raise TraceError('trace instance cleanup incomplete')
        result.append(entry)
    cleaned=json.loads((directory/'cleanup.json').read_text());immutable(original,cleaned['control'])
    if (cleaned['global_before']!=cleaned['global_after'] or cleaned.get('home_command_succeeded') is not True or
            cleaned.get('benchmark_stop_succeeded') is not True or cleaned.get('services')!=['active','active'] or
            cleaned.get('virtual_test_devices')!=0):raise TraceError('normal-state restoration incomplete')
    return {'schema':SCHEMA,'created_at':now(),'status':'MEASURED','performance_acceptance':'NOT_EVALUATED',
            'runs':result,'limits':['Tracing overhead is included; compare the paired untraced workload.',
            'Elapsed syscalls and scheduling intervals need interpretation, not automatic causal labels.',
            'Main-thread direct-IPC diagnostic only; no native/finger/optical or portrait acceptance.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-test',action='store_true');mode.add_argument('--board-smoke',action='store_true')
    mode.add_argument('--board-run',action='store_true');mode.add_argument('--report',type=Path)
    mode.add_argument('--cleanup',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--smoke',type=Path)
    parser.add_argument('--source-revision');parser.add_argument('--expected-system');parser.add_argument('--expected-executable-sha256')
    args=parser.parse_args()
    try:
        if args.self_test:
            return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures)).wasSuccessful() else 1
        if args.cleanup:cleanup(args.cleanup)
        elif args.report:
            data=report(args.report)
            if args.output:log.write_json(args.output,data)
            else:print(json.dumps(data,indent=2))
        elif args.board_smoke:
            if args.output is None:parser.error('smoke needs a new private --output directory')
            board_smoke(args)
        else:
            if (args.output is None or args.smoke is None or not re.fullmatch('[0-9a-f]{40}',args.source_revision or '') or
                    not re.fullmatch('[0-9a-f]{64}',args.expected_executable_sha256 or '') or
                    not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+',args.expected_system or '')):
                parser.error('trial needs qualified smoke, explicit source/system/executable and new output')
            board_run(args)
    except (TraceError,log.TrialError,cap.CaptureError,baseline.perf.InvalidTrace,OSError,
            KeyError,ValueError,subprocess.SubprocessError) as error:
        print('stall-trace: '+str(error),file=sys.stderr);return 2
    return 0


class Fixtures(unittest.TestCase):
    def test_numeric_export_omits_buffers_and_names(self):
        row=parse_line('sway-10 [000] .... 1.100000: sys_enter: NR 64 (2, abcdef, 8, 0, 0, 0)',10)
        self.assertEqual(row,{'pid':10,'cpu':0,'ts_ns':1100000000,'event':'enter','nr':64,'fd':2,'count':8})
        for bad in ('sway-10 [000] .... 1.100000: sys_enter_write: fd:2 buf: password=private',
                    'sway-11 [000] .... 1.100000: sys_enter: NR 64 (2, 0, 8, 0, 0, 0)',
                    'CPU:0 [LOST 2 EVENTS]',
                    'sway-10 [000] .... 1.100000: tracing_mark_write: arbitrary private text'):
            with self.subTest(bad=bad),self.assertRaises(TraceError):parse_line(bad,10)
        switch=parse_line('private-task-name-99 [000] .... 1.320000: sched_switch: prev_comm=private prev_pid=99 prev_prio=120 prev_state=R ==> next_comm=sway next_pid=10 next_prio=120',10)
        self.assertNotIn('private',json.dumps(switch));self.assertEqual(switch['next_pid'],10)
        address=parse_line('sway-10 [000] .... 1.100000: sys_exit: NR 222 = 1400123456789',10)
        self.assertNotIn('1400123456789',json.dumps(address));self.assertEqual(address['result_error'],0)
        error=parse_line('sway-10 [000] .... 1.100000: sys_exit: NR 222 = -12',10)
        self.assertEqual(error['result_error'],12)

    def events(self):
        def e(t,kind,**kw):return {'ts_ns':int(t*1e9),'pid':10,'cpu':0,'event':kind,**kw}
        return [e(1,'marker',phase='start',before_ns=999999900),
            e(1.1,'enter',nr=29,fd=7,command=0),
            e(1.11,'switch',prev_pid=10,next_pid=99,prev_state='D'),
            e(1.3,'wake',wake_pid=10,target_cpu=0),
            e(1.32,'switch',prev_pid=99,next_pid=10,prev_state='R'),
            e(1.33,'exit',nr=29,ret=0),
            e(2,'marker',phase='end',before_ns=1999999900)]

    def fixture(self,directory,events=None):
        events=self.events() if events is None else events
        path=directory/'events.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in events))
        meta={'schema':SCHEMA,'pid':10,'trace_clock':'local [mono] mono_raw',
            'markers':{'start':{'before_ns':999999900,'after_ns':1000000100},
                       'end':{'before_ns':1999999900,'after_ns':2000000100}},
            'stats':{'cpu0':{'overrun':0,'commit overrun':0,'dropped events':0}},
            'event_count':len(events),'events_sha256':log.digest(path)}
        log.write_json(directory/'trace.json',meta);return meta

    def test_syscall_and_sleep_runnable_intervals(self):
        calls,switches,partial=intervals(self.events(),10,1090000000,1340000000)
        self.assertAlmostEqual(calls[0]['wall_ms'],230)
        self.assertAlmostEqual(switches[0]['wall_ms'],210)
        self.assertAlmostEqual(switches[0]['runnable_wait_ms'],20)
        self.assertEqual(switches[0]['descheduled_to_pid'],99);self.assertEqual(partial,[])
        rows=self.events();rows[2]['prev_state']='R+';rows.pop(3)
        _,switches,_=intervals(rows,10,1090000000,1340000000)
        self.assertAlmostEqual(switches[0]['runnable_wait_ms'],210)

    def test_partial_events_only_outside_qualified_window(self):
        rows=self.events();rows.pop(5)
        with self.assertRaises(TraceError):intervals(rows,10,1090000000,1340000000)
        rows=self.events();rows[5]['nr']=64
        with self.assertRaises(TraceError):intervals(rows,10,1090000000,1340000000)
        initial={'ts_ns':1050000000,'pid':10,'cpu':0,'event':'exit','nr':22,'ret':1}
        final={'ts_ns':1500000000,'pid':10,'cpu':0,'event':'enter','nr':22}
        rows=self.events();rows.insert(1,initial);rows.insert(-1,final)
        self.assertEqual(len(intervals(rows,10,1090000000,1340000000)[2]),2)

    def test_clock_loss_and_public_schema_guards(self):
        for mutation in ('none','loss','clock','marker','pid','private'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp);events=self.events()
                if mutation=='marker':events[0]['before_ns']=0
                elif mutation=='pid':events[1]['pid']=11
                elif mutation=='private':events[1]['buffer']='private contents'
                meta=self.fixture(d,events)
                if mutation=='loss':meta['stats']['cpu0']['overrun']=1
                elif mutation=='clock':meta['trace_clock']='[local] mono'
                log.write_json(d/'trace.json',meta)
                if mutation=='none':self.assertEqual(len(checked_events(d)[0]),7)
                else:
                    with self.assertRaises(TraceError):checked_events(d)

    def test_compressed_trace_preserves_identity_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);plain=d/'events.jsonl';payload=plain.read_bytes()
            packed=d/'events.jsonl.gz';packed.write_bytes(gzip.compress(payload,mtime=0))
            with self.assertRaises(TraceError):checked_events(d)
            plain.unlink()
            self.assertEqual(checked_events(d)[0],self.events())
            with mock.patch(__name__+'.MAX_RAW',10),self.assertRaises(TraceError):checked_events(d)
            packed.write_bytes(gzip.compress(payload+b' ',mtime=0))
            with self.assertRaises(TraceError):checked_events(d)

    def test_correlated_late_interval_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d)
            samples=[{'input_id':1,'frame_id':1,'start_ns':1090000000,'submit_ns':1200000000,
                      'end_ns':1340000000,'wall_ms':250,'build_cpu_ms':5}]
            result=correlate(d,samples)
            self.assertEqual(len(result['late_samples']),1)
            self.assertAlmostEqual(result['late_samples'][0]['syscalls'][0]['wall_ms'],230)
            samples[0]['start_ns']=900000000
            with self.assertRaises(TraceError):correlate(d,samples)

    def test_instance_ownership_conflict_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name='k230-stall-'+'a'*16;p=root/'instances'/name;p.mkdir(parents=True)
            state={'instance':name,'inode':p.stat().st_ino,'filters':{'raw_syscalls/sys_enter':'expected'}}
            c=p/'events/raw_syscalls/sys_enter';c.mkdir(parents=True);(c/'filter').write_text('foreign')
            (p/'tracing_on').write_text('1')
            with self.assertRaises(TraceError):stop_owned(state,root)
            self.assertEqual((p/'tracing_on').read_text(),'1')
            state['inode']+=1
            with self.assertRaises(TraceError):owned_path(state,root)
            state['instance']='../foreign'
            with self.assertRaises(TraceError):owned_path(state,root)

    def test_smoke_failure_closes_owned_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            class Fake:
                def __init__(self,directory,target):self.state_path=directory/'state'
                def prepare(self):self.state_path.touch()
                def start(self):calls.append('start')
                def close(self):calls.append('close')
            with mock.patch(__name__+'.Session',Fake),mock.patch('os.write',side_effect=OSError(errno.EIO,'fixture')):
                with self.assertRaises(OSError):board_smoke(argparse.Namespace(output=Path(tmp)/'new'))
            self.assertEqual(calls,['start','close'])

    def test_real_benchmark_parser_keeps_frame_join_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);log.Fixtures().make_trial(d);run=d/'1-debug'
            self.assertEqual(len(benchmark(run)[2]),864)
            manifest=json.loads((run/'metadata.json').read_text());p=run/manifest['runs'][0]['log']
            rows=p.read_text().splitlines();rows.pop(next(i for i,r in enumerate(rows) if 'event=present' in r));p.write_text('\n'.join(rows)+'\n')
            with self.assertRaises(baseline.perf.InvalidTrace):benchmark(run)


if __name__=='__main__':
    sys.exit(main())
