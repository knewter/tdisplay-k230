#!/usr/bin/env python3
"""Analyze correlated card-shell telemetry; missing evidence never passes a gate.

Consumes source-emitted K230_CARD_BENCH rows or JSON objects with the same fields.
--board validates operator provenance; it never opens a board or synthesizes data.
"""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import unittest

SCHEMA = 'card-shell-benchmark-v1'
PREFIX = 'K230_CARD_BENCH '
# Frozen before board acceptance; rationale and exact measurement boundaries are
# in docs/research/card-shell-benchmark.md. All thresholds are inclusive.
BUDGETS = {
    'frame_update_cpu_ms': {'p95': 16.667, 'max': 33.334},
    'motion_to_submit_ms': {'p95': 50.0, 'max': 100.0},
    'motion_to_present_ms': {'p95': 66.667, 'max': 133.334},
    'tracking_present_interval_ms': {'p95': 33.334, 'max': 100.0},
    'release_to_final_submit_ms': {'max': 200.0},
    'release_to_present_ms': {'max': 266.667},
    'incremental_session_memory_bytes': {'max': 64 * 1024 * 1024},
}
MIN_MOTION = 60
MIN_INTERVALS = 30
MIN_RELEASE = 3
MIN_RESOURCE_SAMPLES = 3
MIN_RESOURCE_SPAN_NS = 2_000_000_000
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250_000
MAX_COUNTER = 2**63 - 1
FIELDS = {
    'session': {'v', 'run', 'event', 't_ns', 'clock', 'backend', 'renderer',
                'width', 'height', 'output_format', 'input', 'cards'},
    'input': {'v', 'run', 'event', 'input_id', 'gesture_id', 'kind', 'source', 't_ns'},
    'submit': {'v', 'run', 'event', 'input_id', 'frame_id', 't_ns', 'update_cpu_ns', 'final'},
    'present': {'v', 'run', 'event', 'frame_id', 't_ns', 'presented', 'clock'},
    'resource': {'v', 'run', 'event', 'phase', 't_ns', 'cpu_ns', 'memory_bytes', 'scope'},
}
NUMERIC = {'v', 't_ns', 'width', 'height', 'cards', 'input_id', 'gesture_id',
           'frame_id', 'update_cpu_ns', 'final', 'presented', 'cpu_ns', 'memory_bytes'}
ENUMS = {'clock': {'monotonic'}, 'backend': {'drm', 'headless'},
         'renderer': {'pixman', 'vglite'}, 'input': {'physical', 'injected', 'host'},
         'source': {'physical', 'injected', 'host'}, 'kind': {'motion', 'release'},
         'phase': {'baseline', 'active', 'restored'}, 'scope': {'compositor', 'session'}}


class InvalidEvidence(ValueError):
    pass


def checked_int(value, field):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise InvalidEvidence(f'invalid integer field: {field}')
    value = int(value)
    if value > MAX_COUNTER:
        raise InvalidEvidence(f'counter outside range: {field}')
    return value


