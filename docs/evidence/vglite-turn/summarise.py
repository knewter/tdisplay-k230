#!/usr/bin/env python3
"""Median per-frame figures from TURN_BENCH lines. Usage: summarise.py file..."""
import re
import statistics
import sys
import collections

by = collections.defaultdict(lambda: collections.defaultdict(list))
for f in sys.argv[1:]:
    for line in open(f):
        m = re.match(r'TURN_BENCH mode=(\S+) round=\d+ reps=\d+ (.*)', line)
        if m:
            for k, v in re.findall(r'(\w+)=(\d+)', m.group(2)):
                by[m.group(1)][k].append(int(v) / 1e6)
for mode, d in by.items():
    print(f"{mode:30s} n={len(d['wall_ns_per_frame'])} " + " ".join(
        f"{k.replace('_ns_per_frame', '').replace('_ns', '')}={statistics.median(v):.3f}ms"
        for k, v in d.items()))
