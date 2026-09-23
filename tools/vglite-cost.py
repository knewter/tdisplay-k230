#!/usr/bin/env python3
"""Summarize opt-in renderer costs; never treat missing/failed frames as passes."""
import argparse
import json
import math
from pathlib import Path
import statistics

PHASES = ('snapshot', 'cache', 'init', 'map', 'upload', 'command', 'finish', 'cleanup', 'replay', 'total')
METRICS = tuple(p+'_'+c+'_ns' for p in PHASES for c in ('wall', 'cpu'))


def parse(text):
    records = []
    for line in text.splitlines():
        if 'VG-Lite cost ' not in line:
            continue
        words = line.split('VG-Lite cost ', 1)[1].split()
        pairs = [word.split('=', 1) for word in words]
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError('malformed cost field')
        row = dict(pairs)
        if len(row) != len(pairs) or set(row) != {'v', 'result', 'ok', 'ops', *METRICS}:
            raise ValueError('missing, duplicate or unknown cost fields')
        if row['v'] != '1' or row['result'] not in ('gpu', 'pixman', 'failed'):
            raise ValueError('unknown schema or renderer result')
        for key in ('ok', 'ops', *METRICS):
            if not row[key].isascii() or not row[key].isdigit():
                raise ValueError('non-integer cost field')
            row[key] = int(row[key])
        if row['ok'] != 1 or row['result'] == 'failed':
            raise ValueError('failed renderer frame in measured run')
        if not row['total_wall_ns'] or not row['total_cpu_ns']:
            raise ValueError('empty clock measurement')
        for clock in ('wall', 'cpu'):
            if sum(row[p+'_'+clock+'_ns'] for p in PHASES[:-1]) > row['total_'+clock+'_ns']:
                raise ValueError('phase costs exceed measured total')
        records.append(row)
    if not records:
        raise ValueError('no measured renderer frames')
    return records


def summarize(records, minimum=100, discard=5):
    if minimum < 1 or discard < 0:
        raise ValueError('invalid sample limits')
    measured = records[discard:]
    if len(measured) < minimum:
        raise ValueError('insufficient measured frames after warmup')
    modes = {r['result'] for r in measured}
    if len(modes) != 1:
        raise ValueError('mixed GPU and fallback frames require separate interpretation')
    costs = {}
    for key in METRICS:
        values = sorted(r[key]/1e6 for r in measured)
        costs[key.removesuffix('_ns')+'_ms'] = {
            'median': statistics.median(values),
            'p95': values[math.ceil(.95*len(values))-1],
            'mean': statistics.mean(values),
        }
    cpu_total = sum(r['total_cpu_ns'] for r in measured)
    return {'renderer': next(iter(modes)), 'observed_frames': len(records),
            'discarded_warmup_frames': discard, 'measured_frames': len(measured),
            'costs': costs,
            'phase_cpu_fraction': {p: sum(r[p+'_cpu_ns'] for r in measured)/cpu_total for p in PHASES[:-1]},
            'limits': ['Instrumented render-pass costs, not frame cadence or optical latency.',
                       'Process CPU includes charged user/system time; excludes other processes and separately accounted interrupt work.',
                       'Capture and log overhead remain in the diagnostic environment.',
                       'No default-renderer performance acceptance from this profile alone.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path)
    p.add_argument('--minimum-frames', type=int, default=100)
    p.add_argument('--discard-frames', type=int, default=5)
    a = p.parse_args()
    result = summarize(parse(a.log.read_text()), a.minimum_frames, a.discard_frames)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
