#!/usr/bin/env python3
"""Bounded idle-board function-entry timing of HDMI polling and EDID stages."""
import argparse
import fcntl
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

_spec=importlib.util.spec_from_file_location('detect_holder',Path(__file__).with_name('landscape-drm-holder.py'))
holder=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(holder)
base,log,cap=holder.base,holder.log,holder.cap
Error=base.TraceError
SCHEMA='landscape-hdmi-detect-v1'
PROBE=holder.FUNCTIONS|frozenset(('drm_atomic_helper_connector_hdmi_hotplug',
    'drm_atomic_helper_connector_hdmi_update','drm_bridge_connector_read_edid',
    'lt9611_bridge_edid_read','lt9611_get_edid_block','drm_edid_connector_update'))
SMOKE=frozenset(('hrtimer_nanosleep',))
PARENTS=PROBE|SMOKE|frozenset(('drm_bridge_connector_detect','drm_bridge_edid_read'))
GLOBAL=base.GLOBAL+('set_ftrace_filter','set_graph_function','trace_options')
MAX_BYTES=8*1024*1024
MAX_RECORDS=100000
DEPENDENCIES=('landscape-drm-holder.py','landscape-hdmi-stall-trace.py','landscape-hdmi-logging.py',
    'hdmi-shell-capture-board.py','landscape-hdmi-baseline.py','hdmi-shell-performance.py')


def global_state():return {n:log.digest(base.ROOT/n) for n in GLOBAL}
def dependencies():return {n:log.digest(Path(__file__).with_name(n)) for n in DEPENDENCIES}
def selected(mode):
    if mode not in ('smoke','probe'):raise Error('unknown capture mode')
    return SMOKE if mode=='smoke' else PROBE


def export(raw,directory,mode,pid):
    records=[];previous=-1
    with raw.open() as src,(directory/'events.jsonl').open('w') as out:
        for line in src:
            if not line.strip() or line.lstrip().startswith('#'):continue
            match=holder.FUNCTION_LINE.fullmatch(line.rstrip('\n'))
            if match:
                task,cpu,stamp,symbol,parent=match.groups()
                if symbol not in selected(mode):raise Error('unknown function payload; raw text stays private')
                row={'event':'function','pid':int(task),'cpu':int(cpu),'ts_ns':base.timestamp(stamp),
                     'symbol':symbol,'parent':parent if parent in PARENTS else '[other]'}
            else:
                row=base.parse_line(line,pid)
                if row is None:continue
                if row['event']!='marker' or row['pid']!=pid:raise Error('unexpected event or marker owner')
            if row['cpu']!=0 or row['ts_ns']<previous:raise Error('mixed CPU or trace order')
            previous=row['ts_ns'];records.append(row)
            if len(records)>MAX_RECORDS:raise Error('trace record bound exceeded')
            out.write(json.dumps(row,separators=(',',':'))+'\n')
    if (directory/'events.jsonl').stat().st_size>MAX_BYTES:raise Error('public export exceeds bound')
    return len(records)


