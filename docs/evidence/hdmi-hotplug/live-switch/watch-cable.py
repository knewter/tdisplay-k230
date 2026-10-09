#!/usr/bin/env python3
"""Bounded board observation; read sysfs only, never select or force an output."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--seconds', type=int, default=300)
a = p.parse_args()
if not 1 <= a.seconds <= 900:
    p.error('duration must be 1..900 seconds')

def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return 'unavailable'

def sample():
    monitors = sorted(Path('/sys/bus/i2c/devices').glob('*-003b/hpd'))
    return {
        'hpd': read(monitors[0]) if len(monitors) == 1 else 'unavailable',
        'drm': {
            path.parent.name: {
                'status': read(path),
                'enabled': read(path.parent / 'enabled'),
            } for path in sorted(Path('/sys/class/drm').glob('card*-*/status'))
        },
    }

boot_id = read(Path('/proc/sys/kernel/random/boot_id'))
previous = None
end = time.monotonic() + a.seconds
with a.output.open('x') as stream:
    while time.monotonic() < end:
        state = sample()
        if state != previous:
            event = {
                'utc': datetime.now(timezone.utc).isoformat(),
                'monotonic_seconds': time.monotonic(),
                'boot_id': boot_id,
                'system': str(Path('/run/current-system').resolve()),
                **state,
            }
            stream.write(json.dumps(event, sort_keys=True) + '\n')
            stream.flush()
            previous = state
        time.sleep(0.25)
