#!/usr/bin/env python3
"""Strictly compare committed portrait HDMI compositor traces.

Comparison input is a directory containing ``metadata.json`` and the log
files named by its run records. See ``--self-test`` for the accepted grammar.
This host-only tool does not capture from, identify, or control a board.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import unittest

SCHEMA = 'hdmi-shell-performance-v1'
BENCH_PREFIX = 'K230_CARD_BENCH '
SHELL_PREFIX = 'K230_CARD_SHELL '
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250_000
MAX_COUNTER = 2**63 - 1
FRAME_BUDGET_MS = 33.3
LATENCY_BUDGET_MS = 100.0
MIN_DRAGS = 24
RUN_FIELDS = {
    'run', 'source_revision', 'compositor_executable', 'pixman_identity',
    'kernel', 'logical_width', 'logical_height', 'physical_width',
    'physical_height', 'transform', 'scale', 'format', 'cards',
    'input_class', 'operator_confirmed_contacts', 'variant', 'drag_count',
    'clock', 'log',
}
EVENT_FIELDS = {
    'session': {'v', 'run', 'event', 't_ns', 'clock', 'backend', 'renderer',
                'width', 'height', 'output_format', 'input', 'cards'},
    'input': {'v', 'run', 'event', 'input_id', 'gesture_id', 'kind', 'source', 't_ns'},
    'submit': {'v', 'run', 'event', 'input_id', 'frame_id', 't_ns', 'update_cpu_ns', 'final'},
    'present': {'v', 'run', 'event', 'frame_id', 't_ns', 'presented', 'clock'},
    'resource': {'v', 'run', 'event', 'phase', 't_ns', 'cpu_ns', 'memory_bytes', 'scope'},
}
NUMERIC_FIELDS = {'v', 't_ns', 'width', 'height', 'cards', 'input_id', 'gesture_id',
                  'frame_id', 'update_cpu_ns', 'final', 'presented', 'cpu_ns', 'memory_bytes'}


class InvalidTrace(ValueError):
    pass


def checked_int(value, name):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise InvalidTrace(f'invalid integer field: {name}')
    value = int(value)
    if value > MAX_COUNTER:
        raise InvalidTrace(f'counter outside range: {name}')
    return value


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def parse_log(raw, expected_run):
    if len(raw) > MAX_BYTES:
        raise InvalidTrace('trace log exceeds bounded input size')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise InvalidTrace('trace log is not UTF-8') from error
    rows = []
    origins = {}
    costs = {}
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 8192:
            raise InvalidTrace(f'line {number}: record exceeds size bound')
        if BENCH_PREFIX in line:
            payload = line.split(BENCH_PREFIX, 1)[1]
            pairs = payload.split()
            if any('=' not in pair for pair in pairs):
                raise InvalidTrace(f'line {number}: malformed benchmark row')
            row = {}
            for pair in pairs:
                key, value = pair.split('=', 1)
                if key in row:
                    raise InvalidTrace(f'line {number}: duplicate benchmark field')
                row[key] = value
            event = row.get('event')
            if event not in EVENT_FIELDS:
                raise InvalidTrace(f'line {number}: unknown benchmark event')
            if set(row) != EVENT_FIELDS[event]:
                raise InvalidTrace(f'line {number}: wrong field set for {event}')
            for key in NUMERIC_FIELDS:
                if key in row:
                    row[key] = checked_int(row[key], key)
            if row['v'] != 1:
                raise InvalidTrace(f'line {number}: unsupported benchmark version')
            if row['run'] != expected_run:
                raise InvalidTrace('mixed run identity in trace log')
            if event == 'session':
                if row['clock'] != 'monotonic' or row['backend'] != 'drm':
                    raise InvalidTrace('comparison needs monotonic DRM session telemetry')
                if not re.fullmatch(r'RGB565|XRGB8888|ARGB8888|0x[0-9a-fA-F]{1,8}|[0-9]{1,10}', row['output_format']):
                    raise InvalidTrace('invalid session output format')
            elif event == 'input':
                if row['kind'] not in ('motion', 'release') or row['source'] not in ('physical', 'injected'):
                    raise InvalidTrace('unsupported input kind or source')
            elif event == 'present':
                if row['presented'] not in (0, 1) or row['clock'] != 'monotonic':
                    raise InvalidTrace('invalid presentation state or clock')
            elif event == 'submit' and row['final'] not in (0, 1):
                raise InvalidTrace('invalid final-submit flag')
            elif event == 'resource' and (row['phase'] not in ('baseline', 'active', 'restored') or
                                          row['scope'] not in ('compositor', 'session')):
                raise InvalidTrace('invalid resource sample phase or scope')
            rows.append(row)
        elif SHELL_PREFIX in line:
            payload = line.split(SHELL_PREFIX, 1)[1]
            pairs = payload.split()
            if not pairs:
                continue
            kind, *fields = pairs
            parsed = {}
            for pair in fields:
                if '=' not in pair:
                    raise InvalidTrace(f'line {number}: malformed shell diagnostic')
                key, value = pair.split('=', 1)
                if key in parsed:
                    raise InvalidTrace(f'line {number}: duplicate shell diagnostic field')
                parsed[key] = value
            if kind == 'input-origin':
                if parsed.get('run') != expected_run:
                    raise InvalidTrace('mixed run identity in shell diagnostics')
                if set(parsed) != {'run', 'input_id', 'source_ns'}:
                    raise InvalidTrace(f'line {number}: wrong input-origin field set')
                input_id = checked_int(parsed['input_id'], 'input_id')
                if input_id in origins:
                    raise InvalidTrace('duplicate input-origin record')
                origins[input_id] = checked_int(parsed['source_ns'], 'source_ns')
            elif kind == 'repaint-cost':
                if parsed.get('run') != expected_run:
                    raise InvalidTrace('mixed run identity in shell diagnostics')
                if set(parsed) != {'run', 'frame_id', 'render_cpu_ns', 'prepare_cpu_ns',
                                   'build_cpu_ns', 'commit_cpu_ns', 'attempts', 'failed_attempts'}:
                    raise InvalidTrace(f'line {number}: wrong repaint-cost field set')
                frame_id = checked_int(parsed['frame_id'], 'frame_id')
                if frame_id in costs:
                    raise InvalidTrace('duplicate repaint-cost frame')
                costs[frame_id] = checked_int(parsed['build_cpu_ns'], 'build_cpu_ns')
    if len(rows) > MAX_ROWS:
        raise InvalidTrace('trace exceeds record limit')
    if not rows:
        raise InvalidTrace('no benchmark telemetry found')
    return rows, origins, costs


def validate_run_metadata(item, directory, expected_variant):
    if not isinstance(item, dict) or set(item) != RUN_FIELDS:
        raise InvalidTrace('run metadata has missing or unsupported fields')
    if item['variant'] != expected_variant:
        raise InvalidTrace('metadata variant does not match comparison side')
    if item['input_class'] not in ('injected', 'physical'):
        raise InvalidTrace('input_class must be injected or physical')
    if type(item['operator_confirmed_contacts']) is not bool:
        raise InvalidTrace('operator_confirmed_contacts must be boolean')
    if item['input_class'] == 'injected' and item['operator_confirmed_contacts']:
        raise InvalidTrace('injected run cannot claim operator-confirmed contacts')
    if item['clock'] != 'monotonic':
        raise InvalidTrace('metadata clock must be monotonic')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(item['run'])):
        raise InvalidTrace('invalid run identifier')
    if not re.fullmatch(r'[0-9a-fA-F]{7,40}', str(item['source_revision'])):
        raise InvalidTrace('invalid source revision')
    for key in ('compositor_executable', 'pixman_identity', 'kernel', 'format'):
        if not isinstance(item[key], str) or not item[key] or len(item[key]) > 512:
            raise InvalidTrace(f'invalid runtime metadata field: {key}')
    if not isinstance(item['log'], str) or Path(item['log']).name != item['log'] or item['log'] in ('.', '..'):
        raise InvalidTrace('log must be a simple file name inside the trace directory')
    positive = ('logical_width', 'logical_height', 'physical_width', 'physical_height', 'cards', 'drag_count')
    for key in positive:
        value = checked_int(item[key], key)
        if value == 0:
            raise InvalidTrace(f'{key} must be positive')
        item[key] = value
    if checked_int(item['transform'], 'transform') not in (0, 90, 180, 270):
        raise InvalidTrace('transform must be a right-angle rotation')
    try:
        scale = float(item['scale'])
    except (TypeError, ValueError) as error:
        raise InvalidTrace('scale must be positive numeric') from error
    if not math.isfinite(scale) or scale <= 0:
        raise InvalidTrace('scale must be positive numeric')
    if (item['physical_width'], item['physical_height'], item['transform']) != (1920, 1080, 90):
        raise InvalidTrace('comparison requires physical 1920x1080 transform 90')
    if (item['logical_width'], item['logical_height']) != (1080, 1920):
        raise InvalidTrace('comparison requires logical portrait 1080x1920')
    if item['cards'] not in (1, 2):
        raise InvalidTrace('comparison workload cards must be one or two')
    if item['input_class'] == 'physical' and not item['operator_confirmed_contacts']:
        raise InvalidTrace('physical label alone is not operator-confirmed contact evidence')
    log_path = directory / item['log']
    try:
        raw = log_path.read_bytes()
    except OSError as error:
        raise InvalidTrace('trace log is missing or unreadable') from error
    rows, origins, costs = parse_log(raw, item['run'])
    sessions = [row for row in rows if row['event'] == 'session']
    if len(sessions) != 1:
        raise InvalidTrace('each run needs exactly one session record')
    session = sessions[0]
    expected_format = item['format']
    if session['output_format'] != expected_format:
        raise InvalidTrace('metadata and session format disagree')
    if session['renderer'] != 'pixman' or session['width'] != item['logical_width'] or session['height'] != item['logical_height']:
        raise InvalidTrace('metadata and session renderer or geometry disagree')
    if session['cards'] != item['cards'] or session['input'] != item['input_class']:
        raise InvalidTrace('metadata and session workload or input label disagree')
    inputs = {}
    for row in rows:
        if row['event'] == 'input':
            if row['input_id'] == 0 or row['gesture_id'] == 0:
                raise InvalidTrace('input and gesture identifiers must be positive')
            if row['input_id'] in inputs:
                raise InvalidTrace('duplicate input identifier')
            if row['source'] != item['input_class']:
                raise InvalidTrace('mixed physical/injected labels in run')
            inputs[row['input_id']] = row
    submits = defaultdict(list)
    presents = {}
    for row in rows:
        if row['event'] == 'submit':
            if row['input_id'] not in inputs:
                raise InvalidTrace('submission has no matching input')
            if row['t_ns'] < inputs[row['input_id']]['t_ns']:
                raise InvalidTrace('submission precedes input dispatch')
            submits[row['input_id']].append(row)
        elif row['event'] == 'present':
            if row['frame_id'] in presents:
                raise InvalidTrace('duplicate frame presentation')
            presents[row['frame_id']] = row
    if not inputs:
        raise InvalidTrace('run has no input samples')
    if set(inputs) - set(origins) and item['input_class'] == 'physical':
        raise InvalidTrace('physical latency lacks kernel input-origin timestamps')
    if origins and set(origins) - set(inputs):
        raise InvalidTrace('input-origin record has no matching input')
    latencies = []
    gestures = defaultdict(set)
    gesture_rows = defaultdict(list)
    covered_frames = set()
    ordered_inputs = sorted(inputs.values(), key=lambda row: row['input_id'])
    if any(a['t_ns'] > b['t_ns'] for a, b in zip(ordered_inputs, ordered_inputs[1:])):
        raise InvalidTrace('input timestamps regress')
    for input_id, input_row in inputs.items():
        mapped = submits.get(input_id, [])
        if len(mapped) != 1:
            raise InvalidTrace('each accepted input must map to exactly one frame')
        submit = mapped[0]
        present = presents.get(submit['frame_id'])
        if present is None or present['presented'] != 1:
            raise InvalidTrace('missing successful presentation coverage for submitted frame')
        if present['clock'] != item['clock'] or present['t_ns'] < submit['t_ns']:
            raise InvalidTrace('presentation clock mismatch or timestamp regression')
        if submit['frame_id'] not in costs:
            raise InvalidTrace('submitted frame is missing repaint-cost build CPU')
        covered_frames.add(submit['frame_id'])
        source_time = origins.get(input_id, input_row['t_ns']) if item['input_class'] == 'physical' else input_row['t_ns']
        if source_time > input_row['t_ns'] or source_time > present['t_ns']:
            raise InvalidTrace('input-origin timestamp is after dispatch or presentation')
        latencies.append((present['t_ns'] - source_time) / 1e6)
        gestures[input_row['gesture_id']].add(input_row['kind'])
        gesture_rows[input_row['gesture_id']].append(input_row)
    if not covered_frames <= set(costs):
        raise InvalidTrace('input-correlated frame is missing repaint-cost build CPU')
    if not set(costs) <= set(presents):
        raise InvalidTrace('repaint-cost frame is missing presentation coverage')
    drag_count = 0
    for gesture_id, entries in gesture_rows.items():
        entries.sort(key=lambda row: (row['t_ns'], row['input_id']))
        kinds = [row['kind'] for row in entries]
        if kinds.count('release') > 1 or ('release' in kinds and kinds[-1] != 'release'):
            raise InvalidTrace('gesture release is duplicated or does not end its sequence')
        if 'release' in kinds and 'motion' in kinds:
            drag_count += 1
    if item['drag_count'] != drag_count:
        raise InvalidTrace('metadata drag_count disagrees with complete input gestures')
    if not costs or not latencies:
        raise InvalidTrace('run has no complete frame or latency samples')
    return {
        'run': item['run'], 'variant': item['variant'], 'source_revision': item['source_revision'],
        'runtime_identity': {'compositor_executable': item['compositor_executable'],
                             'pixman_identity': item['pixman_identity'], 'kernel': item['kernel']},
        'physical_geometry': [item['physical_width'], item['physical_height']],
        'logical_geometry': [item['logical_width'], item['logical_height']],
        'transform': item['transform'], 'scale': scale, 'format': item['format'],
        'cards': item['cards'], 'input_class': item['input_class'],
        'operator_confirmed_contacts': item['operator_confirmed_contacts'],
        'drag_count': drag_count, 'build_cpu_ms': _metric([value / 1e6 for value in costs.values()]),
        'input_to_present_ms': _metric(latencies),
        'latency_clock_start': 'kernel-input-origin' if item['input_class'] == 'physical' else 'compositor-dispatch',
        'physical_label_proves_real_finger': False,
    }


def _metric(values):
    return {'sample_count': len(values), 'p95_ms': percentile(values, .95), 'max_ms': max(values)}


def load_side(directory, variant):
    path = directory / 'metadata.json'
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidTrace('metadata.json is missing, unreadable, or invalid JSON') from error
    if not isinstance(manifest, dict) or set(manifest) != {'schema', 'runs'} or manifest['schema'] != SCHEMA:
        raise InvalidTrace('unsupported trace metadata schema')
    if not isinstance(manifest['runs'], list) or not manifest['runs']:
        raise InvalidTrace('metadata must contain a non-empty runs list')
    runs = [validate_run_metadata(dict(item), directory, variant) for item in manifest['runs']]
    ids = [run['run'] for run in runs]
    if len(ids) != len(set(ids)):
        raise InvalidTrace('duplicate run identity in metadata')
    runtimes = {json.dumps({'source_revision': run['source_revision'], **run['runtime_identity']}, sort_keys=True)
                for run in runs}
    if len(runtimes) != 1:
        raise InvalidTrace('mixed runtime identity within comparison side')
    workload_keys = [(run['cards'], run['format']) for run in runs]
    if len(workload_keys) != len(set(workload_keys)):
        raise InvalidTrace('duplicate workload within comparison side')
    return runs


def compare(baseline_dir, candidate_dir):
    baseline = load_side(baseline_dir, 'baseline')
    candidate = load_side(candidate_dir, 'candidate')
    bmap = {(r['cards'], r['format']): r for r in baseline}
    cmap = {(r['cards'], r['format']): r for r in candidate}
    if set(bmap) != set(cmap):
        raise InvalidTrace('baseline and candidate workload, card count, or format sets differ')
    comparisons = []
    for key in sorted(bmap):
        before, after = bmap[key], cmap[key]
        for field in ('physical_geometry', 'logical_geometry', 'transform', 'scale', 'input_class'):
            if before[field] != after[field]:
                raise InvalidTrace(f'baseline and candidate {field} differ')
        drag_gate = 'PASS' if min(before['drag_count'], after['drag_count']) >= MIN_DRAGS else 'INCOMPLETE'
        build_gate = 'PASS' if after['build_cpu_ms']['p95_ms'] <= FRAME_BUDGET_MS else 'FAIL'
        if after['input_class'] != 'physical' or not after['operator_confirmed_contacts']:
            latency_gate = 'INCOMPLETE'
        else:
            latency_gate = ('PASS' if after['input_to_present_ms']['p95_ms'] <= LATENCY_BUDGET_MS else 'FAIL')
        comparisons.append({
            'cards': key[0], 'format': key[1], 'baseline': before, 'candidate': after,
            'gates': {'minimum_24_drags': drag_gate, 'candidate_p95_build_cpu_le_33_3ms': build_gate,
                      'candidate_physical_contact_to_present_p95_le_100ms': latency_gate},
        })
    gate_states = [state for row in comparisons for state in row['gates'].values()]
    status = 'FAIL' if 'FAIL' in gate_states else 'PASS' if gate_states and all(state == 'PASS' for state in gate_states) else 'INCOMPLETE'
    return {'schema': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(), 'status': status,
            'limits': ['A physical label and operator contact attestation do not authenticate a real finger or prove optical visibility.',
                       'Injected latency starts at compositor dispatch and cannot satisfy the physical contact-to-present gate.',
                       'Presentation feedback is not an optical measurement.'],
            'comparisons': comparisons}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--compare', action='store_true')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--candidate', type=Path)
    # Root will implement these modes in the owning integration branch.
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--check-scene', action='store_true')
    parser.add_argument('--variant', choices=('baseline', 'candidate'))
    parser.add_argument('--input', choices=('injected', 'physical'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.self_test:
        if any((args.compare, args.capture, args.check_scene, args.baseline, args.candidate, args.output)):
            parser.error('--self-test cannot be combined with other modes or output')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TraceTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if args.capture or args.check_scene:
        print('hdmi-shell-performance: this mode is not implemented in the host trace-parser change', file=sys.stderr)
        return 2
    if not args.compare or not args.baseline or not args.candidate:
        parser.error('--compare requires --baseline and --candidate directories')
    try:
        report = compare(args.baseline, args.candidate)
    except (InvalidTrace, OSError) as error:
        print(f'hdmi-shell-performance: {error}', file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end='')
    return 0 if report['status'] == 'PASS' else 1


def fixture_run(run, variant, cards=1, input_class='injected', runtime='sha-a'):
    start = 1_000_000_000
    rows = [dict(v=1, run=run, event='session', t_ns=start, clock='monotonic', backend='drm',
                 renderer='pixman', width=1080, height=1920, output_format='ARGB8888',
                 input=input_class, cards=cards)]
    origins = []
    costs = []
    for drag in range(MIN_DRAGS):
        gesture = drag + 1
        for step, kind in enumerate(('motion', 'motion', 'release')):
            input_id = drag * 3 + step + 1
            frame_id = input_id + 100
            t = start + input_id * 20_000_000
            rows.append(dict(v=1, run=run, event='input', input_id=input_id,
                             gesture_id=gesture, kind=kind, source=input_class, t_ns=t))
            rows.append(dict(v=1, run=run, event='submit', input_id=input_id, frame_id=frame_id,
                             t_ns=t + 2_000_000, update_cpu_ns=3_000_000, final=int(kind == 'release')))
            rows.append(dict(v=1, run=run, event='present', frame_id=frame_id, t_ns=t + 10_000_000,
                             presented=1, clock='monotonic'))
            costs.append(f'K230_CARD_SHELL repaint-cost run={run} frame_id={frame_id} render_cpu_ns=3000000 prepare_cpu_ns=1000 build_cpu_ns=3000000 commit_cpu_ns=1000 attempts=1 failed_attempts=0')
            if input_class == 'physical':
                origins.append(f'K230_CARD_SHELL input-origin run={run} input_id={input_id} source_ns={t - 1000000}')
    log_lines = [f'K230_CARD_BENCH v=1 run={r["run"]} event={r["event"]} ' + ' '.join(f'{k}={v}' for k, v in r.items() if k not in ('v', 'run', 'event')) for r in rows]
    metadata = {
        'run': run, 'source_revision': 'a' * 40, 'compositor_executable': '/nix/store/aaa-wlroots',
        'pixman_identity': 'pixman-0.44.0', 'kernel': runtime, 'logical_width': 1080,
        'logical_height': 1920, 'physical_width': 1920, 'physical_height': 1080,
        'transform': 90, 'scale': 1, 'format': 'ARGB8888', 'cards': cards,
        'input_class': input_class, 'operator_confirmed_contacts': input_class == 'physical',
        'variant': variant, 'drag_count': MIN_DRAGS, 'clock': 'monotonic', 'log': f'{run}.log',
    }
    return metadata, ('\n'.join(log_lines + origins + costs) + '\n').encode()


class TraceTests(unittest.TestCase):
    def make_side(self, directory, variant, input_class='injected', runtime='sha-a', cards=(1, 2)):
        runs = []
        for ix, card_count in enumerate(cards):
            item, raw = fixture_run(f'{variant}{ix}', variant, card_count, input_class, runtime)
            runs.append(item)
            (directory / item['log']).write_bytes(raw)
        (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': runs}))

    def test_compare_reports_metrics_and_injected_cannot_pass_physical_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'baseline'; cand = Path(temp) / 'candidate'
            base.mkdir(); cand.mkdir()
            self.make_side(base, 'baseline')
            self.make_side(cand, 'candidate')
            report = compare(base, cand)
            self.assertEqual(report['status'], 'INCOMPLETE')
            row = report['comparisons'][0]
            self.assertEqual(row['candidate']['build_cpu_ms']['p95_ms'], 3)
            self.assertEqual(row['candidate']['input_to_present_ms']['p95_ms'], 10)
            self.assertEqual(row['candidate']['drag_count'], 24)
            self.assertEqual(row['gates']['candidate_physical_contact_to_present_p95_le_100ms'], 'INCOMPLETE')
            self.assertEqual(row['candidate']['physical_label_proves_real_finger'], False)

    def test_physical_origin_measurement_does_not_claim_real_finger(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'baseline'; cand = Path(temp) / 'candidate'
            base.mkdir(); cand.mkdir()
            self.make_side(base, 'baseline', 'physical')
            self.make_side(cand, 'candidate', 'physical')
            report = compare(base, cand)
            self.assertEqual(report['comparisons'][0]['gates']['candidate_physical_contact_to_present_p95_le_100ms'], 'PASS')
            self.assertFalse(report['comparisons'][0]['candidate']['physical_label_proves_real_finger'])

    def test_candidate_frame_budget_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'baseline'; cand = Path(temp) / 'candidate'
            base.mkdir(); cand.mkdir()
            self.make_side(base, 'baseline')
            self.make_side(cand, 'candidate')
            manifest_path = cand / 'metadata.json'
            manifest = json.loads(manifest_path.read_text())
            log_path = cand / manifest['runs'][0]['log']
            log_path.write_bytes(log_path.read_bytes().replace(b'build_cpu_ns=3000000', b'build_cpu_ns=40000000'))
            report = compare(base, cand)
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['comparisons'][0]['gates']['candidate_p95_build_cpu_le_33_3ms'], 'FAIL')

    def test_missing_present_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            item, raw = fixture_run('run1', 'candidate')
            raw = b'\n'.join(line for line in raw.splitlines() if b'event=present' not in line)
            (directory / item['log']).write_bytes(raw)
            (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
            with self.assertRaisesRegex(InvalidTrace, 'missing successful presentation'):
                load_side(directory, 'candidate')

    def test_missing_frame_build_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            item, raw = fixture_run('run1', 'candidate')
            raw = b'\n'.join(line for line in raw.splitlines() if b'repaint-cost' not in line)
            (directory / item['log']).write_bytes(raw)
            (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
            with self.assertRaisesRegex(InvalidTrace, 'missing repaint-cost'):
                load_side(directory, 'candidate')

    def test_mixed_run_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            item, raw = fixture_run('run1', 'candidate')
            (directory / item['log']).write_bytes(raw + raw.replace(b'run1', b'run2'))
            (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
            with self.assertRaisesRegex(InvalidTrace, 'mixed run identity'):
                load_side(directory, 'candidate')

    def test_mixed_runtime_identity_and_input_labels_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.make_side(directory, 'candidate', runtime='kernel-a')
            manifest_path = directory / 'metadata.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['runs'][1]['kernel'] = 'kernel-b'
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(InvalidTrace, 'mixed runtime identity'):
                load_side(directory, 'candidate')
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            item, raw = fixture_run('run1', 'candidate')
            raw = raw.replace(b'source=injected', b'source=physical')
            (directory / item['log']).write_bytes(raw)
            (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
            with self.assertRaisesRegex(InvalidTrace, 'mixed physical/injected'):
                load_side(directory, 'candidate')

    def test_physical_label_requires_origin_and_operator_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            item, raw = fixture_run('run1', 'candidate', input_class='physical')
            raw = b'\n'.join(line for line in raw.splitlines() if b'input-origin' not in line)
            (directory / item['log']).write_bytes(raw)
            (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
            with self.assertRaisesRegex(InvalidTrace, 'kernel input-origin'):
                load_side(directory, 'candidate')
            manifest = json.loads((directory / 'metadata.json').read_text())
            manifest['runs'][0]['operator_confirmed_contacts'] = False
            (directory / 'metadata.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(InvalidTrace, 'operator-confirmed'):
                load_side(directory, 'candidate')

    def test_unsupported_capture_modes_fail_explicitly(self):
        self.assertEqual(main(['--capture', '--variant', 'baseline', '--output', '/tmp/unused']), 2)


if __name__ == '__main__':
    raise SystemExit(main())