def parse_rows(raw):
    if len(raw) > MAX_BYTES:
        raise InvalidEvidence('telemetry exceeds bounded input size')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise InvalidEvidence('telemetry is not UTF-8') from error
    rows = []
    ignored = 0
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 8192:
            raise InvalidEvidence(f'line {number}: record exceeds size bound')
        if PREFIX in line:
            payload = line.split(PREFIX, 1)[1]
            pairs = payload.split()
            if any('=' not in pair for pair in pairs):
                raise InvalidEvidence(f'line {number}: malformed telemetry')
            row = {}
            for pair in pairs:
                key, value = pair.split('=', 1)
                if key in row:
                    raise InvalidEvidence(f'line {number}: duplicate field')
                row[key] = value
        elif line.startswith('{'):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                ignored += 1
                continue
            if not isinstance(row, dict) or row.get('event') not in FIELDS:
                ignored += 1
                continue
        else:
            ignored += 1
            continue
        event = row.get('event')
        if event not in FIELDS:
            raise InvalidEvidence(f'line {number}: unknown benchmark event')
        if set(row) != FIELDS[event]:
            # Report keys only through a constant message: input may carry secrets.
            raise InvalidEvidence(f'line {number}: wrong field set for {event}')
        for key, value in list(row.items()):
            if key in NUMERIC:
                row[key] = checked_int(value, key)
            elif key in ENUMS and (not isinstance(value, str) or value not in ENUMS[key]):
                raise InvalidEvidence(f'line {number}: unsupported {key}')
        if row['v'] != 1:
            raise InvalidEvidence(f'line {number}: unsupported telemetry version')
        row['run'] = str(row['run'])
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row['run']):
            raise InvalidEvidence(f'line {number}: invalid run identifier')
        if event == 'session':
            if not row['cards'] or not row['width'] or not row['height']:
                raise InvalidEvidence('invalid workload dimensions or card count')
            if not isinstance(row['output_format'], str) or not re.fullmatch(r'RGB565|XRGB8888|ARGB8888|0x[0-9a-fA-F]{1,8}', row['output_format']):
                raise InvalidEvidence('invalid output format')
        if event == 'submit' and row['final'] not in (0, 1):
            raise InvalidEvidence('invalid final-submit flag')
        if event == 'present' and row['presented'] not in (0, 1):
            raise InvalidEvidence('invalid presented flag')
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise InvalidEvidence('telemetry exceeds record limit')
    if not rows:
        raise InvalidEvidence('no correlated benchmark telemetry found')
    return rows, ignored