def checked(directory):
    meta=json.loads((directory/'trace.json').read_text());mode=meta.get('mode');allowed=selected(mode)
    if (meta.get('schema')!=SCHEMA or '[mono]' not in meta.get('trace_clock','') or
        meta.get('function_filter')!=sorted(allowed) or meta.get('current_tracer')!='function'):
        raise Error('trace schema/clock/filter/tracer differs')
    with (directory/'events.jsonl').open('rb') as src:data=src.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES or hashlib.sha256(data).hexdigest()!=meta.get('events_sha256'):
        raise Error('export size or identity differs')
    rows=[];previous=-1
    for line in data.decode().splitlines():
        if len(line)>1024:raise Error('record exceeds public schema bound')
        row=json.loads(line);common={'event','pid','cpu','ts_ns'}
        if row.get('event')=='function':
            if (set(row)!=common|{'symbol','parent'} or type(row['symbol']) is not str or
                row['symbol'] not in allowed or type(row['parent']) is not str or
                (row['parent']!='[other]' and row['parent'] not in PARENTS)):
                raise Error('unknown/private function record')
        elif row.get('event')=='marker':
            if (set(row)!=common|{'phase','before_ns'} or row['phase'] not in ('start','end') or
                type(row['before_ns']) is not int or row['pid']!=meta['controller_pid']):
                raise Error('unknown/private marker record')
        else:raise Error('unknown event schema')
        if (any(type(row[k]) is not int for k in ('pid','cpu','ts_ns')) or row['pid']<=0 or
            row['cpu']!=0 or row['ts_ns']<previous):raise Error('invalid event scalar/order')
        previous=row['ts_ns'];rows.append(row)
        if len(rows)>MAX_RECORDS:raise Error('record count exceeds bound')
    if len(rows)!=meta.get('event_count') or not meta.get('stats'):raise Error('missing trace counts')
    for stat in meta['stats'].values():
        if any(stat.get(k)!=0 for k in ('overrun','commit overrun','dropped events')):raise Error('trace loss or missing loss counter')
    if sum(s.get('entries',-MAX_RECORDS) for s in meta['stats'].values())!=len(rows):raise Error('ring/export entry count differs')
    markers={}
    for phase in ('start','end'):
        entries=[r for r in rows if r['event']=='marker' and r['phase']==phase];bound=meta['markers'][phase]
        if (bound['before_ns']>bound['after_ns'] or len(entries)!=1 or entries[0]['before_ns']!=bound['before_ns'] or
            not bound['before_ns']-1000<=entries[0]['ts_ns']<=bound['after_ns']+1000):
            raise Error('monotonic marker missing or outside bracket')
        markers[phase]=entries[0]['ts_ns']
    if markers['start']>=markers['end']:raise Error('marker order differs')
    return [r for r in rows if markers['start']<=r['ts_ns']<=markers['end']],meta


def ownership(path,state):
    actual=[s.split()[0] for s in (path/'set_ftrace_filter').read_text().splitlines() if s.strip() and not s.startswith('#')]
    tracer=(path/'current_tracer').read_text().strip()
    if ((sorted(actual)!=state['function_filter'] and not (not actual and tracer=='nop' and state['phase']=='created')) or
        tracer not in ('nop','function') or (tracer=='nop' and state['phase']=='recording') or
        (path/'events/enable').read_text().strip()!='0'):
        raise Error('owned function tracer/filter/events changed')


def cleanup(state_path):
    state=json.loads(state_path.read_text())
    if state.get('schema')!=SCHEMA:raise Error('cleanup state schema differs')
    with state_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);path=base.owned_path(state)
        if path.exists():
            ownership(path,state);(path/'tracing_on').write_text('0');(path/'current_tracer').write_text('nop');path.rmdir()
        if global_state()!=state['global_before']:raise Error('global controls/options/filters changed; do not overwrite them')
        log.write_json(state_path.parent/'trace-cleanup.json',{'checked_at':base.now(),'instance_removed':True,
            'function_tracer_removed':True,'global_controls_unchanged':True,'global_after':global_state()})


