#!/usr/bin/env python3
"""Analyze bounded, normalized Pixman draw/rotation diagnostics.

Rows are produced by an evidence-side journal collector, not arbitrary journal
text. Journal receipt times can group operations from one render pass; they
are not exact input/presentation timestamps. This tool makes no budget claim.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import unittest

COMMON = {'v', 'stage', 't_ns'}
FIELDS = {
    'draw': COMMON | {'transform', 'path', 'copy_cpu_ns', 'total_cpu_ns',
                      'dst_pixels', 'scratch_bytes'},
    'rotation': COMMON | {'src_width', 'src_height', 'dst_width', 'dst_height',
                          'format', 'transform', 'rotation_cpu_ns', 'scratch_bytes'},
}


def parse(text):
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        if not parts or parts[0] != 'K230_PANEL_PAINT':
            raise ValueError(f'line {number}: expected normalized profile row')
        row = {}
        for part in parts[1:]:
            if '=' not in part:
                raise ValueError(f'line {number}: malformed field')
            key, value = part.split('=', 1)
            if key in row:
                raise ValueError(f'line {number}: duplicate field')
            row[key] = value
        if row.get('stage') not in FIELDS or set(row) != FIELDS[row['stage']]:
            raise ValueError(f'line {number}: unexpected fields/stage')
        if row['v'] != '1':
            raise ValueError(f'line {number}: unsupported version')
        for key in row.keys() - {'stage', 'path', 'format'}:
            if not row[key].isascii() or not row[key].isdigit():
                raise ValueError(f'line {number}: nonnumeric {key}')
            row[key] = int(row[key])
        if row['transform'] not in range(8):
            raise ValueError(f'line {number}: invalid transform')
        if row['stage'] == 'draw':
            if row['path'] not in {'sampler', 'tiled'}:
                raise ValueError(f'line {number}: invalid draw path')
            if row['copy_cpu_ns'] > row['total_cpu_ns']:
                raise ValueError(f'line {number}: copy exceeds total')
        else:
            if row['transform'] not in {1, 3}:
                raise ValueError(f'line {number}: non-quarter rotation')
            if (len(row['format']) != 10 or not row['format'].startswith('0x') or
                    any(c not in '0123456789abcdef' for c in row['format'][2:])):
                raise ValueError(f'line {number}: invalid format')
            if (row['src_width'] != row['dst_height'] or
                    row['src_height'] != row['dst_width'] or
                    not 0 < row['src_width'] <= 16384 or
                    not 0 < row['src_height'] <= 16384):
                raise ValueError(f'line {number}: invalid rotation geometry')
        rows.append(row)
        if len(rows) > 640:
            raise ValueError('profile exceeds bounded row caps')
    if not rows:
        raise ValueError('empty profile')
    return sorted(rows, key=lambda r: r['t_ns'])


def distribution(values):
    if not values:
        return {'count': 0}
    values = sorted(values)
    return {'count': len(values), 'mean': statistics.mean(values),
            'p50': values[(len(values) - 1) // 2],
            'p95': values[math.ceil(len(values) * .95) - 1],
            'max': values[-1]}


def analyze(rows, workload=None):
    draws = [r for r in rows if r['stage'] == 'draw']
    rotations = [r for r in rows if r['stage'] == 'rotation']
    start, end = 0, 2**64
    if workload:
        gestures = workload['gestures']
        if not gestures:
            raise ValueError('workload has no gestures')
        start = min(g['down_monotonic_ns'] for g in gestures)
        end = max(g['up_monotonic_ns'] for g in gestures) + 800_000_000
    selected = [r for r in rows if start <= r['t_ns'] <= end]
    pairs = []
    # Only completed passes bounded by two observed rotation rows are grouped.
    # If the texture cap is reached, discard every frame touching its tail.
    cutoff = draws[-1]['t_ns'] if len(draws) >= 512 else 2**64
    for previous, rotation in zip(rotations, rotations[1:]):
        if not start <= previous['t_ns'] < rotation['t_ns'] <= min(end, cutoff):
            continue
        textures = [r for r in draws if previous['t_ns'] < r['t_ns'] <= rotation['t_ns']]
        pairs.append({'rotation_journal_t_ns': rotation['t_ns'],
                      'texture_draws': len(textures),
                      'texture_cpu_ns': sum(r['total_cpu_ns'] for r in textures),
                      'texture_copy_cpu_ns': sum(r['copy_cpu_ns'] for r in textures),
                      'rotation_cpu_ns': rotation['rotation_cpu_ns']})
    return {
        'schema': 'k230-panel-paint-profile-v1',
        'status': ('INCOMPLETE' if not pairs else 'PARTIAL' if len(draws) >= 512 or len(rotations) >= 128 else 'MEASURED'),
        'quantiles': 'nearest-rank p95; lower-middle p50',
        'rotation_formats': {f: sum(r['format'] == f for r in rotations) for f in sorted({r['format'] for r in rotations})},
        'evidence_class': 'board software CPU diagnostics; no optical claim',
        'limits': ['texture timers exclude solid rectangles, scene preparation and commit',
                   'journal receipt timestamps group rows; no exact commit ID',
                   'profiling/logging overhead is not subtracted',
                   'draw cap512 / rotation cap128 may truncate the workload',
                   'cost distributions do not establish a performance budget pass'],
        'row_counts': {stage: sum(r['stage'] == stage for r in rows) for stage in FIELDS},
        'cap_reached': {'draw': len(draws) >= 512, 'rotation': len(rotations) >= 128},
        'selected_time_window_ns': [start, end] if workload else None,
        'selected_row_counts': {stage: sum(r['stage'] == stage for r in selected) for stage in FIELDS},
        'draw_cpu_ms': distribution([r['total_cpu_ns'] / 1e6 for r in selected if r['stage'] == 'draw']),
        'rotation_cpu_ms': distribution([r['rotation_cpu_ns'] / 1e6 for r in selected if r['stage'] == 'rotation']),
        'grouped_frame_texture_cpu_ms': distribution([r['texture_cpu_ns'] / 1e6 for r in pairs]),
        'grouped_frame_rotation_cpu_ms': distribution([r['rotation_cpu_ns'] / 1e6 for r in pairs]),
        'grouped_frames': pairs,
    }


class ProfileTests(unittest.TestCase):
    draw = 'K230_PANEL_PAINT v=1 stage=draw t_ns=20 transform=0 path=sampler copy_cpu_ns=0 total_cpu_ns=12 dst_pixels=80 scratch_bytes=0'
    turn = 'K230_PANEL_PAINT v=1 stage=rotation t_ns=30 src_width=20 src_height=10 dst_width=10 dst_height=20 format=0x20020888 transform=3 rotation_cpu_ns=7 scratch_bytes=800'

    def test_pass_grouping_and_reverse_journal(self):
        r = parse('\n'.join([self.turn, self.draw, self.turn.replace('t_ns=30', 't_ns=10')]))
        a = analyze(r)
        self.assertEqual(a['grouped_frames'][0]['texture_cpu_ns'], 12)
        self.assertEqual(a['grouped_frames'][0]['rotation_cpu_ns'], 7)

    def test_rejects_unbounded_or_secret_fields(self):
        for text in [self.draw + ' token=secret', self.draw + ' t_ns=21', self.draw.replace('sampler', 'arbitrary'), self.turn.replace('dst_width=10', 'dst_width=11'), self.draw.replace('copy_cpu_ns=0', 'copy_cpu_ns=13'), self.draw.replace('t_ns=20', 't_ns=-1')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_capped_tail_is_not_grouped_as_complete(self):
        rows = [self.turn.replace('t_ns=30', 't_ns=1')]
        rows += [self.draw.replace('t_ns=20', 't_ns='+str(i)) for i in range(2,514)]
        rows += [self.turn.replace('t_ns=30', 't_ns=514')]
        report = analyze(parse('\n'.join(rows)))
        self.assertEqual(report['grouped_frames'], [])
        self.assertTrue(report['cap_reached']['draw'])

    def test_no_frame_invented_from_texture_only(self):
        self.assertEqual(analyze(parse(self.draw))['grouped_frames'], [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path)
    parser.add_argument('--workload', type=Path, help='same-run collection metadata with monotonic gesture times')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        return not unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(ProfileTests)).wasSuccessful()
    if not args.log or not args.output:
        parser.error('--log and --output are required')
    report = analyze(parse(args.log.read_text()), json.loads(args.workload.read_text()) if args.workload else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'grouped_frames'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
