"""Reproduce the HDMI-only graph and shared-reset evidence checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

dtb = Path(sys.argv[1]).resolve(strict=True)
decoded = subprocess.check_output(['dtc', '-I', 'dtb', '-O', 'dts', str(dtb)], text=True)


def get(node, prop, fmt='s'):
    return subprocess.check_output(['fdtget', '-t', fmt, str(dtb), node, prop], text=True).strip()


symbols = {name: get('/__symbols__', name) for name in (
    'touch', 'lt9611', 'dsi', 'lt9611_in', 'lt9611_out',
    'dsi_out_lt9611', 'hdmi_connector_in')}
assert 'rm69a10' not in decoded and 'canaan,universal' not in decoded
assert get(symbols['lt9611'], 'lontium,shared-reset-owner', 'x') == get(symbols['touch'], 'phandle', 'x')
for first, second in [('dsi_out_lt9611', 'lt9611_in'), ('lt9611_out', 'hdmi_connector_in')]:
    assert get(symbols[first], 'remote-endpoint', 'x') == get(symbols[second], 'phandle', 'x')
    assert get(symbols[second], 'remote-endpoint', 'x') == get(symbols[first], 'phandle', 'x')
properties = subprocess.check_output(['fdtget', '-p', str(dtb), symbols['lt9611']], text=True).splitlines()
assert 'reset-gpios' not in properties and 'interrupts' not in properties
assert get(symbols['touch'], 'reset-gpios', 'x').split()[1:] == ['18', '1']
assert get(symbols['touch'], 'interrupts', 'x').split()[0] == '17'
assert get(symbols['lt9611'], 'reg', 'x') == '3b'
assert get(symbols['touch'], 'reg', 'x') == '5d'
assert subprocess.check_output(['fdtget', '-l', str(dtb), symbols['dsi'] + '/ports/port@1'], text=True).splitlines() == ['endpoint']
print(json.dumps(dict(result='PASS', dtb=str(dtb), sha256=hashlib.sha256(dtb.read_bytes()).hexdigest(), symbols=symbols), indent=2))
