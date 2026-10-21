"""Replay render/scheduler correlation and the separate, frozen card gate."""
from pathlib import Path
import argparse
import importlib.util
import json


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[5])
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    analyzer = load('profile_analyzer', directory / 'render-profile-analyze.py')
    costs = load('profile_costs', directory.parent / 'analyze-card-costs.py')
    cadence = load('profile_cadence', directory.parent / 'tracking-cadence/analyze.py')
    profile = analyzer.analyze(directory, args.repo)
    manifest = json.loads((directory / 'manifest.json').read_text())
    budgets, diagnostics = {}, {}
    for role in ('untraced', 'traced', 'untraced-return'):
        budgets[role] = costs.replay(directory / role, manifest)
        diagnostics[role] = cadence.describe((directory / role / '3-cards/telemetry.log').read_bytes())
        frozen = budgets[role]['runs'][0]['metrics']['tracking_present_interval_ms']
        diagnostic = diagnostics[role]['tracking_present_interval_ms']
        assert (frozen['count'], frozen['p95']) == (diagnostic['count'], diagnostic['p95'])
        print(role, 'tracking p95', frozen['p95'], frozen['status'])
    for name, value in [('profile-analysis', profile), ('budget-analysis', budgets),
                        ('cadence-diagnostics', diagnostics)]:
        (directory / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
