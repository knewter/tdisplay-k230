#!/usr/bin/env python3
"""Bounded capture of one real K230 HDMI card-shell benchmark session.

The helper records only the public benchmark diagnostic grammars consumed by
``hdmi-shell-performance.py``. It does not treat injected events as physical
contact evidence, nor does this capture establish optical visibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

SOCKET = '/run/shell/sway-ipc.sock'
MAGIC = b'i3-ipc'
SCHEMA = 'hdmi-shell-performance-v1'
PREFIXES = ('K230_CARD_BENCH ', 'K230_CARD_SHELL ', 'K230_PIXMAN_DRAW ',
            'K230_PIXMAN_OUTPUT_TURN ')
MAX_JOURNAL = 16 * 1024 * 1024
MAX_ROWS = 20_000
SAFE_VALUE = re.compile(r'[A-Za-z0-9_.:+/-]{1,512}\Z')
RUN_FIELDS = {'run','source_revision','compositor_executable','pixman_identity','kernel',
              'logical_width','logical_height','physical_width','physical_height','transform',
              'scale','format','cards','input_class','operator_confirmed_contacts','variant',
              'drag_count','clock','log'}


class CaptureError(RuntimeError):
    pass


class IPC:
    def __init__(self, path=SOCKET, timeout=2):
        self.path, self.timeout = path, timeout
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(path)
        self.pid = struct.unpack('3i', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
        self.seq = 0

    def close(self):
        self.sock.close()

    def request(self, kind, payload=''):
        data = payload.encode()
        self.sock.sendall(MAGIC + struct.pack('<II', len(data), kind) + data)
        header = self._read(14)
        if header[:6] != MAGIC:
            raise CaptureError('invalid i3 IPC response')
        length, response = struct.unpack('<II', header[6:])
        if length > 4 * 1024 * 1024 or response != kind:
            raise CaptureError('unexpected or oversized i3 IPC response')
        try:
            return json.loads(self._read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CaptureError('invalid i3 IPC JSON') from error

    def _read(self, length):
        data = bytearray()
        while len(data) < length:
            block = self.sock.recv(length - len(data))
            if not block:
                raise CaptureError('i3 IPC disconnected')
            data.extend(block)
        return bytes(data)

    def outputs(self):
        return self.request(3)

    def tree(self):
        return self.request(4)

    def command(self, text):
        response = self.request(0, text)
        if not isinstance(response, list) or not response or not all(x.get('success') for x in response):
            raise CaptureError('Sway rejected a card_shell command')
        return response


def output_state(outputs):
    """Keep only output facts needed to validate and restore this capture."""
    if not isinstance(outputs, list):
        raise CaptureError('invalid output response')
    rows = []
    for out in outputs:
        if not isinstance(out, dict) or not out.get('active'):
            continue
        rect = out.get('rect') or {}
        row = {key: out.get(key) for key in ('name','active','transform','scale','current_mode')}
        row['rect'] = {k: rect.get(k) for k in ('x','y','width','height')}
        # Some Sway builds expose this output property, others do not.
        if 'render_bit_depth' in out:
            row['render_bit_depth'] = out['render_bit_depth']
        rows.append(row)
    return rows


def app_count(node):
    count = 0
    if isinstance(node, dict):
        props = node.get('window_properties') or {}
        names = [node.get('app_id'), props.get('class'), props.get('instance')]
        if any(str(n or '').casefold() in ('foot','k230-terminal') for n in names):
            count += 1
        for key in ('nodes','floating_nodes'):
            count += sum(app_count(child) for child in node.get(key, []))
    return count


def runtime_identity(pid, variant):
    proc = Path('/proc') / str(pid)
    try:
        exe = os.readlink(proc / 'exe')
        exe_hash = hashlib.sha256((proc / 'exe').read_bytes()).hexdigest()
        env = (proc / 'environ').read_bytes().split(b'\0')
        env = dict(item.split(b'=', 1) for item in env if b'=' in item)
        mapping = next((line.split()[-1] for line in (proc/'maps').read_text().splitlines()
                        if 'libpixman-1.so' in line and line.split()[-1].startswith('/')), None)
        if not mapping:
            raise CaptureError('compositor has no identifiable loaded Pixman library')
        pix_hash = hashlib.sha256(Path(mapping).read_bytes()).hexdigest()
    except (OSError, StopIteration) as error:
        raise CaptureError('cannot identify live compositor executable or Pixman') from error
    toggles = [env.get(name.encode(), b'').decode(errors='ignore') for name in
               ('WLR_PIXMAN_QUARTER_TURN','WLR_PIXMAN_OUTPUT_TURN')]
    enabled = any(value == '1' for value in toggles)
    if variant == 'candidate' and not enabled:
        raise CaptureError('candidate compositor runtime opt-in is not enabled')
    if variant == 'baseline' and any(value not in ('', '0') for value in toggles):
        raise CaptureError('baseline compositor has a quarter-turn runtime opt-in')
    return {'compositor_executable': f'{exe} sha256:{exe_hash}',
            'pixman_identity': f'{mapping} sha256:{pix_hash}',
            'environment': {'WLR_PIXMAN_QUARTER_TURN': toggles[0],
                            'WLR_PIXMAN_OUTPUT_TURN': toggles[1]}}


def journal(since, timeout=8):
    try:
        result = subprocess.run(['journalctl','--unit=k230-card-shell.service','--since',since,
                                 '--output=cat','--lines=20000'], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise CaptureError('bounded journal capture failed') from error
    if len(result.stdout) > MAX_JOURNAL:
        raise CaptureError('journal capture exceeds size limit')
    return result.stdout.decode('utf-8', errors='replace')


def allowlisted_records(text, run_id, start_ns, end_ns):
    """Sanitize strictly; never persist non-allowlisted journal content."""
    result, session, discovered = [], None, run_id
    bench_keys = {
        'session': {'v','run','event','t_ns','clock','backend','renderer','width','height','output_format','input','cards'},
        'input': {'v','run','event','input_id','gesture_id','kind','source','t_ns'},
        'submit': {'v','run','event','input_id','frame_id','t_ns','update_cpu_ns','final'},
        'present': {'v','run','event','frame_id','t_ns','presented','clock'},
        'resource': {'v','run','event','phase','t_ns','cpu_ns','memory_bytes','scope'},
        'incomplete': {'v','run','event','reason'},
        'error': {'v','run','event','reason'}}
    shell_fields = {
        'input-origin': {'run','input_id','source_ns'},
        'repaint-cost': {'run','frame_id','render_cpu_ns','prepare_cpu_ns','build_cpu_ns','commit_cpu_ns','attempts','failed_attempts'},
        'frame-cost': {'run','frame_id','total_cpu_ns','render_cpu_ns','input_cpu_ns'},
        'input-cost': {'run','input_id','cpu_ns','policy_cpu_ns','scene_cpu_ns','chrome_cpu_ns'},
        'touch-route': {'phase','id','source_ms','dispatch_ms','x','y','width','height','edge','bottom_reserved','consumed','active','mode','ui','lock','launcher','drawer','popup','points','pointer','contact','edge_tracking','blocked','home'}}
    draw_keys = {'transform','path','copy_cpu_ns','total_cpu_ns','dst_pixels','scratch_bytes'}
    turn_keys = {'src','dst','format','rotation','rotation_cpu_ns','scratch_bytes'}
    source_lines = text.splitlines()[:MAX_ROWS]
    benchmark_error = None
    if discovered is None:
        # Journal order is not an API contract. Select the newest benchmark
        # arm by compositor monotonic time, never by the first session row.
        candidates = []
        for raw in source_lines:
            marker = 'K230_CARD_BENCH '
            if marker not in raw or len(raw) > 8192:
                continue
            fields = {}
            for pair in raw[raw.find(marker)+len(marker):].split():
                if '=' not in pair:
                    fields = {}; break
                key, value = pair.split('=', 1); fields[key] = value
            if fields.get('event') == 'resource' and fields.get('phase') == 'baseline':
                try:
                    stamp = int(fields['t_ns'])
                    if start_ns <= stamp <= end_ns:
                        candidates.append((stamp, fields.get('run')))
                except (KeyError, ValueError):
                    pass
        if candidates:
            discovered = max(candidates)[1]
    for raw in source_lines:
        if len(raw) > 8192:
            continue
        line = next((raw[raw.find(prefix):] for prefix in PREFIXES if prefix in raw), None)
        if not line:
            continue
        prefix = next(prefix for prefix in PREFIXES if line.startswith(prefix))
        words = line[len(prefix):].split()
        if not words:
            continue
        kind = words[0] if prefix == 'K230_CARD_SHELL ' else ''
        if prefix == 'K230_CARD_SHELL ' and kind not in shell_fields:
            continue
        if prefix == 'K230_CARD_SHELL ':
            words = words[1:]
        fields = {}
        valid = True
        for pair in words:
            if '=' not in pair:
                valid = False; break
            key, value = pair.split('=', 1)
            if key in fields or not SAFE_VALUE.fullmatch(value):
                valid = False; break
            fields[key] = value
        if not valid:
            continue
        expected = (bench_keys.get(fields.get('event')) if prefix == 'K230_CARD_BENCH ' else
                    shell_fields.get(kind) if prefix == 'K230_CARD_SHELL ' else
                    draw_keys if prefix == 'K230_PIXMAN_DRAW ' else turn_keys)
        if (prefix == 'K230_CARD_BENCH ' and fields.get('event') in ('incomplete','error')
                and fields.get('run') == discovered):
            # Keep only a known safe reason in context. Do not add this marker
            # to the parser log, whose stable schema intentionally has no error event.
            reason = fields.get('reason')
            benchmark_error = reason if reason in ('input-overflow',) else 'benchmark-error'
        if prefix == 'K230_PIXMAN_OUTPUT_TURN ':
            numeric = (re.fullmatch(r'[0-9]{1,6}x[0-9]{1,6}', fields.get('src','')) and
                       re.fullmatch(r'[0-9]{1,6}x[0-9]{1,6}', fields.get('dst','')) and
                       re.fullmatch(r'0x[0-9A-Fa-f]{1,8}', fields.get('format','')) and
                       all(re.fullmatch(r'[0-9]{1,20}', fields.get(key,'')) for key in
                           ('rotation','rotation_cpu_ns','scratch_bytes')))
            if not numeric:
                continue
        if expected is None or set(fields) != expected:
            continue
        if prefix == 'K230_CARD_BENCH ':
            if fields.get('event') not in bench_keys:
                continue
            if fields['event'] == 'resource' and fields.get('phase') == 'baseline':
                if fields.get('run') == discovered:
                    session = dict(fields)
            if fields.get('event') == 'session':
                if fields.get('run') == discovered:
                    session = dict(fields)
            selected_run = discovered
            if selected_run is None or fields.get('run') != selected_run:
                continue
            try:
                t = int(fields['t_ns'])
            except (KeyError, ValueError):
                continue
            if not start_ns <= t <= end_ns:
                continue
        elif prefix == 'K230_CARD_SHELL ':
            selected_run = discovered
            if 'run' in fields and fields['run'] != selected_run:
                continue
        elif prefix == 'K230_PIXMAN_DRAW ':
            # Pixman rows have no run id: retain only a fixed numeric grammar from this bounded journal window.
            if not all(value.isdecimal() or SAFE_VALUE.fullmatch(value) for value in fields.values()):
                continue
        result.append(line)
    return result, session, discovered, benchmark_error


def complete_gestures(lines):
    gestures = {}
    for line in lines:
        if not line.startswith('K230_CARD_BENCH '):
            continue
        fields = dict(pair.split('=',1) for pair in line.split()[2:])
        if fields.get('event') == 'input' and fields.get('kind') in ('motion','release'):
            gestures.setdefault(fields.get('gesture_id'), set()).add(fields['kind'])
    return sum({'motion','release'} <= kinds for kinds in gestures.values())


def outcome(reason, stop_error, restore_error, session, count, target, benchmark_error=None):
    """Cleanup failures always override otherwise complete benchmark coverage."""
    if reason or stop_error or restore_error or benchmark_error:
        return 'INCOMPLETE', reason or stop_error or restore_error or benchmark_error
    if session and session.get('event') == 'session' and count >= target:
        return 'CAPTURED', None
    return 'INCOMPLETE', 'no complete telemetry-covered gesture set'


def capture(args):
    if args.input == 'physical' and not args.operator_confirmed_contacts:
        raise CaptureError('physical capture requires explicit --operator-confirmed-contacts')
    if args.input == 'injected' and args.operator_confirmed_contacts:
        raise CaptureError('injected capture cannot claim operator-confirmed contacts')
    if args.output.exists() and any(args.output.iterdir()):
        raise CaptureError('--output must be a new or empty directory')
    args.output.mkdir(parents=True, exist_ok=True)
    ipc = IPC()
    started = time.monotonic()
    wall_started = time.time()
    before = output_state(ipc.outputs())
    app_before = app_count(ipc.tree())
    if app_before not in (1, 2):
        ipc.close(); raise CaptureError('capture requires one or two ordinary Foot windows')
    if len(before) != 1:
        ipc.close(); raise CaptureError('capture requires exactly one active output')
    out = before[0]
    mode = out.get('current_mode') or {}
    rect = out['rect']
    physical = (mode.get('width'), mode.get('height'), out.get('transform'), out.get('scale'))
    if physical != (1920, 1080, '90', 1) and physical != (1920,1080,90,1):
        ipc.close(); raise CaptureError('required output is physical 1920x1080 transform 90 scale 1')
    if (rect.get('width'), rect.get('height')) != (1080, 1920):
        ipc.close(); raise CaptureError('required logical output geometry is 1080x1920')
    identity = runtime_identity(ipc.pid, args.variant)
    kernel = subprocess.run(['uname','-r'], text=True, stdout=subprocess.PIPE, timeout=2, check=True).stdout.strip()
    run_id = None
    t0_ns = time.monotonic_ns()
    since = time.strftime('%Y-%m-%d %H:%M:%S')
    status, reason = 'INCOMPLETE', None
    lines, session = [], None
    deadline = started + args.seconds
    entered, touch_down, active_touch_id, stop_failed, restore_failed = False, False, None, None, None
    output_after = None
    benchmark_error = None
    try:
        ipc.command('card_shell back')
        ipc.command('card_shell benchmark ' + args.input)
        # The shell creates its own run token; discover it from the bounded
        # benchmark resource row and then reject every other run identity.
        if time.monotonic() >= deadline:
            raise CaptureError('capture deadline expired while arming benchmark')
        raw = journal(since, max(.1, min(8, deadline-time.monotonic())))
        _, _, run_id, benchmark_error = allowlisted_records(raw, None, t0_ns, time.monotonic_ns())
        if not run_id:
            raise CaptureError('benchmark arm did not emit a run identity')
        if args.input == 'injected':
            ipc.command('card_shell test-touch init')
            ipc.command('card_shell enter'); entered = True
            width, height = rect['width'], rect['height']
            for index in range(args.drags):
                if time.monotonic() >= deadline:
                    raise CaptureError('capture deadline reached during injected gestures')
                start_x, end_x = ((width//2-100,width//2+100) if index % 2 == 0 else
                                   (width//2+100,width//2-100))
                gesture = index + 1
                ipc.command(f'card_shell test-touch down {gesture} {start_x} {height//2}')
                touch_down, active_touch_id = True, gesture
                for step in range(1, 7):
                    if time.monotonic() >= deadline:
                        raise CaptureError('capture deadline reached during injected gestures')
                    x = start_x + ((end_x-start_x)*step)//6
                    ipc.command(f'card_shell test-touch motion {gesture} {x} {height//2}')
                ipc.command(f'card_shell test-touch up {gesture}'); touch_down, active_touch_id = False, None
                time.sleep(min(.05, max(0, deadline-time.monotonic())))
        else:
            print('READY: swipe up from Foot into overview, then perform center horizontal drags.', flush=True)
            entered = True
            while time.monotonic() < deadline:
                time.sleep(min(.2, max(0, deadline-time.monotonic())))
                raw = journal(since, max(.1, min(8, deadline-time.monotonic())))
                lines, session, _, marker = allowlisted_records(raw, run_id, t0_ns, time.monotonic_ns())
                benchmark_error = marker or benchmark_error
                if complete_gestures(lines) >= args.drags + 1:
                    break
        if args.input == 'injected':
            entered = True
        time.sleep(min(.1, max(0, deadline-time.monotonic())))
    except Exception as error:
        reason = str(error)
    finally:
        if touch_down:
            try: ipc.command(f'card_shell test-touch up {active_touch_id}')
            except Exception: pass
        try: ipc.command('card_shell benchmark-stop')
        except Exception as error: stop_failed = str(error)
        try: ipc.command('card_shell back')
        except Exception as error: restore_failed = str(error)
        try:
            raw = journal(since)
            lines, session, _, marker = allowlisted_records(raw, run_id, t0_ns, time.monotonic_ns())
            benchmark_error = marker or benchmark_error
        except Exception as error:
            reason = reason or str(error)
        try:
            output_after = output_state(ipc.outputs())
            if output_after != before:
                # The helper never mutates output configuration. Do not reset a
                # concurrent operator change; report the changed state instead.
                raise CaptureError('output state changed during capture')
        except Exception as error:
            restore_failed = restore_failed or str(error)
        try:
            if app_count(ipc.tree()) != app_before:
                restore_failed = restore_failed or 'ordinary Foot window count changed'
        except Exception as error:
            restore_failed = restore_failed or str(error)
        ipc.close()
    count = complete_gestures(lines)
    status, reason = outcome(reason, stop_failed, restore_failed, session, count,
                             args.drags + (1 if args.input == 'physical' else 0), benchmark_error)
    log_name = 'capture.log'
    safe_log = '\n'.join(lines) + ('\n' if lines else '')
    log_path = args.output / log_name
    log_path.write_text(safe_log)
    log_path.chmod(0o600)
    logs = []
    # Never emit a run without a full parser-valid session; preserve honest zero-contact evidence.
    if status == 'CAPTURED' and session and session.get('event') == 'session':
        inputs = [dict(pair.split('=',1) for pair in line.split()[2:]) for line in lines
                  if line.startswith('K230_CARD_BENCH ') and 'event=input' in line]
        fmt = session['output_format']
        metadata = {'run':run_id,'source_revision':args.source_revision,
            'compositor_executable':identity['compositor_executable'], 'pixman_identity':identity['pixman_identity'],
            'kernel':kernel, 'logical_width':rect['width'],'logical_height':rect['height'],
            'physical_width':1920,'physical_height':1080,'transform':90,'scale':1,
            'format':fmt,'cards':int(session['cards']),'input_class':args.input,
            'operator_confirmed_contacts':bool(args.operator_confirmed_contacts), 'variant':args.variant,
            'drag_count':count,'clock':'monotonic','log':log_name}
        if set(metadata) != RUN_FIELDS:
            raise CaptureError('internal metadata schema mismatch')
        logs = [metadata]
    context = {'schema':SCHEMA,'status':status,'reason':reason,'variant':args.variant,'input':args.input,
        'operator_confirmed_contacts':bool(args.operator_confirmed_contacts), 'requested_drags':args.drags,
        'complete_drag_count':count,'seconds_limit':args.seconds,'started_unix':wall_started,
        'elapsed_seconds':round(time.monotonic()-started,3),'source_revision':args.source_revision,
        'compositor':identity,'kernel':kernel,'output_before':before,
        'output_after':output_after,
        'frequency':read_frequency(), 'stop_error':stop_failed,'restore_error':restore_failed,
        'evidence_limit':'capture telemetry is not optical proof; injected input is not physical contact.'}
    (args.output/'metadata.json').write_text(json.dumps({'schema':SCHEMA,'runs':logs},indent=2,sort_keys=True)+'\n')
    (args.output/'context.json').write_text(json.dumps(context,indent=2,sort_keys=True)+'\n')
    return 0 if status == 'CAPTURED' else 1


def read_frequency():
    result = {}
    for key, paths in {'khz':['/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'],
                       'governor':['/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'],
                       'temperature':['/sys/class/thermal/thermal_zone0/temp']}.items():
        for path in paths:
            try:
                value = Path(path).read_text().strip()
                if re.fullmatch(r'[0-9]{1,10}', value) or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
                    result[key] = value
                break
            except OSError:
                pass
    return result


class Fixtures(unittest.TestCase):
    def test_output_whitelist_and_foot_count(self):
        state = output_state([{'name':'HDMI-A-1','active':True,'transform':'90','scale':1,
            'rect':{'x':0,'y':0,'width':1080,'height':1920},'current_mode':{'width':1920,'height':1080},
            'serial':'private'}])
        self.assertNotIn('serial', state[0])
        self.assertEqual(app_count({'app_id':'foot','name':'sensitive title'}),1)

    def test_runtime_optin_contract(self):
        self.assertIn('operator_confirmed_contacts', RUN_FIELDS)
        self.assertEqual(SCHEMA,'hdmi-shell-performance-v1')

    def test_complete_gesture_count(self):
        lines=['K230_CARD_BENCH v=1 run=x event=input input_id=1 gesture_id=2 kind=motion source=injected t_ns=1',
               'K230_CARD_BENCH v=1 run=x event=input input_id=2 gesture_id=2 kind=release source=injected t_ns=2']
        self.assertEqual(complete_gestures(lines),1)

    def test_run_selection_and_allowlist(self):
        raw='\n'.join([
            'K230_CARD_BENCH v=1 run=old event=session t_ns=1 clock=monotonic backend=drm renderer=pixman width=1080 height=1920 output_format=ARGB8888 input=injected cards=1',
            'K230_CARD_BENCH v=1 run=new event=resource t_ns=100 clock=monotonic phase=baseline cpu_ns=1 memory_bytes=2 scope=compositor',
            'K230_CARD_BENCH v=1 run=new event=session t_ns=101 clock=monotonic backend=drm renderer=pixman width=1080 height=1920 output_format=ARGB8888 input=injected cards=1',
            'K230_CARD_SHELL repaint-cost run=new frame_id=5 render_cpu_ns=1 prepare_cpu_ns=1 build_cpu_ns=1 commit_cpu_ns=1 attempts=1 failed_attempts=0',
            'Foot title=private'])
        rows, session, run, error = allowlisted_records(raw,None,0,200)
        self.assertEqual(run,'new')
        self.assertEqual(session['event'],'session')
        self.assertIsNone(error)
        self.assertTrue(all('old' not in row and 'private' not in row for row in rows))

    def test_incomplete_overflow_marker_and_output_turn_record(self):
        raw='\n'.join([
            'K230_CARD_BENCH v=1 run=selected event=resource t_ns=10 clock=monotonic phase=baseline cpu_ns=1 memory_bytes=2 scope=compositor',
            'K230_CARD_BENCH v=1 run=selected event=incomplete reason=input-overflow',
            'K230_PIXMAN_OUTPUT_TURN src=1080x1920 dst=1920x1080 format=0x34325258 rotation=1 rotation_cpu_ns=1234 scratch_bytes=0',
            'K230_PIXMAN_OUTPUT_TURN src=bad dst=bad format=secret rotation=1 rotation_cpu_ns=1 scratch_bytes=0'])
        rows, _, run, error = allowlisted_records(raw,'selected',0,20)
        self.assertEqual(run,'selected')
        self.assertEqual(error,'input-overflow')
        self.assertEqual(sum(row.startswith('K230_PIXMAN_OUTPUT_TURN ') for row in rows),1)
        self.assertNotIn('secret','\n'.join(rows))
        _, _, _, unknown = allowlisted_records(
            'K230_CARD_BENCH v=1 run=selected event=error reason=unrecognized-private-text',
            'selected',0,20)
        self.assertEqual(unknown,'benchmark-error')

    def test_sanitizer_ignores_arbitrary_text_and_pixman_unscoped(self):
        rows, _, _, _ = allowlisted_records('password=secret K230_CARD_BENCH junk\nK230_PIXMAN_DRAW transform=90 path=fast copy_cpu_ns=1 total_cpu_ns=2 dst_pixels=3 scratch_bytes=0', 'x',0,3)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0].startswith('K230_PIXMAN_DRAW '))
        self.assertNotIn('secret','\n'.join(rows))

    def test_schema_exact(self):
        self.assertEqual(len(RUN_FIELDS),19)

    def test_stop_or_restore_failure_overrides_complete_trace(self):
        session={'event':'session'}
        self.assertEqual(outcome(None,'benchmark stop failed',None,session,24,24)[0],'INCOMPLETE')
        self.assertEqual(outcome(None,None,'output restore failed',session,24,24)[0],'INCOMPLETE')
        self.assertEqual(outcome(None,None,None,session,24,24),('CAPTURED',None))

    def test_fake_capture_and_cleanup_failure(self):
        class FakeIPC:
            instances=[]
            def __init__(self):
                self.commands=[]; self.fail_stop=False; self.closed=False; self.pid=123
                FakeIPC.instances.append(self)
            def outputs(self):
                return [{'name':'HDMI-A-1','active':True,'transform':'90','scale':1,
                    'current_mode':{'width':1920,'height':1080,'refresh':60000},
                    'rect':{'x':0,'y':0,'width':1080,'height':1920}}]
            def tree(self):
                return {'nodes':[{'app_id':'foot','window_properties':{'class':'foot'}}]}
            def command(self, command):
                self.commands.append(command)
                if self.fail_stop and command == 'card_shell benchmark-stop':
                    raise CaptureError('fixture stop failure')
            def close(self): self.closed=True

        def run_fixture(directory, fail_stop=False, overflow=False):
            FakeIPC.instances.clear()
            run='fixture_run'
            calls=[]
            def fake_journal(_since, _timeout=8):
                calls.append(1)
                t=time.monotonic_ns()
                rows=[f'K230_CARD_BENCH v=1 run={run} event=resource t_ns={t} clock=monotonic phase=baseline cpu_ns=1 memory_bytes=2 scope=compositor',
                      f'K230_CARD_BENCH v=1 run={run} event=session t_ns={t+1} clock=monotonic backend=drm renderer=pixman width=1080 height=1920 output_format=ARGB8888 input=injected cards=1']
                for input_id,kind in ((1,'motion'),(2,'release')):
                    stamp=t+input_id*100
                    frame=input_id+10
                    rows.extend([
                        f'K230_CARD_BENCH v=1 run={run} event=input input_id={input_id} gesture_id=1 kind={kind} source=injected t_ns={stamp}',
                        f'K230_CARD_BENCH v=1 run={run} event=submit input_id={input_id} frame_id={frame} t_ns={stamp+1} update_cpu_ns=1 final={int(kind=="release")}',
                        f'K230_CARD_BENCH v=1 run={run} event=present frame_id={frame} t_ns={stamp+2} presented=1 clock=monotonic',
                        f'K230_CARD_SHELL repaint-cost run={run} frame_id={frame} render_cpu_ns=1 prepare_cpu_ns=1 build_cpu_ns=1 commit_cpu_ns=1 attempts=1 failed_attempts=0'])
                rows.append('K230_CARD_SHELL touch-route phase=before id=9 source_ms=1 dispatch_ms=2 x=500.000 y=1900.000 width=1080 height=1920 edge=24 bottom_reserved=120 consumed=0 active=0 mode=0 ui=0 lock=0 launcher=0 drawer=0 popup=0 points=1 pointer=0 contact=0 edge_tracking=0 blocked=0 home=0')
                rows.append('Foot title=private secret')
                if overflow:
                    rows.append(f'K230_CARD_BENCH v=1 run={run} event=incomplete reason=input-overflow')
                return '\n'.join(rows if len(calls)>1 else rows[:1])
            args=argparse.Namespace(input='injected',operator_confirmed_contacts=False,output=directory,
                variant='candidate',source_revision='a'*40,seconds=5,drags=1)
            with mock.patch(__name__+'.IPC',FakeIPC), \
                 mock.patch(__name__+'.runtime_identity',return_value={'compositor_executable':'sway sha256:x','pixman_identity':'pixman sha256:y','environment':{'WLR_PIXMAN_QUARTER_TURN':'1','WLR_PIXMAN_OUTPUT_TURN':''}}), \
                 mock.patch(__name__+'.journal',side_effect=fake_journal), \
                 mock.patch('subprocess.run',return_value=subprocess.CompletedProcess(['uname'],0,'fixture-kernel\n','')):
                FakeIPC.instances.append  # keep fixture object accessible after patched capture
                code=capture(args)
            return code, json.loads((directory/'metadata.json').read_text()), json.loads((directory/'context.json').read_text()), FakeIPC.instances

        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'good'
            code,meta,context,instances=run_fixture(directory,False)
            self.assertEqual(code,0,context)
            self.assertEqual(set(meta['runs'][0]),RUN_FIELDS)
            self.assertEqual(meta['runs'][0]['drag_count'],1)
            self.assertEqual(meta['runs'][0]['log'],'capture.log')
            self.assertTrue(any('down 1 440 960' in cmd for cmd in instances[0].commands))
            self.assertTrue(instances[0].closed)
            import importlib.util
            parser_path=Path(__file__).with_name('hdmi-shell-performance.py')
            spec=importlib.util.spec_from_file_location('hdmi_shell_performance',parser_path)
            parser_module=importlib.util.module_from_spec(spec); spec.loader.exec_module(parser_module)
            parser_module.validate_run_metadata(dict(meta['runs'][0]),directory,'candidate')
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'stop-fails'
            # Inject a failure on the fake IPC only after initialization.
            original=FakeIPC.command
            def failing_stop(self, command):
                if command == 'card_shell benchmark-stop':
                    raise CaptureError('fixture stop failure')
                return original(self,command)
            with mock.patch.object(FakeIPC,'command',failing_stop):
                code,meta,context,instances=run_fixture(directory,True)
            self.assertEqual(code,1)
            self.assertEqual(meta['runs'],[])
            self.assertEqual(context['status'],'INCOMPLETE')
            self.assertIn('fixture stop failure',context['reason'])
            safe_log=(directory/'capture.log').read_text()
            self.assertIn('K230_CARD_SHELL touch-route',safe_log)
            self.assertNotIn('secret',safe_log)
            self.assertNotIn('private',safe_log)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'overflow'
            code,meta,context,instances=run_fixture(directory,False,overflow=True)
            self.assertEqual(code,1)
            self.assertEqual(meta['runs'],[])
            self.assertEqual(context['status'],'INCOMPLETE')
            self.assertEqual(context['reason'],'input-overflow')
            safe_log=(directory/'capture.log').read_text()
            self.assertIn('K230_CARD_BENCH v=1',safe_log)
            self.assertIn('K230_CARD_SHELL touch-route',safe_log)
            self.assertNotIn('secret',safe_log)


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--variant',choices=('baseline','candidate'))
    p.add_argument('--input',choices=('injected','physical'))
    p.add_argument('--seconds',type=int,default=60)
    p.add_argument('--drags',type=int,default=24)
    p.add_argument('--source-revision')
    p.add_argument('--output',type=Path)
    p.add_argument('--operator-confirmed-contacts',action='store_true')
    return p


def main(argv=None):
    p=parser(); a=p.parse_args(argv)
    if a.self_test:
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures)).wasSuccessful() else 1
    if a.variant is None or a.input is None or a.output is None or not a.source_revision:
        p.error('capture needs --variant, --input, --output and --source-revision')
    if not 1 <= a.seconds <= 300 or not 1 <= a.drags <= 48:
        p.error('--seconds must be 1..300 and --drags 1..48')
    if not re.fullmatch('[0-9a-fA-F]{40}', a.source_revision):
        p.error('--source-revision must be 40 hexadecimal characters')
    try:
        return capture(a)
    except (CaptureError,OSError,subprocess.SubprocessError) as error:
        print(f'capture-board: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
