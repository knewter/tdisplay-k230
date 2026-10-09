#!/usr/bin/env python3
"""Inspect the compiled status-only qualification graph (host proof only)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--dtb', type=Path, required=True)
p.add_argument('--fdtget', type=Path, required=True)
a = p.parse_args()

def get(node, prop=None, flag=None):
    args = [str(a.fdtget)]
    if flag:
        args += [flag]
    args += [str(a.dtb), node]
    if prop:
        args += [prop]
    return subprocess.check_output(args, text=True).strip()

monitor = '/soc/i2c@91408000/hdmi-monitor@3b'
touch = '/soc/i2c@91408000/touchscreen@5d'
output = '/soc/dsi@90850000/ports/port@1'
panel = '/soc/dsi@90850000/panel@0'
props = set(get(monitor, flag='-p').splitlines())
assert 'lontium,hpd-monitor-only' in props
assert not props.intersection({'reset-gpios', 'interrupts', 'interrupts-extended'})
assert get(monitor, flag='-l') == ''
assert get(monitor, 'reg') == '59'
assert get(monitor, 'lontium,shared-reset-owner') == get(touch, 'phandle')
assert get(output, flag='-l') == 'endpoint'
assert get(output + '/endpoint', 'remote-endpoint') == get(panel + '/ports/port@0/endpoint', 'phandle')
print(json.dumps({
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'evidence_class': 'host compiled device-tree inspection',
    'command': 'python3 docs/evidence/hdmi-hotplug/live-switch/inspect-monitor-dtb.py --dtb <compiled-monitor-dtb> --fdtget <pinned-host-fdtget>',
    'device_tree': str(a.dtb.resolve()),
    'sha256': hashlib.sha256(a.dtb.read_bytes()).hexdigest(),
    'panel_is_sole_dsi_endpoint': True,
    'monitor_has_no_dsi_graph_reset_or_irq': True,
    'monitor_waits_for_touch_reset_owner': True,
    'monitor_address': '0x3b',
    'result': 'PASS',
    'board_probe_or_physical_hotplug_proved': False,
}, indent=2))
