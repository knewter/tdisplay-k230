#!/usr/bin/env python3
"""Analyze opt-in mpv K230 presentation feedback; never infer panel photons."""
import argparse
import collections
import json
import re
from pathlib import Path


def analyze(text):
    events = collections.defaultdict(list)
    for line in text.splitlines():
        match = re.search(r'K230_(PRESENT_CLOCK|SUBMIT|PRESENT|DISCARD) (.*)', line)
        if match:
            fields = dict(re.findall(r'(\w+)=([^\s]+)', match[2]))
            events[match[1]].append(fields)
    clocks = {int(x['clock_id']) for x in events['PRESENT_CLOCK']}
    if len(clocks) != 1:
        raise ValueError('exactly one declared presentation clock is required')
    clock = clocks.pop()
    submitted = {int(x['serial']): x for x in events['SUBMIT']}
    if len(submitted) != len(events['SUBMIT']):
        raise ValueError('duplicate submission serials; use one player run per log')
    presented = events['PRESENT']
    if len(presented) < 2:
        raise ValueError('at least two presented events are required')
    resolved = set()
    for event in presented + events['DISCARD']:
        serial = int(event['serial'])
        if serial not in submitted or serial in resolved:
            raise ValueError('unmatched or multiply resolved feedback')
        original = submitted[serial]
        if event['frame'] != original['frame'] or event['pts'] != original['pts']:
            raise ValueError('feedback does not match its submitted frame')
        resolved.add(serial)
    times = [int(x['presented_ns']) for x in presented]
    sequences = [int(x['sequence']) for x in presented]
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError('presentation clock regressed')
    if any(b < a for a, b in zip(sequences, sequences[1:])):
        raise ValueError('presentation sequence regressed/reset during the run')
    span = (times[-1] - times[0]) / 1e9
    if span <= 0:
        raise ValueError('presentation timestamps did not advance')
    intervals = sorted((b - a) / 1e6 for a, b in zip(times, times[1:]))
    flags = collections.Counter(int(x['flags']) for x in presented)
    hardware_completion = all(flag & 4 for flag in flags)
    latency = None
    if clock == 1:  # Linux CLOCK_MONOTONIC matches the trace's submission clock.
        samples = [(int(x['presented_ns']) - int(x['submit_mono_ns'])) / 1e6
                   for x in presented]
        if any(x < 0 for x in samples):
            raise ValueError('presentation predates submission in the same clock')
        if any(int(x['presented_ns']) > int(x['receive_mono_ns']) for x in presented):
            raise ValueError('presentation timestamp is later than receipt')
        latency = {'min': min(samples), 'max': max(samples),
                   'mean': sum(samples) / len(samples)}
    return {
        'clock_id': clock, 'submitted': len(submitted),
        'presented': len(presented), 'discarded': len(events['DISCARD']),
        'unresolved_at_log_end': len(submitted) - len(resolved),
        'unique_presented_video_frames': len({x['frame'] for x in presented}),
        'unique_presented_pts': len({x['pts'] for x in presented}),
        'presentation_span_s': span,
        'presentation_events_per_s': (len(presented) - 1) / span,
        'interval_ms': {'median': intervals[len(intervals) // 2],
                        'p95': intervals[int((len(intervals) - 1) * .95)],
                        'max': max(intervals)},
        'sequence_first': sequences[0], 'sequence_last': sequences[-1],
        'flags_counts': dict(flags), 'all_hardware_completion': hardware_completion,
        'submit_to_present_ms': latency,
        'evidence_level': 'hardware-signalled compositor presentation' if hardware_completion
                          else 'compositor presentation without hardware-completion guarantee',
        'limitations': 'Not a photon measurement. Rates count surface updates, not decoder throughput. '
                       'Driver event correctness requires a separate source/hardware audit.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--min-seconds', type=float, default=30)
    parser.add_argument('--require-hardware-completion', action='store_true')
    args = parser.parse_args()
    try:
        result = analyze(args.log.read_text())
    except (ValueError, KeyError) as error:
        parser.exit(1, f'invalid presentation evidence: {error}\n')
    print(json.dumps(result, indent=2))
    if result['presentation_span_s'] < args.min_seconds:
        parser.exit(1, 'presentation span is shorter than the required interval\n')
    if args.require_hardware_completion and not result['all_hardware_completion']:
        parser.exit(1, 'hardware completion is not established by these events\n')


if __name__ == '__main__':
    main()
