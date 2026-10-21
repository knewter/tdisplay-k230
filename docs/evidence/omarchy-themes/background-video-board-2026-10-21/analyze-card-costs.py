#!/usr/bin/env python3
"""Replay frozen card thresholds, preserving raw compositor telemetry separately.

External resources measure the sum of shell.service and shell-ui.service.
This is not a claim that the compositor emitted those session resource rows.
The board parser's portrait-only geometry gate remains in the returned report.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('card_benchmark', ROOT / 'tools/card-shell-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def replay(directory, manifest):
    combined = b''
    traces = []
    for p in sorted(directory.glob('*/telemetry.log')):
        raw = p.read_bytes()
        rows, _ = benchmark.parse_rows(raw)
        headers = [r for r in rows if r['event'] == 'session']
        assert len(headers) == 1
        header = headers[0]
        entry = header['t_ns']
        metadata = json.loads(p.with_name('metadata.json').read_text())
        external = p.with_name('external-session-resources.json')
        added = []
        transitional = 0
        if external.exists():
            samples = json.loads(external.read_text())
            assert samples['units'] == ['shell.service', 'shell-ui.service']
            assert not any(r['event'] == 'resource' and r['scope'] == 'session' for r in rows)
            for r in samples['samples']:
                t = r['t_ns']
                if t < entry:
                    phase = 'baseline'
                elif t < metadata['back_requested_ns']:
                    phase = 'active'
                elif t >= metadata['back_acknowledged_ns']:
                    phase = 'restored'
                else:
                    transitional += 1
                    continue
                added.append({'v': 1, 'run': header['run'], 'event': 'resource',
                              'phase': phase, **r, 'scope': 'session'})
        derived = raw + b''.join((json.dumps(r, sort_keys=True) + '\n').encode() for r in added)
        (p.parent / 'with-session-resources.log').write_bytes(derived)
        traces.append({'directory': p.parent.name, 'cards': header['cards'],
                       'raw_sha256': hashlib.sha256(raw).hexdigest(),
                       'derived_sha256': hashlib.sha256(derived).hexdigest(),
                       'external_resource_rows': len(added),
                       'unassigned_back_transition_samples': transitional})
        combined += derived
    assert traces
    report = benchmark.analyze(combined, board=True, manifest=manifest)
    report['resource_normalization'] = {
        'method': 'Measured sum of two service cgroups, assigned to actual entry/back IPC boundaries. Raw compositor telemetry is unchanged.',
        'units': ['shell.service', 'shell-ui.service'],
        'traces': traces,
        'analyzer_sha256': hashlib.sha256((ROOT / 'tools/card-shell-benchmark.py').read_bytes()).hexdigest(),
        'limits': 'Landscape reports retain the frozen parser portrait geometry warning. No target or threshold was changed. Samples during the explicit back-request/ack transition are counted separately, not assigned to a stable phase.',
    }
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(args.directory, json.loads(args.manifest.read_text())), indent=2) + '\n')
