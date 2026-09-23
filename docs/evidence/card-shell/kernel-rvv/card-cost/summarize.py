#!/usr/bin/env python3
"""Recheck the six captured runs and summarize paired, not pooled, costs."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    paired = load('rvv_paired', ROOT / 'tools/card-shell-rvv-benchmark.py')
    budget = load('rvv_budget', ROOT / 'tools/card-shell-benchmark.py')
    result = json.loads((HERE / 'run1/result.json').read_text())
    checked = paired.summarize(result['runs'], 3)
    if any(result[k] != v for k, v in checked.items()):
        raise ValueError('recorded comparison differs from reconstructed result')
    rows = []
    for run in result['runs']:
        public = HERE / f"run1/pair-{run['pair']}-{run['policy']}/public"
        if json.loads((public / 'run.json').read_text()) != run:
            raise ValueError('per-run record differs from batch result')
        recalculated = budget.analyze(
            (public / 'telemetry.log').read_bytes(), True,
            json.loads((public / 'manifest.json').read_text()))
        recorded = json.loads((public / 'budget.json').read_text())
        # The analyzer stamps when a report is produced; all evidence and
        # numerical fields must still match exactly across board and host.
        recalculated['created_at'] = recorded['created_at']
        if recalculated != recorded:
            raise ValueError('budget report differs from captured telemetry')
        if paired.compact_budget(recalculated) != run['budget']:
            raise ValueError('compact budget differs from complete report')
        for cards in ('1', '2'):
            workload = run['budget']['workloads'][cards]
            metrics = workload['metrics']
            rows.append({
                'pair': run['pair'], 'policy': run['policy'], 'cards': int(cards),
                'frames': workload['submitted_frames'],
                'budget': workload['status'],
                'frame_cpu_p95_ms': metrics['frame_update_cpu_ms']['p95'],
                'frame_cpu_max_ms': metrics['frame_update_cpu_ms']['max'],
                'motion_to_present_p95_ms': metrics['motion_to_present_ms']['p95'],
                'tracking_interval_p95_ms': metrics['tracking_present_interval_ms']['p95'],
                'compositor_active_cpu_percent': workload['resources']['compositor']['active']['cpu_percent'],
                'session_active_cpu_percent': workload['resources']['session']['active']['cpu_percent'],
                'incremental_memory_bytes': metrics['incremental_session_memory_bytes']['max'],
                'failed_metrics': [k for k, v in metrics.items() if v['status'] != 'PASS'],
            })
    changes = []
    for pair in (1, 2, 3):
        for cards in (1, 2):
            group = {r['policy']: r for r in rows if r['pair'] == pair and r['cards'] == cards}
            before, after = group['no-rvv'], group['auto']
            changes.append({
                'pair': pair, 'cards': cards,
                'frame_cpu_p95_change_percent': 100 * (after['frame_cpu_p95_ms'] / before['frame_cpu_p95_ms'] - 1),
                'compositor_cpu_change_percentage_points': after['compositor_active_cpu_percent'] - before['compositor_active_cpu_percent'],
            })
    summary = {
        'source_revision': result['plan']['source_revision'],
        'boot_id': result['boot_id'],
        'measurement_status': checked['measurement_status'],
        'all_card_budgets_pass': checked['all_card_budgets_pass'],
        'all_interaction_checks_observed': checked['all_interaction_checks_observed'],
        'runs': rows, 'paired_changes': changes,
        'interaction_failures': [
            {'pair': r['pair'], 'policy': r['policy'], 'cases': r['interaction_failures']}
            for r in result['runs'] if r['interaction_failures']],
        'limits': checked['limits'] + [
            'Per-run p95 values are reported separately; no pooled percentile or statistical confidence claim.',
            'CPU percentage points compare active sampled intervals, not cumulative time for an identical frame count.',
        ],
    }
    (HERE / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