class Session(base.Session):
    def __init__(self,directory,mode):
        super().__init__(directory,os.getpid());self.mode=mode
        self.state.update(schema=SCHEMA,global_before=global_state(),mode=mode,function_filter=sorted(selected(mode)),phase='created')

    def prepare(self):
        if Path('/sys/devices/system/cpu/online').read_text().strip()!='0':raise Error('requires only CPU0')
        available=int(re.search(r'^MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text(),re.M)[1])
        if available<128*1024:raise Error('insufficient free memory')
        base.atomic_json(self.state_path,self.state);unit=self.state['cleanup_unit']
        log.command('systemd-run','--quiet','--unit='+unit,'--on-active=600s',sys.executable,
                    str(Path(__file__).resolve()),'--cleanup',str(self.state_path))
        if log.command('systemctl','is-active',unit+'.timer')!='active':raise Error('independent cleanup did not arm')
        self.path.mkdir();self.state['inode']=self.path.stat().st_ino;base.atomic_json(self.state_path,self.state)
        (self.path/'tracing_on').write_text('0');(self.path/'events/enable').write_text('0');(self.path/'trace_clock').write_text('mono')
        (self.path/'per_cpu/cpu0/buffer_size_kb').write_text('1024')
        total=int((self.path/'buffer_total_size_kb').read_text().split()[0])
        if total>8192:raise Error('function ring exceeds8MiB')
        for name in ('sym-addr','sym-offset','userstacktrace'):(self.path/'options'/name).write_text('0')
        (self.path/'options/print-parent').write_text('1')
        (self.path/'set_ftrace_filter').write_text('\n'.join(self.state['function_filter']))
        (self.path/'current_tracer').write_text('function');self.state['phase']='recording';base.atomic_json(self.state_path,self.state)
        ownership(self.path,self.state)
        if global_state()!=self.state['global_before']:raise Error('global state changed during setup')
        self.metadata={'schema':SCHEMA,'mode':self.mode,'controller_pid':self.target,'markers':{},'buffer_total_kb':total,
            'global_before':self.state['global_before'],'function_filter':self.state['function_filter'],'current_tracer':'function',
            'tool_sha256':log.digest(Path(__file__)),'dependencies':dependencies()}

    def finish(self):
        self.marker('end');(self.path/'tracing_on').write_text('0');ownership(self.path,self.state);stats={}
        for f in sorted((self.path/'per_cpu').glob('cpu*/stats')):
            fields={}
            for line in f.read_text().splitlines():
                if ':' in line:
                    k,v=line.split(':',1)
                    if v.strip().isdecimal():fields[k.strip()]=int(v)
            stats[f.parent.name]=fields
        with (self.path/'trace').open('rb') as src:data=src.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise Error('raw trace exceeds8MiB')
        raw=self.directory/'raw.trace';raw.write_bytes(data);raw.chmod(0o600)
        count=export(raw,self.directory,self.mode,self.target)
        self.metadata.update(stats=stats,event_count=count,raw_bytes=len(data),raw_sha256=log.digest(raw),
            events_sha256=log.digest(self.directory/'events.jsonl'),trace_clock=(self.path/'trace_clock').read_text().strip())
        log.write_json(self.directory/'trace.json',self.metadata);checked(self.directory)

    def close(self):
        cleanup(self.state_path);log.command('systemctl','stop',self.state['cleanup_unit']+'.timer')
        row=json.loads((self.directory/'trace-cleanup.json').read_text())
        row['cleanup_timer_active']=subprocess.run(['systemctl','is-active','--quiet',self.state['cleanup_unit']+'.timer']).returncode==0
        log.write_json(self.directory/'trace-cleanup.json',row)


def cleanup_checked(directory):
    row=json.loads((directory/'trace-cleanup.json').read_text());meta=json.loads((directory/'trace.json').read_text())
    if (row.get('instance_removed') is not True or row.get('function_tracer_removed') is not True or
        row.get('cleanup_timer_active') is not False or row.get('global_controls_unchanged') is not True or
        row.get('global_after')!=meta['global_before']):raise Error('capture cleanup incomplete')
    return row


def analyze(rows):
    functions=[{k:v for k,v in r.items() if k!='event'} for r in rows if r['event']=='function']
    held,rejected=holder.intervals(functions);stages=[];without=[];bad=[]
    for h in held:
        local=[r for r in functions if r['pid']==h['pid'] and h['probe_ns']<=r['ts_ns']<=h['drop_ns']]
        def of(name):return [r for r in local if r['symbol']==name]
        readers=of('drm_bridge_connector_read_edid');callbacks=of('lt9611_bridge_edid_read');blocks=of('lt9611_get_edid_block')
        updates=of('drm_edid_connector_update');hotplug=of('drm_atomic_helper_connector_hdmi_hotplug')
        helpers=of('drm_atomic_helper_connector_hdmi_update')
        if not readers:
            if callbacks or blocks:bad.append(dict(h,reason='EDID callback without reader boundary'))
            else:without.append(h)
            continue
        if (len(readers)!=1 or len(callbacks)!=1 or len(updates)!=1 or len(hotplug)!=1 or len(helpers)>1 or
            not 1<=len(blocks)<=8 or readers[0]['parent'] not in ('drm_atomic_helper_connector_hdmi_update','drm_atomic_helper_connector_hdmi_hotplug') or
            callbacks[0]['parent'] not in ('drm_bridge_edid_read','drm_bridge_connector_read_edid') or
            updates[0]['parent'] not in ('drm_atomic_helper_connector_hdmi_update','drm_atomic_helper_connector_hdmi_hotplug')):
            bad.append(dict(h,reason='ambiguous EDID markers/callers'));continue
        read,callback,update=readers[0]['ts_ns'],callbacks[0]['ts_ns'],updates[0]['ts_ns']
        if not h['detect_ns']<=hotplug[0]['ts_ns']<=read<=callback<=blocks[0]['ts_ns']<=blocks[-1]['ts_ns']<update<=h['drop_ns']:
            bad.append(dict(h,reason='EDID stage order differs'));continue
        if helpers and not hotplug[0]['ts_ns']<=helpers[0]['ts_ns']<=read:
            bad.append(dict(h,reason='HDMI update helper order differs'));continue
        stage=dict(h,read_ns=read,callback_ns=callback,connector_update_ns=update,block_callback_count=len(blocks),
            before_edid_ms=(read-h['detect_ns'])/1e6,edid_path_ms=(update-read)/1e6,
            after_edid_ms=(h['drop_ns']-update)/1e6,edid_share_percent=100*(update-read)/(h['drop_ns']-h['detect_ns']))
        stages.append(stage)
    return {'edid_stages':stages,'probes_without_edid_reader_marker':without,'rejected_poll_intervals':rejected,'rejected_edid_stages':bad}


def board_smoke(args):
    directory=base.new_directory(args.output);ipc=cap.IPC();original=log.control(ipc);log.idle_startup(ipc);session=Session(directory,'smoke')
    try:
        session.prepare();session.start();before=time.monotonic_ns();time.sleep(.05);after=time.monotonic_ns();session.finish()
    finally:
        try:base.safe_close(session)
        finally:ipc.close()
    rows,meta=checked(directory);cleanup_checked(directory)
    if not any(r['event']=='function' and r['pid']==meta['controller_pid'] and before-1000<=r['ts_ns']<=after+1000 for r in rows):
        raise Error('smoke lacks controller sleep entry in bracket')
    log.write_json(directory/'smoke.json',{'schema':SCHEMA,'status':'QUALIFIED','created_at':base.now(),
        'kernel':log.command('uname','-r'),'machine':log.command('uname','-m'),'system':os.path.realpath('/run/current-system'),
        'tool_sha256':log.digest(Path(__file__)),'dependencies':dependencies(),'sleep_before_ns':before,'sleep_after_ns':after,
        'control':original,'event_count':meta['event_count']})


def board_run(args):
    smoke=json.loads((args.smoke/'smoke.json').read_text());checked(args.smoke);cleanup_checked(args.smoke)
    if (smoke.get('schema')!=SCHEMA or smoke.get('status')!='QUALIFIED' or smoke.get('kernel')!=log.command('uname','-r') or
        smoke.get('machine')!='riscv64' or smoke.get('system')!=args.expected_system or
        smoke.get('tool_sha256')!=log.digest(Path(__file__)) or smoke.get('dependencies')!=dependencies()):raise Error('qualified smoke identity differs')
    directory=base.new_directory(args.output);ipc=cap.IPC();session=None
    try:
        original=log.control(ipc);base.immutable(smoke['control'],original);log.idle_startup(ipc)
        if (original['system']!=args.expected_system or original['persistent_system']!=args.expected_system or
            original['executable_sha256']!=args.expected_executable_sha256 or not original['debug_flag']):raise Error('installed baseline differs')
        outputs=original['output']
        if (len(outputs)!=1 or outputs[0]['name']!='HDMI-A-1' or outputs[0]['transform']!='normal' or outputs[0]['scale']!=1 or
            outputs[0]['current_mode']['width']!=1280 or outputs[0]['current_mode']['height']!=800):raise Error('landscape geometry differs')
        log.write_json(directory/'original.json',original);log.write_json(directory/'qualified-smoke.json',smoke)
        session=Session(directory,'probe');session.prepare();session.start();before=time.monotonic_ns();time.sleep(35);after=time.monotonic_ns();session.finish()
    finally:
        try:
            if session:base.safe_close(session)
            if (directory/'original.json').exists():
                original=json.loads((directory/'original.json').read_text());ipc.command('card_shell benchmark-stop');ipc.command('card_shell home')
                final=log.control(ipc);base.immutable(original,final)
                log.write_json(directory/'normal.json',{'checked_at':base.now(),'control':final,'idle_terminal':log.idle_startup(ipc),
                    'services':log.command('systemctl','is-active','shell.service','shell-ui.service').splitlines(),
                    'virtual_test_devices':sum('injected' in r.get('name','').lower() or 'fixture' in r.get('name','').lower() for r in ipc.request(100)),
                    'home_command_succeeded':True,'benchmark_stop_succeeded':True})
        finally:ipc.close()
    log.write_json(directory/'trial.json',{'schema':SCHEMA,'status':'CAPTURED','observation':'single35sidle',
        'idle_before_ns':before,'idle_after_ns':after,'tool_sha256':log.digest(Path(__file__)),'dependencies':dependencies()})


def report(directory):
    rows,meta=checked(directory);cleanup_checked(directory)
    trial=json.loads((directory/'trial.json').read_text());smoke=json.loads((directory/'qualified-smoke.json').read_text())
    if (trial.get('schema')!=SCHEMA or trial.get('status')!='CAPTURED' or trial.get('observation')!='single35sidle' or meta['mode']!='probe' or
        not 35e9<=trial['idle_after_ns']-trial['idle_before_ns']<=60e9 or
        not meta['markers']['start']['after_ns']<=trial['idle_before_ns']<=trial['idle_after_ns']<=meta['markers']['end']['before_ns'] or
        not trial['tool_sha256']==meta['tool_sha256']==smoke['tool_sha256'] or
        not trial['dependencies']==meta['dependencies']==smoke['dependencies'] or smoke.get('status')!='QUALIFIED'):
        raise Error('capture/smoke identity, mode or idle bracket differs')
    normal=json.loads((directory/'normal.json').read_text());original=json.loads((directory/'original.json').read_text())
    base.immutable(smoke['control'],original);base.immutable(original,normal['control'])
    if (normal['services']!=['active','active'] or normal['virtual_test_devices']!=0 or
        normal.get('home_command_succeeded') is not True or normal.get('benchmark_stop_succeeded') is not True or
        not normal['idle_terminal'].get('idle_shell_without_child_jobs')):raise Error('normal state incomplete')
    result=analyze(rows)
    if len(result['edid_stages'])<3:raise Error('fewer than three qualified EDID stage intervals')
    result.update(schema=SCHEMA,status='STAGE_MEASURED',created_at=base.now(),trace=meta,original=original,normal=normal,
        report_tool_sha256=log.digest(Path(__file__)),limits=['Idle-board observation; no new gesture/native/glass/optical or latency-improvement proof.',
        'Stage boundaries are function entries: EDID path includes wrappers, validation and return overhead, instrumentation and scheduling.',
        'No EDID bytes, individual I2C durations, exact inlined function-return time, mutex pointers or per-probe connector IDs were collected.'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--self-test',action='store_true');g.add_argument('--board-smoke',action='store_true');g.add_argument('--board-run',action='store_true')
    g.add_argument('--report',type=Path);g.add_argument('--cleanup',type=Path);p.add_argument('--output',type=Path);p.add_argument('--smoke',type=Path)
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
            if (args.output is None or args.smoke is None or not re.fullmatch('[0-9a-f]{64}',args.expected_executable_sha256 or '') or
                not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+',args.expected_system or '')):p.error('trial needs smoke, system/executable identity and new output')
            board_run(args)
    except (Error,log.TrialError,cap.CaptureError,OSError,EOFError,KeyError,ValueError,subprocess.SubprocessError) as error:
        print('hdmi-detect: '+str(error),file=sys.stderr);return 2
    return 0


class Fixtures(unittest.TestCase):
    def path(self,pid=99):
        rows=[]
        sequence=[('output_poll_execute',0,'[other]'),('drm_helper_probe_detect_ctx',1000,'output_poll_execute'),
            ('detect_connector_status',2000,'drm_helper_probe_detect_ctx'),('lt9611_bridge_detect',3000,'drm_bridge_connector_detect'),
            ('drm_atomic_helper_connector_hdmi_hotplug',500000,'drm_bridge_connector_detect'),
            ('drm_atomic_helper_connector_hdmi_update',501000,'drm_atomic_helper_connector_hdmi_hotplug'),
            ('drm_bridge_connector_read_edid',502000,'drm_atomic_helper_connector_hdmi_update'),
            ('lt9611_bridge_edid_read',503000,'drm_bridge_edid_read'),('lt9611_get_edid_block',504000,'[other]'),
            ('lt9611_get_edid_block',180500000,'[other]'),('drm_edid_connector_update',180501000,'drm_atomic_helper_connector_hdmi_update'),
            ('drm_modeset_drop_locks',181000000,'drm_helper_probe_detect_ctx')]
        for cycle in range(3):
            rows.extend(dict(event='function',pid=pid,cpu=0,ts_ns=1_000_000_000+cycle*10_240_000_000+t,symbol=s,parent=p) for s,t,p in sequence)
        return rows

    def test_three_stages_and_additive_boundaries(self):
        r=analyze(self.path());self.assertEqual(len(r['edid_stages']),3);self.assertFalse(r['rejected_edid_stages'])
        for stage in r['edid_stages']:
            self.assertAlmostEqual(stage['edid_path_ms'],179.999)
            self.assertAlmostEqual(sum(stage[k] for k in ('before_edid_ms','edid_path_ms','after_edid_ms')),stage['held_lower_bound_ms'])
            self.assertGreater(stage['edid_share_percent'],99);self.assertLess(stage['edid_share_percent'],100)

    def test_foreign_worker_cannot_supply_stage(self):
        rows=self.path();rows.append(dict(event='function',pid=101,cpu=0,ts_ns=1000502500,symbol='drm_bridge_connector_read_edid',parent='[other]'))
        rows.sort(key=lambda r:r['ts_ns']);self.assertEqual(len(analyze(rows)['edid_stages']),3)
        for row in rows:
            if row['symbol']=='lt9611_bridge_edid_read':row['pid']=101
        self.assertFalse(analyze(rows)['edid_stages'])

    def test_missing_duplicate_wrong_caller(self):
        for name in ('lt9611_bridge_edid_read','lt9611_get_edid_block','drm_edid_connector_update','drm_atomic_helper_connector_hdmi_hotplug'):
            with self.subTest(name=name):self.assertFalse(analyze([r for r in self.path() if r['symbol']!=name])['edid_stages'])
        rows=self.path();duplicate=dict(rows[6],ts_ns=rows[6]['ts_ns']+1);rows.append(duplicate);rows.sort(key=lambda r:r['ts_ns'])
        self.assertEqual(len(analyze(rows)['edid_stages']),2)
        rows=self.path()
        for row in rows:
            if row['symbol']=='drm_bridge_connector_read_edid':row['parent']='[other]'
        self.assertFalse(analyze(rows)['edid_stages'])

    def test_inlined_update_helper_variant(self):
        rows=[r for r in self.path() if r['symbol']!='drm_atomic_helper_connector_hdmi_update']
        for row in rows:
            if row['parent']=='drm_atomic_helper_connector_hdmi_update':row['parent']='drm_atomic_helper_connector_hdmi_hotplug'
        self.assertEqual(len(analyze(rows)['edid_stages']),3)

    def fixture(self,d):
        raw=('private-10 [000] .... 1.000000: tracing_mark_write: K230_STALL start before_ns=999999900\n'
            'private-10 [000] .... 1.050000: hrtimer_nanosleep <-private_caller\n'
            'private-10 [000] .... 1.100000: tracing_mark_write: K230_STALL end before_ns=1099999900\n')
        (d/'raw').write_text(raw);export(d/'raw',d,'smoke',10)
        meta={'schema':SCHEMA,'mode':'smoke','controller_pid':10,'trace_clock':'[mono]','function_filter':sorted(SMOKE),
            'current_tracer':'function','events_sha256':log.digest(d/'events.jsonl'),'event_count':3,
            'stats':{'cpu0':{'entries':3,'overrun':0,'commit overrun':0,'dropped events':0}},
            'markers':{'start':{'before_ns':999999900,'after_ns':1000000100},'end':{'before_ns':1099999900,'after_ns':1100000100}}}
        log.write_json(d/'trace.json',meta);return meta

    def test_private_payload_rejection_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);self.fixture(d);text=(d/'events.jsonl').read_text();self.assertNotIn('private',text)
            for unsafe in ('secret_text','0xffffffffdeadbeef','hrtimer_nanosleep payload=secret','sys_enter: NR 29 (a, b, c, 0, 0, 0)'):
                (d/'raw').write_text('private-10 [000] .... 1.050000: '+unsafe+'\n')
                with self.subTest(unsafe=unsafe),self.assertRaises(Error):export(d/'raw',d,'smoke',10)

    def test_clock_loss_count_hash_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);meta=self.fixture(d);self.assertEqual(len(checked(d)[0]),3)
            changes=[('event_count',4),('events_sha256','0'*64),('trace_clock','[local]'),('function_filter',[]),
                ('stats',{'cpu0':{'entries':3,'overrun':1,'commit overrun':0,'dropped events':0}}),
                ('stats',{'cpu0':{'entries':4,'overrun':0,'commit overrun':0,'dropped events':0}}),
                ('markers',{'start':{'before_ns':999999900,'after_ns':999999800},'end':meta['markers']['end']})]
            for key,value in changes:
                log.write_json(d/'trace.json',dict(meta,**{key:value}))
                with self.subTest(key=key),self.assertRaises(Error):checked(d)
            log.write_json(d/'trace.json',meta);rows=[json.loads(l) for l in (d/'events.jsonl').read_text().splitlines()]
            rows[1]['pointer']='secret';(d/'events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n');meta['events_sha256']=log.digest(d/'events.jsonl');log.write_json(d/'trace.json',meta)
            with self.assertRaises(Error):checked(d)

    def test_cleanup_foreign_control_and_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'set_ftrace_filter').write_text('hrtimer_nanosleep\n');(d/'current_tracer').write_text('function\n');(d/'events').mkdir();(d/'events/enable').write_text('0\n')
            state={'function_filter':sorted(SMOKE),'phase':'recording'};ownership(d,state)
            for filename,value in [('set_ftrace_filter','foreign_function'),('current_tracer','nop'),('events/enable','1')]:
                old=(d/filename).read_text();(d/filename).write_text(value)
                with self.subTest(filename=filename),self.assertRaises(Error):ownership(d,state)
                (d/filename).write_text(old)
            root=d/'root';path=root/'instances/k230-stall-0123456789abcdef';path.mkdir(parents=True)
            with self.assertRaises(Error):base.owned_path({'instance':path.name,'inode':path.stat().st_ino+1},root)


if __name__=='__main__':sys.exit(main())
