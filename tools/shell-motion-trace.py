#!/usr/bin/env python3
"""Check shell motion against declared budgets; a missing stage never passes.

A trace follows one accepted touch through its stages:

    input -> scene_damage -> commit -> frame_done -> present

Rows are JSON objects, one per line (schema shell-motion-trace-v1), or the
K230_CARD_BENCH rows plus K230_CARD_SHELL motion-* diagnostics (--log).
Older logs carry only input, submit (commit) and present, and remain incomplete.
Scene damage is the first completed scene update in the accepted input handler;
frame_done is the first actual surface callback dispatch for its output commit.

--self-test proves the schema and the budget report format on synthetic data;
it says nothing about panel presentation. --board analyzes an operator-supplied
capture and requires its provenance; it never opens the board or the serial
port. Reduced motion is checked by comparing two runs of the same gesture.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = 'shell-motion-trace-v1'
PREFIX = 'K230_CARD_BENCH '
MOTION_PREFIX = 'K230_CARD_SHELL motion-'
STAGES = ('input', 'scene_damage', 'commit', 'frame_done', 'present')
# Legacy logs contain these stages; new diagnostics add the other two.

LOG_STAGES = ('input', 'commit', 'present')
# The mode advertises about 52.19 Hz (docs/evidence/card-shell/frame-budget),
# so one output interval is nominally 19.16 ms; that is an advertised mode,
# not measured scanout. Budgets follow the archived coherent-shell design
# (decision 7): p95 input-to-present within two output intervals.
OUTPUT_HZ = 52.19
INTERVAL_MS = 1000 / OUTPUT_HZ
BUDGETS = {
    'input_to_present_ms': {'p95': 2 * INTERVAL_MS, 'p99': 3 * INTERVAL_MS},
    'frame_interval_ms': {'p95': 2 * INTERVAL_MS, 'p99': 3 * INTERVAL_MS},
    'blank_frames': {'max': 0},
    'rss_growth_bytes': {'max': 64 * 1024 * 1024},
}
# CPU is sampled and reported; no CPU budget is declared before board tuning.
MIN_TRACES = 100
MIN_INTERVALS = 50
MIN_RESOURCE_SAMPLES = 3
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250_000
MAX_COUNTER = 2**63 - 1
CLOCKS = {'monotonic'}
MOTIONS = {'full', 'reduced'}
SOURCES = {'host', 'injected', 'physical'}
FIELDS = {
    'session': {'v', 'run', 'event', 't_ns', 'clock', 'motion', 'renderer', 'input'},
    'stage': {'v', 'run', 'event', 'trace_id', 'gesture_id', 'kind', 'stage', 't_ns', 'presented'},
    'resource': {'v', 'run', 'event', 't_ns', 'cpu_ns', 'rss_bytes'},
}
NUMERIC = {'v', 't_ns', 'gesture_id', 'presented', 'cpu_ns', 'rss_bytes'}


class InvalidTrace(ValueError):
    pass


def counter(value, field):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise InvalidTrace(f'invalid integer field: {field}')
    value = int(value)
    if value > MAX_COUNTER:
        raise InvalidTrace(f'counter outside range: {field}')
    return value


def parse_rows(raw):
    """Parse schema rows. Wrong field sets are rejected by key name only."""
    if len(raw) > MAX_BYTES:
        raise InvalidTrace('trace exceeds bounded input size')
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise InvalidTrace('trace is not UTF-8') from error
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if len(line) > 8192:
            raise InvalidTrace(f'line {number}: record exceeds size bound')
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise InvalidTrace(f'line {number}: not JSON') from error
        if not isinstance(row, dict) or row.get('event') not in FIELDS:
            raise InvalidTrace(f'line {number}: unknown trace event')
        if set(row) != FIELDS[row['event']]:
            raise InvalidTrace(f'line {number}: wrong field set for {row["event"]}')
        for key in NUMERIC & set(row):
            row[key] = counter(row[key], key)
        if row['v'] != 1:
            raise InvalidTrace(f'line {number}: unsupported trace version')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(row['run'])):
            raise InvalidTrace(f'line {number}: invalid run identifier')
        row['run'] = str(row['run'])
        if row['event'] == 'session':
            if row['clock'] not in CLOCKS or row['motion'] not in MOTIONS or \
                    row['input'] not in SOURCES:
                raise InvalidTrace(f'line {number}: unsupported session field')
        if row['event'] == 'stage':
            if row['stage'] not in STAGES or row['kind'] not in ('motion', 'release') or \
                    row['presented'] not in (0, 1):
                raise InvalidTrace(f'line {number}: unsupported stage field')
            if not re.fullmatch(r'[A-Za-z0-9_:-]{1,96}', str(row['trace_id'])):
                raise InvalidTrace(f'line {number}: invalid trace identifier')
        rows.append(row)
        if len(rows) > MAX_ROWS:
            raise InvalidTrace('trace exceeds record limit')
    if not rows:
        raise InvalidTrace('no trace rows found')
    return rows


def rows_from_log(raw):
    """Map K230_CARD_BENCH rows onto stage rows; unseen stages stay absent."""
    if len(raw) > MAX_BYTES:
        raise InvalidTrace('log exceeds bounded input size')
    rows, inputs, submits, presents, sessions, resources = [], {}, {}, {}, {}, []
    damage, callbacks, motion, settles = {}, {}, {}, {}
    for line in raw.decode('utf-8', 'replace').splitlines():
        if MOTION_PREFIX in line:
            event, _, payload = line.split(MOTION_PREFIX, 1)[1].partition(' ')
            fields = dict(pair.split('=', 1) for pair in payload.split() if '=' in pair)
            if event == 'session':
                if fields.get('motion') not in MOTIONS:
                    raise InvalidTrace('invalid motion session mode')
                if fields['run'] in motion:
                    raise InvalidTrace('duplicate motion session')
                motion[fields['run']] = fields['motion']
            elif event == 'settle':
                key = (fields['run'], fields['input_id'])
                if key in settles:
                    raise InvalidTrace('duplicate release settlement')
                counter(fields['t_ns'], 't_ns')
                settles[key] = fields
            elif event in ('stage', 'frame'):
                table, key_field, stage = (damage, 'input_id', 'scene_damage') if event == 'stage' else (callbacks, 'frame_id', 'frame_done')
                if fields.get('stage') != stage:
                    raise InvalidTrace('invalid motion diagnostic stage')
                key = (fields['run'], fields[key_field])
                if key in table:
                    raise InvalidTrace('duplicate motion diagnostic stage')
                table[key] = counter(fields['t_ns'], 't_ns')
            continue
        if PREFIX not in line:
            continue
        fields = dict(pair.split('=', 1) for pair in line.split(PREFIX, 1)[1].split() if '=' in pair)
        event = fields.get('event')
        if event == 'session':
            sessions[fields['run']] = fields
        elif event == 'input':
            inputs[(fields['run'], fields['input_id'])] = fields
        elif event == 'submit':
            key = (fields['run'], fields['input_id'])
            if key not in submits or fields.get('final') == '1':
                submits[key] = fields
        elif event == 'present':
            presents[(fields['run'], fields['frame_id'])] = fields
        elif event == 'resource' and fields.get('scope') == 'compositor':
            resources.append(fields)
    if not sessions:
        raise InvalidTrace('log has no session row')
    for run, session in sessions.items():
        source = session.get('input', 'host')
        rows.append({'v': 1, 'run': run, 'event': 'session', 't_ns': counter(session['t_ns'], 't_ns'),
                     'clock': 'monotonic', 'motion': motion.get(run, 'full'),
                     'renderer': session.get('renderer', 'pixman'),
                     'input': source if source in SOURCES else 'host'})
    for (run, input_id), entry in inputs.items():
        if run not in sessions:
            continue
        if entry.get('source') != sessions[run].get('input'):
            raise InvalidTrace('input provenance differs from session')
        trace = f'{run}:{input_id}'
        base = {'v': 1, 'run': run, 'event': 'stage', 'trace_id': trace,
                'gesture_id': counter(entry['gesture_id'], 'gesture_id'),
                'kind': entry['kind']}
        rows.append({**base, 'stage': 'input', 't_ns': counter(entry['t_ns'], 't_ns'), 'presented': 1})
        if (run, input_id) in damage:
            rows.append({**base, 'stage': 'scene_damage', 't_ns': damage[(run, input_id)], 'presented': 1})
        submit = submits.get((run, input_id))
        if not submit:
            continue
        release = entry['kind'] == 'release'
        settlement = settles.get((run, input_id))
        if release and settlement:
            submit = settlement
        rows.append({**base, 'stage': 'commit', 't_ns': counter(submit['t_ns'], 't_ns'), 'presented': 1})
        if (run, submit['frame_id']) in callbacks:
            rows.append({**base, 'stage': 'frame_done', 't_ns': callbacks[(run, submit['frame_id'])], 'presented': 1})
        present = presents.get((run, submit['frame_id']))
        # A release ends at its observed settled frame. The first post-up
        # presentation alone does not establish animation completion.
        if present and (not release or settlement):
            rows.append({**base, 'stage': 'present', 't_ns': counter(present['t_ns'], 't_ns'),
                         'presented': counter(present['presented'], 'presented')})
    for r in resources:
        rows.append({'v': 1, 'run': r['run'], 'event': 'resource', 't_ns': counter(r['t_ns'], 't_ns'),
                     'cpu_ns': counter(r['cpu_ns'], 'cpu_ns'),
                     'rss_bytes': counter(r['memory_bytes'], 'memory_bytes')})
    return rows


def percentile(values, fraction):
    """Nearest-rank percentile: deterministic and conservative at small samples."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def metric(values, budget, required):
    if not values:
        return {'status': 'INCOMPLETE', 'count': 0, 'budget': budget, 'failed': []}
    stats = {'count': len(values), 'p50': percentile(values, .5), 'p95': percentile(values, .95),
             'p99': percentile(values, .99), 'max': max(values), 'budget': budget}
    failed = [{'limit': key, 'measured': stats[key], 'allowed': allowed}
              for key, allowed in budget.items() if stats[key] > allowed]
    # A failed budget is reported even from a short sample; a pass is not.
    stats['failed'] = failed
    stats['status'] = 'FAIL' if failed else 'INCOMPLETE' if len(values) < required else 'PASS'
    return stats


