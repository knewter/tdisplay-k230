#!/usr/bin/env python3
"""Report an installed 1280x800 HDMI IPC diagnostic; no acceptance budgets."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('hdmi_performance', Path(__file__).with_name('hdmi-shell-performance.py'))
perf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf)
SCHEMA = 'hdmi-shell-landscape-baseline-v1'
PROFILE = 'landscape-1280x800'


def load(directory, cards):
    try:
        manifest = json.loads((directory / 'metadata.json').read_text())
        context = json.loads((directory / 'context.json').read_text())
    except (OSError, ValueError) as error:
        raise perf.InvalidTrace('missing or invalid capture manifest/context') from error
    if not isinstance(manifest, dict) or set(manifest) != {'schema', 'runs'} or manifest['schema'] != SCHEMA:
        raise perf.InvalidTrace('landscape diagnostic requires its own manifest schema')
    if not isinstance(manifest['runs'], list) or len(manifest['runs']) != 1:
        raise perf.InvalidTrace('each landscape workload needs exactly one run')
    item = manifest['runs'][0]
    row = perf.validate_run_metadata(item, directory, 'candidate', profile=PROFILE)
    if row['cards'] != cards or row['drag_count'] < 24 or row['input_class'] != 'injected':
        raise perf.InvalidTrace('requires matching card count and at least 24 IPC-injected drags')
    if not isinstance(context, dict) or any(context.get(k) != v for k, v in {
            'schema': SCHEMA, 'profile': PROFILE, 'status': 'CAPTURED',
            'source_revision': row['source_revision'], 'input': 'injected',
            'operator_confirmed_contacts': False, 'complete_drag_count': row['drag_count'],
            'stop_error': None, 'restore_error': None, 'reason': None}.items()):
        raise perf.InvalidTrace('capture context or cleanup is incomplete/inconsistent')
    collector = context.get('collector_sha256')
    if not isinstance(collector, str) or not re.fullmatch('[0-9a-f]{64}', collector):
        raise perf.InvalidTrace('missing collector identity')
    workload = context.get('injected_workload')
    if not isinstance(workload, dict) or any(workload.get(k) != v for k, v in {
            'route': 'compositor IPC card_shell down/motion/up', 'moves_per_drag': 35,
            'nominal_motion_seconds': .7, 'settle_seconds': .8}.items()):
        raise perf.InvalidTrace('unexpected IPC workload pacing')
    outputs = context.get('output_before')
    if not isinstance(outputs, list) or len(outputs) != 1 or outputs != context.get('output_after'):
        raise perf.InvalidTrace('output changed or output context is incomplete')
    out = outputs[0]
    mode = out.get('current_mode') or {}
    if (out.get('name'), out.get('active'), mode.get('width'), mode.get('height'),
            out.get('transform'), out.get('scale')) != ('HDMI-A-1', True, 1280, 800, 'normal', 1):
        raise perf.InvalidTrace('context does not describe current landscape HDMI')
    identity = context.get('compositor') or {}
    for key in ('compositor_executable', 'pixman_identity'):
        if identity.get(key) != row['runtime_identity'][key]:
            raise perf.InvalidTrace('context and manifest runtime identities differ')
    return row, {'collector_sha256': collector, 'injected_workload': workload,
                 'output': outputs, 'frequency': context.get('frequency')}


def report(one, two):
    rows, contexts = zip(load(one, 1), load(two, 2))
    for key in ('source_revision', 'runtime_identity', 'format', 'input_class'):
        if rows[0][key] != rows[1][key]:
            raise perf.InvalidTrace(f'mixed {key} across landscape workloads')
    for key in ('collector_sha256', 'injected_workload', 'output'):
        if contexts[0][key] != contexts[1][key]:
            raise perf.InvalidTrace(f'mixed {key} across landscape workloads')
    if rows[0]['run'] == rows[1]['run']:
        raise perf.InvalidTrace('workloads reuse a run identity')
    return {'schema': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'MEASURED', 'performance_acceptance': 'NOT_EVALUATED',
            'limits': ['IPC injection is not native-input or physical contact proof.',
                       'IPC processing adds to nominal pacing; dispatch timing excludes input delivery.',
                       'Presentation feedback is not optical visibility.',
                       'This landscape diagnostic does not satisfy portrait performance or glass gates.'],
            'workloads': list(rows), 'capture_contexts': list(contexts)}


class Fixtures(unittest.TestCase):
    def make(self, directory, cards):
        directory.mkdir()
        item, raw = perf.fixture_run(f'landscape{cards}', 'candidate', cards)
        item.update(logical_width=1280, logical_height=800, physical_width=1280,
                    physical_height=800, transform=0)
        raw = raw.replace(b'width=1080 height=1920', b'width=1280 height=800')
        (directory / item['log']).write_bytes(raw)
        (directory / 'metadata.json').write_text(json.dumps({'schema': SCHEMA, 'runs': [item]}))
        output = [{'name': 'HDMI-A-1', 'active': True, 'scale': 1, 'transform': 'normal',
                   'current_mode': {'width': 1280, 'height': 800, 'refresh': 59910}}]
        context = dict(schema=SCHEMA, profile=PROFILE, status='CAPTURED', input='injected',
            source_revision=item['source_revision'], operator_confirmed_contacts=False,
            complete_drag_count=24, stop_error=None, restore_error=None, reason=None,
            collector_sha256='b'*64, output_before=output, output_after=output,
            compositor={k: item[k] for k in ('compositor_executable', 'pixman_identity')},
            injected_workload=dict(route='compositor IPC card_shell down/motion/up', moves_per_drag=35,
                                   nominal_motion_seconds=.7, settle_seconds=.8))
        (directory / 'context.json').write_text(json.dumps(context))
        return item

    def test_report_and_portrait_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            one, two = Path(tmp)/'one', Path(tmp)/'two'
            item = self.make(one, 1); self.make(two, 2)
            result = report(one, two)
            self.assertEqual(result['status'], 'MEASURED')
            self.assertEqual(result['performance_acceptance'], 'NOT_EVALUATED')
            self.assertEqual(result['workloads'][0]['input_to_present_ms']['p95_ms'], 10)
            with self.assertRaises(perf.InvalidTrace):
                perf.load_side(one, 'candidate')
            with self.assertRaises(perf.InvalidTrace):
                perf.validate_run_metadata(item, one, 'candidate')

    def test_rejects_invalid_evidence(self):
        mutations = ('schema', 'geometry', 'scale', 'card_count', 'source', 'pacing',
                     'collector', 'cleanup', 'missing_present', 'missing_cost', 'physical', 'run')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                one, two = Path(tmp)/'one', Path(tmp)/'two'
                self.make(one, 1); self.make(two, 2)
                mpath, cpath = two/'metadata.json', two/'context.json'
                manifest, context = json.loads(mpath.read_text()), json.loads(cpath.read_text())
                item = manifest['runs'][0]
                if mutation == 'schema': manifest['schema'] = perf.SCHEMA
                elif mutation == 'geometry': item['physical_width'] = 1920
                elif mutation == 'scale': item['scale'] = 2
                elif mutation == 'card_count': item['cards'] = 1
                elif mutation == 'source':
                    item['source_revision'] = 'c'*40; context['source_revision'] = 'c'*40
                elif mutation == 'pacing': context['injected_workload']['moves_per_drag'] = 6
                elif mutation == 'collector': context['collector_sha256'] = 'c'*64
                elif mutation == 'cleanup': context['restore_error'] = 'failed'
                elif mutation in ('missing_present', 'missing_cost'):
                    log = two/item['log']; raw = log.read_text().splitlines()
                    prefix = 'event=present' if mutation == 'missing_present' else 'repaint-cost'
                    ix = next(i for i, line in enumerate(raw) if prefix in line)
                    raw.pop(ix); log.write_text('\n'.join(raw)+'\n')
                elif mutation == 'physical': item['input_class'] = 'physical'
                elif mutation == 'run': item['run'] = 'landscape1'
                mpath.write_text(json.dumps(manifest)); cpath.write_text(json.dumps(context))
                with self.assertRaises(perf.InvalidTrace): report(one, two)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--one', type=Path); parser.add_argument('--two', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.self_test:
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Fixtures)).wasSuccessful() else 1
    if args.one is None or args.two is None: parser.error('requires --one and --two')
    try:
        result = report(args.one, args.two)
    except perf.InvalidTrace as error:
        print(f'landscape-baseline: {error}', file=sys.stderr); return 2
    text = json.dumps(result, indent=2, sort_keys=True)+'\n'
    if args.output: args.output.write_text(text)
    else: print(text, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
