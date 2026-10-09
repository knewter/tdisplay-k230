#!/usr/bin/env python3
"""Inspect the compiled combined panel/HDMI graph (host proof only)."""
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

bridge = '/soc/i2c@91408000/hdmi-bridge@3b'
touch = '/soc/i2c@91408000/touchscreen@5d'
dsi = '/soc/dsi@90850000'
output = dsi + '/ports/port@1'
panel = dsi + '/panel@0'
props = set(get(bridge, flag='-p').splitlines())
assert 'lontium,hpd-monitor-only' not in props
assert not props.intersection({'reset-gpios', 'interrupts', 'interrupts-extended'})
assert get(bridge, 'reg') == '59'
assert get(bridge, 'lontium,shared-reset-owner') == get(touch, 'phandle')
assert 'canaan,dual-output' in get(dsi, flag='-p').splitlines()
assert get(dsi, 'canaan,hsfreqrange') == '135'
assert get(dsi, 'canaan,hdmi-hsfreqrange') == '150'
assert set(get(output, flag='-l').splitlines()) == {'endpoint@0', 'endpoint@1'}
for left, right in [(output + '/endpoint@0', panel + '/ports/port@0/endpoint'),
                    (output + '/endpoint@1', bridge + '/ports/port@1/endpoint'),
                    (bridge + '/ports/port@2/endpoint', '/connector/port/endpoint')]:
    assert get(left, 'remote-endpoint') == get(right, 'phandle')
    assert get(right, 'remote-endpoint') == get(left, 'phandle')
assert get(output + '/endpoint@0', 'reg') == '0'
assert get(output + '/endpoint@1', 'reg') == '1'
print(json.dumps({
    'recorded_at': datetime.now(timezone.utc).isoformat(),
    'evidence_class': 'host compiled device-tree inspection',
    'command': 'python3 docs/evidence/hdmi-hotplug/live-switch/inspect-hotplug-dtb.py --dtb <compiled-hotplug-dtb> --fdtget <pinned-host-fdtget>',
    'device_tree': str(a.dtb.resolve()),
    'sha256': hashlib.sha256(a.dtb.read_bytes()).hexdigest(),
    'reciprocal_panel_and_bridge_dsi_endpoints': True,
    'bridge_to_hdmi_connector_reciprocal': True,
    'bridge_has_no_shared_reset_or_irq_properties': True,
    'bridge_waits_for_touch_reset_owner': True,
    'panel_phy': '0x87',
    'hdmi_phy': '0x96',
    'result': 'PASS',
    'board_probe_or_physical_hotplug_proved': False,
}, indent=2))