def check_chain(traces, require):
    """Each trace has at most one row per stage, in order, with IDs intact."""
    for trace_id, rows in traces.items():
        seen = [row['stage'] for row in rows]
        if len(set(seen)) != len(seen):
            raise InvalidTrace('duplicate stage within one trace')
        if len({row['gesture_id'] for row in rows}) != 1 or len({row['kind'] for row in rows}) != 1:
            raise InvalidTrace('trace changes gesture or kind between stages')
        ordered = sorted(rows, key=lambda row: STAGES.index(row['stage']))
        if [row['t_ns'] for row in ordered] != sorted(row['t_ns'] for row in ordered):
            raise InvalidTrace('stage timestamps regress within one trace')
        if 'input' not in seen:
            raise InvalidTrace('trace has no input stage')
        missing = [stage for stage in require if stage not in seen]
        if missing and 'present' in seen:
            raise InvalidTrace('presented trace skips a required stage: ' + ','.join(missing))


def analyze_run(run, rows, require=STAGES):
    sessions = [row for row in rows if row['event'] == 'session']
    if len(sessions) != 1:
        raise InvalidTrace('each run needs exactly one session row')
    session = sessions[0]
    traces = defaultdict(list)
    for row in rows:
        if row['event'] == 'stage':
            traces[row['trace_id']].append(row)
    check_chain(traces, require)
    observed = [stage for stage in STAGES if any(r['stage'] == stage for rs in traces.values() for r in rs)]
    latencies, presented_at, blank, unresolved = [], [], 0, 0
    incomplete_chains = 0
    stage_latencies = {f"{a}_to_{b}_ms": [] for a, b in zip(STAGES, STAGES[1:])}
    settle = []
    for trace_id, stage_rows in traces.items():
        by_stage = {row['stage']: row for row in stage_rows}
        incomplete_chains += any(stage not in by_stage for stage in STAGES)
        for a, b in zip(STAGES, STAGES[1:]):
            if a in by_stage and b in by_stage:
                stage_latencies[f'{a}_to_{b}_ms'].append((by_stage[b]['t_ns'] - by_stage[a]['t_ns']) / 1e6)
        entry = by_stage['input']
        shown = by_stage.get('present')
        if not shown:
            unresolved += 1
            continue
        if not shown['presented']:
            blank += 1
            continue
        latencies.append((shown['t_ns'] - entry['t_ns']) / 1e6)
        presented_at.append((entry['gesture_id'], shown['t_ns']))
        if entry['kind'] == 'release':
            settle.append((shown['t_ns'] - entry['t_ns']) / 1e6)
    intervals, missed = [], 0
    gestures = defaultdict(list)
    for gesture, when in presented_at:
        gestures[gesture].append(when)
    for times in gestures.values():
        times.sort()
        for before, after in zip(times, times[1:]):
            gap = (after - before) / 1e6
            if gap > 0:
                intervals.append(gap)
                if gap > 1.5 * INTERVAL_MS:
                    missed += round(gap / INTERVAL_MS) - 1
    metrics = {
        'input_to_present_ms': metric(latencies, BUDGETS['input_to_present_ms'], MIN_TRACES),
        'frame_interval_ms': metric(intervals, BUDGETS['frame_interval_ms'], MIN_INTERVALS),
    }
    stage_metrics = {name: metric(values, {}, MIN_TRACES) for name, values in stage_latencies.items()}
    blank_fail = [{'limit': 'max', 'measured': blank, 'allowed': 0}] if blank else []
    metrics['blank_frames'] = {'status': 'FAIL' if blank_fail else 'PASS', 'count': blank,
                               'budget': BUDGETS['blank_frames'], 'failed': blank_fail}
    resources = sorted((r for r in rows if r['event'] == 'resource'), key=lambda r: r['t_ns'])
    if any(a['cpu_ns'] > b['cpu_ns'] for a, b in zip(resources, resources[1:])):
        raise InvalidTrace('resource CPU counter reset')
    if len(resources) >= MIN_RESOURCE_SAMPLES:
        span = resources[-1]['t_ns'] - resources[0]['t_ns']
        growth = max(0, max(r['rss_bytes'] for r in resources) - resources[0]['rss_bytes'])
        resource = {'status': 'PASS', 'count': len(resources), 'span_ms': span / 1e6,
                    'cpu_percent': 100 * (resources[-1]['cpu_ns'] - resources[0]['cpu_ns']) / span if span else None,
                    'peak_rss_bytes': max(r['rss_bytes'] for r in resources),
                    'rss_growth_bytes': growth, 'cpu_budget': 'none declared; reported only'}
        limit = BUDGETS['rss_growth_bytes']['max']
        metrics['rss_growth_bytes'] = {'status': 'FAIL' if growth > limit else 'PASS', 'count': 1,
            'budget': BUDGETS['rss_growth_bytes'],
            'failed': [{'limit': 'max', 'measured': growth, 'allowed': limit}] if growth > limit else []}
    else:
        resource = {'status': 'INCOMPLETE', 'count': len(resources)}
        metrics['rss_growth_bytes'] = {'status': 'INCOMPLETE', 'count': len(resources),
                                       'budget': BUDGETS['rss_growth_bytes'], 'failed': []}
    cadence = (1000 / percentile(intervals, .5)) if intervals else None
    statuses = {m['status'] for m in metrics.values()}
    return {'run': run, 'motion': session['motion'], 'renderer': session['renderer'],
            'input': session['input'], 'traces': len(traces), 'unresolved_traces': unresolved,
            'incomplete_stage_chains': incomplete_chains, 'stage_timings': stage_metrics,
            'stages_observed': observed,
            'stages_unobserved': [stage for stage in STAGES if stage not in observed],
            'missed_frames': missed, 'actual_cadence_hz': cadence,
            'nominal_cadence_hz': OUTPUT_HZ, 'settle_ms': settle,
            'metrics': metrics, 'resources': resource,
            'status': 'FAIL' if 'FAIL' in statuses else 'INCOMPLETE' if 'INCOMPLETE' in statuses or unresolved or incomplete_chains else 'PASS'}