def percentile(values, fraction):
    """Nearest-rank percentile: deterministic, conservative at small samples."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def metric(values, budget=None, required=1):
    if not values:
        return {'status': 'INCOMPLETE', 'count': 0, 'budget': budget}
    stats = {'count': len(values), 'min': min(values), 'median': percentile(values, .5),
             'p95': percentile(values, .95), 'max': max(values), 'budget': budget}
    stats['status'] = ('FAIL' if budget and any(stats[key] > limit for key, limit in budget.items())
                       else 'INCOMPLETE' if len(values) < required else 'PASS')
    return stats


def unique(rows, key, label):
    out = {}
    for row in rows:
        value = row[key]
        if value in out:
            raise InvalidEvidence(f'duplicate {label}')
        out[value] = row
    return out


def analyze_run(run_id, rows):
    by_event = defaultdict(list)
    for row in rows:
        by_event[row['event']].append(row)
    if len(by_event['session']) != 1:
        raise InvalidEvidence('each run needs exactly one session record')
    session = by_event['session'][0]
    inputs = unique(by_event['input'], 'input_id', 'input identifier')
    mappings = defaultdict(list)
    seen_mappings = set()
    for row in by_event['submit']:
        key = (row['input_id'], row['frame_id'])
        if key in seen_mappings:
            raise InvalidEvidence('duplicate input-to-frame mapping')
        seen_mappings.add(key)
        mappings[row['input_id']].append(row)
    submissions = {}
    for input_id, entries in mappings.items():
        if input_id not in inputs:
            raise InvalidEvidence('submission has no matching input')
        entries.sort(key=lambda row: row['t_ns'])
        if inputs[input_id]['kind'] == 'motion' and len(entries) != 1:
            raise InvalidEvidence('motion input maps to more than one frame')
        finals = [row for row in entries if row['final']]
        if len(finals) > 1 or (finals and finals[0] is not entries[-1]):
            raise InvalidEvidence('release final submission is duplicated or followed by another mapping')
        submissions[input_id] = finals[0] if finals else entries[-1]
    presentations = unique(by_event['present'], 'frame_id', 'frame presentation')
    missing = []
    if any(row['source'] != session['input'] for row in inputs.values()):
        raise InvalidEvidence('mixed input provenance within a run')
    if any(row['t_ns'] < session['t_ns'] for row in inputs.values()):
        raise InvalidEvidence('input precedes session start')
    ordered_inputs = sorted(inputs.values(), key=lambda row: row['input_id'])
    if any(a['t_ns'] > b['t_ns'] for a, b in zip(ordered_inputs, ordered_inputs[1:])):
        raise InvalidEvidence('input timestamps regress')
    frames = {}
    frame_inputs = defaultdict(list)
    samples = defaultdict(list)
    unresolved = Counter()
    for submission in by_event['submit']:
        input_id = submission['input_id']
        entry = inputs[input_id]
        if submission['t_ns'] < entry['t_ns']:
            raise InvalidEvidence('submission precedes input')
        frame_id = submission['frame_id']
        signature = (submission['t_ns'], submission['update_cpu_ns'])
        if frame_id in frames and frames[frame_id] != signature:
            raise InvalidEvidence('coalesced frame rows disagree on frame cost or time')
        frames[frame_id] = signature
        frame_inputs[frame_id].append(entry)
    for frame_id, signature in frames.items():
        samples['frame_update_cpu_ms'].append(signature[1] / 1e6)
    for input_id, entry in inputs.items():
        kind = entry['kind']
        submission = submissions.get(input_id)
        if not submission:
            unresolved[f'{kind}_without_submit'] += 1
            continue
        if kind == 'release':
            first = mappings[input_id][0]
            samples['release_to_first_submit_ms'].append((first['t_ns']-entry['t_ns']) / 1e6)
            first_present = presentations.get(first['frame_id'])
            if first_present and first_present['presented']:
                if first_present['t_ns'] < first['t_ns']:
                    raise InvalidEvidence('presentation precedes initial release feedback')
                samples['release_to_first_present_ms'].append((first_present['t_ns']-entry['t_ns']) / 1e6)
        if kind == 'release' and not submission['final']:
            unresolved['release_without_final_submit'] += 1
            continue
        field = 'motion_to_submit_ms' if kind == 'motion' else 'release_to_final_submit_ms'
        samples[field].append((submission['t_ns'] - entry['t_ns']) / 1e6)
        presentation = presentations.get(submission['frame_id'])
        if not presentation or not presentation['presented']:
            unresolved[f'{kind}_without_present'] += 1
            continue
        if presentation['clock'] != session['clock']:
            raise InvalidEvidence('incompatible presentation clock')
        if presentation['t_ns'] < submission['t_ns']:
            raise InvalidEvidence('presentation precedes submission')
        field = 'motion_to_present_ms' if kind == 'motion' else 'release_to_present_ms'
        samples[field].append((presentation['t_ns'] - entry['t_ns']) / 1e6)
    # Actual presented frames per gesture, not one interval per coalesced input.
    # Input pauses above 50ms are excluded and disclosed, never counted as a stall.
    gestures = defaultdict(dict)
    for frame_id, entries in frame_inputs.items():
        presentation = presentations.get(frame_id)
        if not presentation or not presentation['presented']:
            continue
        for entry in entries:
            if entry['kind'] == 'motion':
                key = (entry['gesture_id'], frame_id)
                prior = gestures[key[0]].get(frame_id)
                if prior is None or prior['t_ns'] < entry['t_ns']:
                    gestures[key[0]][frame_id] = entry
    motion_times = defaultdict(list)
    for entry in inputs.values():
        if entry['kind'] == 'motion':
            motion_times[entry['gesture_id']].append(entry['t_ns'])
    for times in motion_times.values():
        times.sort()
    excluded_pauses = 0
    for gesture_id, gesture_frames in gestures.items():
        ordered = sorted(gesture_frames, key=lambda frame_id: frames[frame_id][0])
        for before, after in zip(ordered, ordered[1:]):
            input_gap = gesture_frames[after]['t_ns'] - gesture_frames[before]['t_ns']
            present_gap = presentations[after]['t_ns'] - presentations[before]['t_ns']
            if input_gap < 0 or present_gap < 0:
                raise InvalidEvidence('frame chronology regresses')
            times = motion_times[gesture_id]
            between = times[bisect_left(times, gesture_frames[before]['t_ns']):
                            bisect_right(times, gesture_frames[after]['t_ns'])]
            # Many coalesced events can bridge a stalled frame. Test each input
            # gap, not the overall gap between represented latest positions.
            if any(b-a > 50_000_000 for a, b in zip(between, between[1:])):
                excluded_pauses += 1
                continue
            samples['tracking_present_interval_ms'].append(present_gap / 1e6)
    metrics = {}
    for name, budget in BUDGETS.items():
        if name == 'incremental_session_memory_bytes':
            continue
        required = MIN_RELEASE if name.startswith('release_') else MIN_INTERVALS if name.startswith('tracking_') else MIN_MOTION
        metrics[name] = metric(samples[name], budget, required)
    for name in ('release_to_first_submit_ms', 'release_to_first_present_ms'):
        metrics[name] = metric(samples[name], required=MIN_RELEASE)
    resources = {}
    for scope in ('compositor', 'session'):
        phases = {}
        for phase in ('baseline', 'active', 'restored'):
            selected = sorted((r for r in by_event['resource'] if r['scope'] == scope and r['phase'] == phase),
                              key=lambda r: r['t_ns'])
            if len({r['t_ns'] for r in selected}) != len(selected):
                raise InvalidEvidence('duplicate resource timestamp')
            if any(a['cpu_ns'] > b['cpu_ns'] for a, b in zip(selected, selected[1:])):
                raise InvalidEvidence('resource CPU counter reset')
            span = selected[-1]['t_ns'] - selected[0]['t_ns'] if selected else 0
            adequate = len(selected) >= MIN_RESOURCE_SAMPLES and span >= MIN_RESOURCE_SPAN_NS
            phases[phase] = {'count': len(selected), 'span_ms': span / 1e6,
                             'status': 'PASS' if adequate else 'INCOMPLETE'}
            if selected:
                phases[phase].update(first_t_ns=selected[0]['t_ns'], last_t_ns=selected[-1]['t_ns'],
                                     first_cpu_ns=selected[0]['cpu_ns'], last_cpu_ns=selected[-1]['cpu_ns'],
                                     median_memory_bytes=percentile([r['memory_bytes'] for r in selected], .5),
                                     peak_memory_bytes=max(r['memory_bytes'] for r in selected),
                                     cpu_percent=100 * (selected[-1]['cpu_ns']-selected[0]['cpu_ns']) / span if span else None)
        ordered_phases = [phases[phase] for phase in ('baseline', 'active', 'restored')]
        for a, b in zip(ordered_phases, ordered_phases[1:]):
            if a['count'] and b['count'] and (a['last_t_ns'] >= b['first_t_ns'] or a['last_cpu_ns'] > b['first_cpu_ns']):
                raise InvalidEvidence('resource phases overlap or counters reset')
        if phases['baseline']['count'] and phases['baseline']['last_t_ns'] > session['t_ns']:
            raise InvalidEvidence('memory baseline follows deck entry')
        if phases['active']['count'] and phases['active']['first_t_ns'] < session['t_ns']:
            raise InvalidEvidence('active resource sample precedes deck entry')
        resources[scope] = phases
    phases = resources['session']
    if phases['baseline']['count'] and phases['active']['count']:
        growth = max(0, phases['active']['peak_memory_bytes'] - phases['baseline']['median_memory_bytes'])
        metrics['incremental_session_memory_bytes'] = metric([growth], BUDGETS['incremental_session_memory_bytes'])
        if any(row['status'] != 'PASS' for row in phases.values()):
            if metrics['incremental_session_memory_bytes']['status'] != 'FAIL':
                metrics['incremental_session_memory_bytes']['status'] = 'INCOMPLETE'
    else:
        metrics['incremental_session_memory_bytes'] = metric([], BUDGETS['incremental_session_memory_bytes'])
    if phases['baseline']['count'] and phases['restored']['count']:
        resources['restored_session_delta_bytes'] = phases['restored']['median_memory_bytes'] - phases['baseline']['median_memory_bytes']
    if unresolved:
        missing.append('Not every accepted input has a final matching submission and actual presentation.')
    if any(value['status'] == 'INCOMPLETE' for value in metrics.values()):
        missing.append('One or more metrics lack the required samples or resource phases.')
    if not frames:
        missing.append('No correlated frames were recorded; callback counters cannot replace them.')
    status = ('FAIL' if any(value['status'] == 'FAIL' for value in metrics.values()) else
              'INCOMPLETE' if missing else 'PASS')
    return {'run': run_id, 'session': session, 'status': status, 'metrics': metrics,
            'inputs': len(inputs), 'submitted_frames': len(frames),
            'submission_mappings': len(by_event['submit']),
            'coalesced_inputs': sum(max(0, len(entries)-1) for entries in frame_inputs.values()),
            'unresolved': dict(unresolved), 'excluded_input_pauses': excluded_pauses,
            'resources': resources, 'missing_evidence': missing}


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != 1:
        raise InvalidEvidence('board manifest schema is missing or unsupported')
    fixed = {'environment': 'board', 'board_model': 'LILYGO T-Display-K230',
             'ownership': 'coordinator-reserved'}
    for key, value in fixed.items():
        if manifest.get(key) != value:
            raise InvalidEvidence(f'board manifest requires {key}')
    if not isinstance(manifest.get('source_revision'), str) or not re.fullmatch(r'[0-9a-f]{40}', manifest['source_revision']):
        raise InvalidEvidence('board manifest requires a source revision')
    if not isinstance(manifest.get('package_store_path'), str) or not re.fullmatch(r'/nix/store/[0-9a-z]{32}-[A-Za-z0-9+._-]*card-shell[A-Za-z0-9+._-]*',
                        manifest['package_store_path']):
        raise InvalidEvidence('board manifest requires the installed card-shell store path')
    if manifest.get('evidence_class') not in ('board-injected', 'board-real-touch'):
        raise InvalidEvidence('board manifest requires an input evidence class')
    try:
        collected = datetime.fromisoformat(manifest.get('collected_at', '').replace('Z', '+00:00'))
        if collected.tzinfo is None:
            raise ValueError
    except (ValueError, TypeError) as error:
        raise InvalidEvidence('board manifest requires a timezone-aware collection timestamp') from error
    return {key: manifest[key] for key in (*fixed, 'schema', 'source_revision', 'package_store_path', 'evidence_class', 'collected_at')}


def analyze(raw, board=False, manifest=None, renderer='pixman'):
    rows, ignored = parse_rows(raw)
    groups = defaultdict(list)
    for row in rows:
        groups[row['run']].append(row)
    runs = [analyze_run(run_id, group) for run_id, group in groups.items()]
    issues = []
    provenance = validate_manifest(manifest) if board else {'environment': 'host', 'evidence_class': 'host-telemetry'}
    for run in runs:
        session = run['session']
        if session['renderer'] != renderer:
            issues.append('Observed renderer differs from the requested analysis renderer.')
        if board:
            if session['backend'] != 'drm' or (session['width'], session['height']) != (568, 1232) or session['output_format'] != 'RGB565':
                issues.append('Board acceptance needs observed DRM at 568x1232 RGB565.')
            expected = 'physical' if provenance['evidence_class'] == 'board-real-touch' else 'injected'
            if session['input'] != expected:
                issues.append('Board manifest and observed input provenance disagree.')
    if board and not ({1}.issubset({r['session']['cards'] for r in runs}) and any(r['session']['cards'] >= 2 for r in runs)):
        issues.append('Board acceptance requires separate one-card and multiple-card workloads.')
    status = ('FAIL' if any(run['status'] == 'FAIL' for run in runs) else
              'INCOMPLETE' if issues or any(run['status'] != 'PASS' for run in runs) else 'PASS')
    return {'schema': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
            'status': status, 'board_budget_gate': status if board else 'NOT_BOARD_EVIDENCE',
            'provenance': provenance, 'telemetry_sha256': hashlib.sha256(raw).hexdigest(),
            'telemetry_bytes': len(raw), 'ignored_non_benchmark_lines': ignored,
            'renderer_requested': renderer, 'budgets': BUDGETS, 'runs': runs, 'missing_evidence': sorted(set(issues)),
            'limits': ['Input times begin at compositor dispatch, not physical finger contact.',
                       'Presentation timestamps are backend feedback, not optical pixel visibility.',
                       'A native capture and real-finger optical review remain separate acceptance gates.',
                       'Board provenance is operator-attested; this parser does not contact or identify hardware.',
                       'Missing data, callbacks alone, or headless execution cannot prove board acceptance.',
                       'Memory is sampled cgroup memory.current; spikes between samples are unmeasured.',
                       'Physical input labels require operator provenance; telemetry cannot authenticate a human finger.'],
            'optical_visibility': 'UNVERIFIED', 'real_finger_acceptance': 'UNVERIFIED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('docs/evidence/card-shell/telemetry.log'))
    parser.add_argument('--board', action='store_true', help='validate previously collected board telemetry; never opens UART')
    parser.add_argument('--manifest', type=Path, default=Path('docs/evidence/card-shell/manifest.json'))
    parser.add_argument('--renderer', choices=('pixman', 'vglite'), default='pixman')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    if args.self_test:
        if args.board or args.output:
            parser.error('--self-test cannot produce or claim a board report')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ParserTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    try:
        # Read one extra byte to detect truncation; never accept a partial input.
        with args.input.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        manifest = json.loads(args.manifest.read_text()) if args.board else None
        report = analyze(raw, args.board, manifest, args.renderer)
    except (OSError, json.JSONDecodeError, InvalidEvidence) as error:
        # Paths and arbitrary input values may be private; use bounded error text.
        message = str(error) if isinstance(error, InvalidEvidence) else 'telemetry or manifest is missing, unreadable, or invalid JSON'
        print(f'card-shell-benchmark: {message}', file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end='')
    return 0 if report['status'] == 'PASS' else 1


# Fixtures exist only for --self-test. They can never be selected by --board.
def fixture(run='one', cards=1):
    rows = []
    def emit(event, **fields):
        rows.append(dict(v=1, run=run, event=event, **fields))
    start = 3_000_000_000
    emit('session', t_ns=start, clock='monotonic', backend='drm', renderer='pixman',
         width=568, height=1232, output_format='RGB565', input='injected', cards=cards)
    for phase, base, memory in [('baseline', 0, 100_000_000), ('active', start, 110_000_000),
                                ('restored', 6_000_000_000, 102_000_000)]:
        for step in range(3):
            t = base + step * 1_000_000_000
            emit('resource', phase=phase, t_ns=t, cpu_ns=t // 4, memory_bytes=memory, scope='session')
    for index in range(90):
        t = start + index * 20_000_000
        emit('input', input_id=index+1, gesture_id=1, kind='motion', source='injected', t_ns=t)
        emit('submit', input_id=index+1, frame_id=index+10, t_ns=t+2_000_000, update_cpu_ns=1_000_000, final=0)
        emit('present', frame_id=index+10, t_ns=t+10_000_000, presented=1, clock='monotonic')
    for index in range(3):
        t = start + 2_000_000_000 + index*100_000_000
        emit('input', input_id=100+index, gesture_id=2+index, kind='release', source='injected', t_ns=t)
        emit('submit', input_id=100+index, frame_id=200+index, t_ns=t+2_000_000, update_cpu_ns=1_000_000, final=1)
        emit('present', frame_id=200+index, t_ns=t+10_000_000, presented=1, clock='monotonic')
    return rows


def encode(rows):
    return ('\n'.join(PREFIX + ' '.join(f'{key}={value}' for key, value in row.items()) for row in rows) + '\n').encode()


def test_manifest():
    return dict(schema=1, environment='board', board_model='LILYGO T-Display-K230', ownership='coordinator-reserved',
                source_revision='a'*40, package_store_path='/nix/store/'+'a'*32+'-k230-card-shell',
                evidence_class='board-injected', collected_at='2026-09-23T00:00:00Z')


class ParserTests(unittest.TestCase):
    def test_complete_correlated_workloads(self):
        report = analyze(encode(fixture()+fixture('two', 2)), True, test_manifest())
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['optical_visibility'], 'UNVERIFIED')
        self.assertEqual(report['runs'][0]['metrics']['motion_to_present_ms']['p95'], 10)

    def test_missing_present_is_incomplete(self):
        rows = [r for r in fixture() if r['event'] != 'present']
        report = analyze(encode(rows))
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['runs'][0]['metrics']['motion_to_present_ms']['count'], 0)

    def test_callback_counts_never_substitute(self):
        raw = b'{"event":"heartbeat","callbacks":9999,"frames":9999}\n'
        with self.assertRaises(InvalidEvidence):
            analyze(raw)

    def test_memory_fail_and_missing_scope(self):
        rows = fixture()
        for row in rows:
            if row['event'] == 'resource' and row['phase'] == 'active':
                row['memory_bytes'] += 100_000_000
        self.assertEqual(analyze(encode(rows))['status'], 'FAIL')
        for row in rows:
            if row['event'] == 'resource':
                row['scope'] = 'compositor'
        report = analyze(encode(rows))
        self.assertEqual(report['runs'][0]['metrics']['incremental_session_memory_bytes']['status'], 'INCOMPLETE')

    def test_coalesced_inputs_count_once_for_frame_cost(self):
        rows = fixture()
        rows.extend([dict(v=1, run='one', event='input', input_id=0, gesture_id=1, kind='motion', source='injected', t_ns=3_000_000_000),
                     dict(v=1, run='one', event='submit', input_id=0, frame_id=10, t_ns=3_002_000_000, update_cpu_ns=1_000_000, final=0)])
        run = analyze(encode(rows))['runs'][0]
        self.assertEqual(run['metrics']['frame_update_cpu_ms']['count'], 93)
        self.assertEqual(run['metrics']['motion_to_present_ms']['count'], 91)
        self.assertEqual(run['coalesced_inputs'], 1)

    def test_continuous_coalesced_input_cannot_hide_frame_stall(self):
        rows = fixture()
        # Ten real motion samples continue over 200ms while only two frames
        # appear. Group inputs 2..10 on the later frame; that is a stall, not
        # an idle finger pause even though latest-input times are far apart.
        for row in rows:
            if row['event'] == 'submit' and 2 <= row['input_id'] <= 10:
                row['frame_id'] = 19
                row['t_ns'] = 3_182_000_000
        rows = [row for row in rows if not (row['event'] == 'present' and 11 <= row['frame_id'] <= 18)]
        run = analyze(encode(rows))['runs'][0]
        self.assertEqual(run['metrics']['tracking_present_interval_ms']['status'], 'FAIL')
        self.assertEqual(run['metrics']['tracking_present_interval_ms']['max'], 180)
        self.assertEqual(run['excluded_input_pauses'], 0)

    def test_conflicting_coalesced_frame_rejected(self):
        rows = fixture()
        next(r for r in rows if r['event'] == 'submit' and r['input_id'] == 2)['frame_id'] = 10
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))

    def test_missing_input_mapping_incomplete(self):
        rows = [r for r in fixture() if not (r['event'] == 'submit' and r['input_id'] == 1)]
        self.assertEqual(analyze(encode(rows))['status'], 'INCOMPLETE')

    def test_bad_clock_and_negative_latency_rejected(self):
        for field, value in [('clock', 'realtime'), ('t_ns', 1)]:
            rows = fixture()
            next(r for r in rows if r['event'] == 'present')[field] = value
            with self.assertRaises(InvalidEvidence):
                analyze(encode(rows))

    def test_duplicates_and_unknown_fields_rejected(self):
        rows = fixture()
        rows.append(dict(rows[0]))
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))
        rows = fixture()
        rows[0]['token'] = 'private'
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))

    def test_headless_never_board_pass(self):
        rows = fixture()+fixture('two', 2)
        for row in rows:
            if row['event'] == 'session':
                row['backend'] = 'headless'
        self.assertEqual(analyze(encode(rows), True, test_manifest())['status'], 'INCOMPLETE')
        self.assertEqual(analyze(encode(rows))['board_budget_gate'], 'NOT_BOARD_EVIDENCE')

    def test_renderer_workload_and_provenance_requirements(self):
        self.assertEqual(analyze(encode(fixture()), True, test_manifest())['status'], 'INCOMPLETE')
        rows = fixture()
        next(r for r in rows if r['event'] == 'input')['source'] = 'physical'
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))
        self.assertEqual(analyze(encode(fixture()), renderer='vglite')['status'], 'INCOMPLETE')

    def test_resource_baseline_order_and_cpu_reset(self):
        rows = fixture()
        next(r for r in rows if r['event'] == 'resource' and r['phase'] == 'baseline')['t_ns'] = 4_000_000_000
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))
        rows = fixture()
        next(r for r in rows if r['event'] == 'resource' and r['phase'] == 'restored')['cpu_ns'] = 0
        with self.assertRaises(InvalidEvidence):
            analyze(encode(rows))

    def test_release_provisional_then_final_is_measured_honestly(self):
        rows = fixture()
        first = next(row for row in rows if row['event'] == 'submit' and row['input_id'] == 100)
        first['final'] = 0
        rows.extend([dict(first, frame_id=500, t_ns=5_250_000_000, final=1),
                     dict(v=1, run='one', event='present', frame_id=500, t_ns=5_260_000_000, presented=1, clock='monotonic')])
        run = analyze(encode(rows))['runs'][0]
        self.assertEqual(run['metrics']['release_to_first_submit_ms']['max'], 2)
        self.assertEqual(run['metrics']['release_to_final_submit_ms']['max'], 250)
        self.assertEqual(run['metrics']['release_to_final_submit_ms']['status'], 'FAIL')
        self.assertEqual(run['metrics']['release_to_present_ms']['max'], 260)

    def test_nonfinal_release_and_discarded_frame_incomplete(self):
        rows = fixture()
        next(r for r in rows if r['event'] == 'submit' and r['final'])['final'] = 0
        self.assertEqual(analyze(encode(rows))['status'], 'INCOMPLETE')
        rows = fixture()
        next(r for r in rows if r['event'] == 'present')['presented'] = 0
        self.assertEqual(analyze(encode(rows))['status'], 'INCOMPLETE')

    def test_slow_submission_fails(self):
        rows = fixture()
        row = next(r for r in rows if r['event'] == 'submit')
        row['update_cpu_ns'] = 40_000_000
        self.assertEqual(analyze(encode(rows))['status'], 'FAIL')

    def test_cli_missing_input_cannot_create_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            self.assertEqual(main(['--board', '--input', str(Path(directory)/'missing'), '--output', str(output)]), 2)
            self.assertFalse(output.exists())

    def test_unrelated_text_not_copied(self):
        report = analyze(b'password=never-copy-this\n'+encode(fixture()))
        self.assertNotIn('never-copy-this', json.dumps(report))
        self.assertEqual(report['ignored_non_benchmark_lines'], 1)


if __name__ == '__main__':
    raise SystemExit(main())
