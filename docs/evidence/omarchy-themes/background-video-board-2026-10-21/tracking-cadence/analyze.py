#!/usr/bin/env python3
"""Replay unchanged budgets and describe cadence; never waive a failed metric."""
from pathlib import Path
from bisect import bisect_left, bisect_right
from collections import defaultdict, Counter
import importlib.util
import json
import re

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('card_costs', HERE.parent / 'analyze-card-costs.py')
costs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(costs)
benchmark = costs.benchmark


def distribution(values):
    return {'count': len(values), **({
        'p50': benchmark.percentile(values, .5),
        'p95': benchmark.percentile(values, .95),
        'max': max(values),
    } if values else {})}


def describe(raw):
    rows, _ = benchmark.parse_rows(raw)
    headers = [r for r in rows if r['event'] == 'session']
    assert len(headers) == 1
    inputs = {r['input_id']: r for r in rows if r['event'] == 'input'}
    presentations = {r['frame_id']: r['t_ns'] for r in rows
                     if r['event'] == 'present' and r['presented']}
    submits = {r['frame_id']: r['t_ns'] for r in rows if r['event'] == 'submit'}
    motions = defaultdict(list)
    represented = defaultdict(dict)
    for r in inputs.values():
        if r['kind'] == 'motion':
            motions[r['gesture_id']].append(r['t_ns'])
    for r in rows:
        if r['event'] != 'submit' or r['frame_id'] not in presentations:
            continue
        entry = inputs[r['input_id']]
        if entry['kind'] == 'motion':
            g = represented[entry['gesture_id']]
            g[r['frame_id']] = max(g.get(r['frame_id'], 0), entry['t_ns'])
    input_gaps, all_present_gaps, tracking_gaps = [], [], []
    over_budget, with_intermediate_present = 0, 0
    for gesture, times in motions.items():
        times.sort()
        input_gaps.extend((b-a)/1e6 for a, b in zip(times, times[1:]))
        actual = sorted(t for t in presentations.values() if times[0] <= t <= times[-1])
        all_present_gaps.extend((b-a)/1e6 for a, b in zip(actual, actual[1:]))
        frames = sorted(represented[gesture], key=submits.get)
        for before, after in zip(frames, frames[1:]):
            a, b = represented[gesture][before], represented[gesture][after]
            between = times[bisect_left(times, a):bisect_right(times, b)]
            if any(y-x > 50_000_000 for x, y in zip(between, between[1:])):
                continue
            p, q = presentations[before], presentations[after]
            gap = (q-p)/1e6
            tracking_gaps.append(gap)
            if gap > benchmark.BUDGETS['tracking_present_interval_ms']['p95']:
                over_budget += 1
                with_intermediate_present += any(p < t < q for t in presentations.values())
    stages = defaultdict(list)
    for line in raw.decode().splitlines():
        if not line.startswith('K230_CARD_SHELL repaint-cost '):
            continue
        fields = dict(re.findall(r'(\w+)=([0-9]+)', line))
        for key in ['render_cpu_ns', 'prepare_cpu_ns', 'build_cpu_ns', 'commit_cpu_ns']:
            stages[key.removesuffix('_ns')+'_ms'].append(int(fields[key])/1e6)
    return {
        'run': headers[0]['run'], 'cards': headers[0]['cards'],
        'input_dispatch_interval_ms': distribution(input_gaps),
        'all_present_intervals_during_motion_ms': distribution(all_present_gaps),
        'all_present_vblank_buckets': dict(Counter(round(t/19.16094) for t in all_present_gaps)),
        'tracking_present_interval_ms': distribution(tracking_gaps),
        'tracking_intervals_above_33_334_ms': over_budget,
        'over_budget_tracking_intervals_with_an_intermediate_present': with_intermediate_present,
        'submit_to_present_ms': distribution([(t-submits[f])/1e6 for f, t in presentations.items() if f in submits]),
        'repaint_stages': {k: distribution(v) for k, v in stages.items()},
        'limits': 'All-present intervals are a diagnostic across each gesture first/last motion window, not a replacement for the frozen correlated tracking metric. Presentation is backend feedback, not optical visibility. No kernel cause inferred.',
    }


if __name__ == '__main__':
    manifest = json.loads((HERE/'manifest.json').read_text())
    report = costs.replay(HERE, manifest)
    (HERE/'budget-analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    diagnostic = {p.parent.name: describe(p.read_bytes()) for p in sorted(HERE.glob('*/telemetry.log'))}
    for run in diagnostic.values():
        accepted = next(r for r in report['runs'] if r['run'] == run['run'])
        frozen = accepted['metrics']['tracking_present_interval_ms']
        assert run['tracking_present_interval_ms']['count'] == frozen['count']
        assert run['tracking_present_interval_ms']['p95'] == frozen['p95']
    (HERE/'diagnostics.json').write_text(json.dumps(diagnostic, indent=2)+'\n')
    for name, run in diagnostic.items():
        print(name, 'tracking p95', run['tracking_present_interval_ms'].get('p95'),
              'all-present p95', run['all_present_intervals_during_motion_ms'].get('p95'),
              'slow gaps/intermediate present', run['tracking_intervals_above_33_334_ms'],
              run['over_budget_tracking_intervals_with_an_intermediate_present'])