def analyze(rows, require=STAGES):
    runs = defaultdict(list)
    for row in rows:
        runs[row['run']].append(row)
    return {run: analyze_run(run, items, require) for run, items in runs.items()}


def failures(report):
    """Plain sentences naming each failed budget and its measured value."""
    out = []
    for run, result in report.items():
        for name, item in result['metrics'].items():
            for fail in item['failed']:
                out.append(f'{run}: {name} {fail["limit"]} measured {fail["measured"]:.3f} '
                           f'exceeds {fail["allowed"]:.3f}')
    return out


def stage_shape(rows):
    """Ordered stage chain of every trace, for parity between motion modes."""
    shape = defaultdict(list)
    for row in sorted((r for r in rows if r['event'] == 'stage'),
                      key=lambda r: (STAGES.index(r['stage']), r['t_ns'])):
        shape[row['trace_id']].append(row['stage'])
    return sorted(set(map(tuple, shape.values())))


def reduced_motion_parity(full_rows, reduced_rows):
    """Reduced motion keeps every stage and only shortens settling."""
    if stage_shape(full_rows) != stage_shape(reduced_rows):
        raise InvalidTrace('reduced motion changed the trace stages')
    full, reduced = analyze(full_rows), analyze(reduced_rows)
    if len(full) != 1 or len(reduced) != 1:
        raise InvalidTrace('parity compares exactly one full and one reduced run')
    a, b = next(iter(full.values())), next(iter(reduced.values()))
    if a['motion'] != 'full' or b['motion'] != 'reduced':
        raise InvalidTrace('parity needs a full run and a reduced run, in that order')
    if not a['settle_ms'] or not b['settle_ms']:
        raise InvalidTrace('parity needs a release settle in both runs')
    full_settle, reduced_settle = percentile(a['settle_ms'], .5), percentile(b['settle_ms'], .5)
    if reduced_settle >= full_settle:
        raise InvalidTrace(f'reduced settle {reduced_settle:.3f} ms is not shorter than {full_settle:.3f} ms')
    return {'full_settle_p50_ms': full_settle, 'reduced_settle_p50_ms': reduced_settle,
            'stages': [list(shape) for shape in stage_shape(full_rows)]}


