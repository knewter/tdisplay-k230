#!/usr/bin/env python3
"""Measure observed HPD-to-DRM timing; never infer glass or finger results."""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--capture', type=Path, required=True)
p.add_argument('--bundle', type=Path, required=True)
a = p.parse_args()
capture = json.loads(a.capture.read_text())
identity = json.loads((a.bundle / 'identity.json').read_text())
events = capture['events']
assert events, 'No events recorded'
assert all(e['boot_id'] == capture['boot_id'] for e in events), 'Boot changed'
assert all(e['system'] == identity['system'] for e in events), 'Wrong system'
assert all(x['monotonic_seconds'] < y['monotonic_seconds']
           for x, y in zip(events, events[1:])), 'Non-monotonic events'

def matches(event, cable, activation=False):
    states = event['drm']
    hdmi = [s for name, s in states.items() if name.endswith('-HDMI-A-1')]
    panel = [s for name, s in states.items() if name.endswith('-DSI-1')]
    if len(hdmi) != 1 or len(panel) != 1:
        return False
    active, inactive = (hdmi[0], panel[0]) if cable == 'connected' else (panel[0], hdmi[0])
    if active['status'] != 'connected' or inactive['status'] != 'disconnected':
        return False
    return not activation or (active['enabled'] == 'enabled' and inactive['enabled'] == 'disabled')

starts = []
previous = events[0]['hpd']
for index, event in enumerate(events[1:], 1):
    cable = event['hpd']
    if cable not in ('connected', 'disconnected'):
        continue
    if previous not in ('connected', 'disconnected'):
        previous = cable
        continue
    if cable != previous:
        starts.append(index)
        previous = cable
transitions = []
for n, start in enumerate(starts):
    first = events[start]
    end = starts[n + 1] if n + 1 < len(starts) else len(events)
    window = events[start:end]
    result = {'hpd': first['hpd'], 'observed_utc': first['utc']}
    for key, activation in [('connector_detection_seconds', False), ('output_activation_seconds', True)]:
        match = next((e for e in window if matches(e, first['hpd'], activation)), None)
        result[key] = round(match['monotonic_seconds'] - first['monotonic_seconds'], 6) if match else None
    result['target_met'] = (result['connector_detection_seconds'] is not None
                            and result['connector_detection_seconds'] <= 1
                            and result['output_activation_seconds'] is not None
                            and result['output_activation_seconds'] <= 3)
    transitions.append(result)
passed = (len(transitions) >= 2
          and {t['hpd'] for t in transitions} == {'connected', 'disconnected'}
          and all(t['target_met'] for t in transitions))
print(json.dumps({
    'evidence_class': 'serial/sysfs sampled timing only',
    'command': 'python3 docs/evidence/hdmi-hotplug/live-switch/inspect-cable-latency.py --capture <sanitized-watch-capture> --bundle <matching-bundle>',
    'bundle': str(a.bundle.resolve()), 'system': identity['system'],
    'boot_id': capture['boot_id'], 'transitions': transitions,
    'result': 'PASS' if passed else 'INCOMPLETE_OR_SLOW',
    'limits': ['Watcher samples nominally every 250 ms; scheduling and I2C reads add jitter.',
               'Zero sampled delay means both changes appeared in one sample, not instantaneous detection.',
               'Monitor video-lock, visible handoff and real touch require separate operator reports.'],
}, indent=2))
raise SystemExit(0 if passed else 1)
