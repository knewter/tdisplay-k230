#!/usr/bin/env python3
"""Correlate diagnostic CPU subdivisions to the unchanged acceptance producer."""
import argparse
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('card_benchmark', ROOT/'tools/card-shell-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)
PREFIX = 'K230_CARD_SHELL frame-cost '
KEYS = {'run', 'frame_id', 'total_cpu_ns', 'render_cpu_ns', 'input_cpu_ns'}


def analyze(raw):
    events, _ = benchmark.parse_rows(raw)
    sessions = {row['run']: row for row in events if row['event'] == 'session'}
    submitted = {}
    for row in events:
        if row['event'] != 'submit':
            continue
        key = (row['run'], row['frame_id'])
        if key in submitted and submitted[key] != row['update_cpu_ns']:
            raise ValueError('conflicting submitted-frame totals')
        submitted[key] = row['update_cpu_ns']
    profiles = {}
    for line in raw.decode('utf-8').splitlines():
        if PREFIX not in line:
            continue
        pairs = [field.split('=') for field in line.split(PREFIX, 1)[1].split()]
        if len(pairs) != 5 or any(len(p) != 2 or not re.fullmatch(r'[0-9]+', p[1]) for p in pairs):
            raise ValueError('malformed numeric frame profile')
        row = dict(pairs)
        if set(row) != KEYS:
            raise ValueError('incomplete profile fields')
        key = (row['run'], int(row['frame_id']))
        row = {k: int(v) for k, v in row.items()}
        if key in profiles or key not in submitted or key[0] not in sessions:
            raise ValueError('duplicate or uncorrelated profile')
        if row['total_cpu_ns'] != submitted[key]:
            raise ValueError('profile differs from accepted producer total')
        row['other_cpu_ns'] = row['total_cpu_ns'] - row['render_cpu_ns'] - row['input_cpu_ns']
        if row['other_cpu_ns'] < 0:
            raise ValueError('overlapping CPU subdivisions')
        profiles[key] = row
    if not submitted or profiles.keys() != submitted.keys():
        raise ValueError('missing per-frame diagnostic coverage')
    runs = []
    for run, session in sorted(sessions.items(), key=lambda item: item[1]['cards']):
        rows = [row for key, row in profiles.items() if key[0] == run]
        if not rows:
            continue
        total = sum(row['total_cpu_ns'] for row in rows)
        if total <= 0:
            raise ValueError('empty CPU measurement')
        stages = {}
        for stage in ('total', 'render', 'input', 'other'):
            samples = [row[stage+'_cpu_ns']/1e6 for row in rows]
            stages[stage] = {'p95_ms': benchmark.percentile(samples, .95),
                             'max_ms': max(samples),
                             'mean_ms': sum(samples)/len(samples),
                             'percent_of_total_cpu': 100*sum(row[stage+'_cpu_ns'] for row in rows)/total}
        runs.append({'run': run, 'cards': session['cards'], 'frames': len(rows), 'stages': stages})
    return {'schema': 'card-frame-cpu-diagnostic-v1', 'runs': runs,
            'limits': ['Diagnostic CPU subdivision only; not an acceptance decision.',
                       'Render includes scene preparation, renderer and output commit.',
                       'Additional instrumentation has measurement overhead.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.input.read_bytes())
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