def synthetic(run, motion='full', traces=120, latency_ms=30.0, blank_every=0, stages=STAGES):
    """Deterministic rows for the self-test and tests; never a measurement."""
    rows = [{'v': 1, 'run': run, 'event': 'session', 't_ns': 0, 'clock': 'monotonic',
             'motion': motion, 'renderer': 'pixman', 'input': 'host'}]
    step = round(INTERVAL_MS * 1e6)
    offsets = {'input': 0, 'scene_damage': .1, 'commit': .45, 'frame_done': .75, 'present': 1.0}
    for index in range(traces):
        release = index == traces - 1
        # A release settles for a long time at full motion, briefly when reduced.
        total = (latency_ms * (1 if motion == 'reduced' else 6) if release else latency_ms) * 1e6
        start = 1_000_000 + index * step
        for stage in stages:
            rows.append({'v': 1, 'run': run, 'event': 'stage', 'trace_id': f'{run}-{index}',
                         'gesture_id': 1, 'kind': 'release' if release else 'motion', 'stage': stage,
                         't_ns': round(start + total * offsets[stage]),
                         'presented': 0 if stage == 'present' and blank_every and index % blank_every == blank_every - 1 and not release else 1})
    for index in range(4):
        rows.append({'v': 1, 'run': run, 'event': 'resource', 't_ns': index * 1_000_000_000,
                     'cpu_ns': index * 400_000_000, 'rss_bytes': 80_000_000 + index * 1024})
    return rows


def self_test():
    ok = analyze(synthetic('self'))['self']
    assert ok['status'] == 'PASS' and ok['stages_unobserved'] == [], ok['status']
    bad = analyze(synthetic('slow', latency_ms=60.0))['slow']
    assert bad['status'] == 'FAIL' and bad['metrics']['input_to_present_ms']['failed']
    assert any('input_to_present_ms' in line for line in failures({'slow': bad}))
    blank = analyze(synthetic('blank', blank_every=10))['blank']
    assert blank['metrics']['blank_frames']['status'] == 'FAIL'
    reduced_motion_parity(synthetic('full'), synthetic('reduced', 'reduced'))
    print(f'{SCHEMA} self-test PASS: stages {" -> ".join(STAGES)}; budgets '
          f'{json.dumps(BUDGETS, sort_keys=True)}')
    print('host schema and budget report format only; no panel presentation is claimed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--board', action='store_true',
                        help='analyze an operator-supplied capture; never opens the board')
    parser.add_argument('--trace', type=Path, help='JSONL rows of schema ' + SCHEMA)
    parser.add_argument('--log', type=Path, help='console log holding K230_CARD_BENCH rows')
    parser.add_argument('--provenance', choices=sorted(SOURCES))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--compare-motion', action='store_true',
                        help='compare one full and one reduced run from the same workload')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.board:
        parser.error('choose --self-test or --board')
    if not args.provenance or bool(args.trace) == bool(args.log):
        parser.error('--board needs --provenance and exactly one of --trace or --log')
    raw = (args.trace or args.log).read_bytes()
    rows = parse_rows(raw) if args.trace else rows_from_log(raw)
    require = STAGES if args.trace else LOG_STAGES
    report = analyze(rows, require)
    for result in report.values():
        if result['input'] != args.provenance:
            raise InvalidTrace('declared provenance does not match the session row')
    document = {'schema': SCHEMA, 'generated_utc': datetime.now(timezone.utc).isoformat(),
                'provenance': args.provenance, 'source': (args.trace or args.log).name,
                'camera_correlation': 'not provided; UNVERIFIED', 'runs': report,
                'failed_budgets': failures(report)}
    if args.compare_motion:
        modes = {mode: [run for run, result in report.items() if result['motion'] == mode]
                 for mode in MOTIONS}
        if any(len(runs) != 1 for runs in modes.values()):
            raise InvalidTrace('motion comparison needs one full and one reduced run')
        full = [row for row in rows if row['run'] == modes['full'][0]]
        reduced = [row for row in rows if row['run'] == modes['reduced'][0]]
        document['reduced_motion_parity'] = reduced_motion_parity(full, reduced)
    text = json.dumps(document, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    for line in document['failed_budgets']:
        print('FAIL', line)
    print(f'{SCHEMA}: ' + ', '.join(f'{run}={r["status"]}' for run, r in report.items()))
    return 1 if document['failed_budgets'] else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except InvalidTrace as error:
        print(f'invalid trace: {error}', file=sys.stderr)
        sys.exit(2)
