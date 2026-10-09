#!/usr/bin/env python3
"""Read-only runtime state, with application titles and network data omitted."""
import json, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

def read(p):
    try: return Path(p).read_text().strip()
    except OSError: return 'unavailable'
def sway(kind):
    try:
        return json.loads(subprocess.check_output(['runuser', '-u', 'shell', '--', 'env', 'SWAYSOCK=/run/shell/sway-ipc.sock', 'swaymsg', '-t', kind, '-r'], timeout=5, text=True))
    except (OSError, subprocess.SubprocessError, ValueError): return []
outputs = [{k: x.get(k) for k in ['name', 'active', 'current_mode', 'transform', 'scale', 'rect']} for x in sway('get_outputs')]
inputs = [{k: x.get(k) for k in ['identifier', 'name', 'type', 'vendor', 'product']} for x in sway('get_inputs') if 'goodix' in x.get('name', '').lower() or 'k230' in x.get('name', '').lower()]
services = {name: subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True, timeout=5).stdout.strip() for name in ['shell', 'shell-ui', 'k230-touch-trackpad']}
try:
    shell_pid = int(subprocess.check_output(['systemctl', 'show', 'shell-ui', '-p', 'MainPID', '--value'], timeout=5, text=True))
    shell_executable = str(Path('/proc/' + str(shell_pid) + '/exe').resolve(strict=True))
except (OSError, subprocess.SubprocessError, ValueError):
    shell_executable = 'unavailable'
hpd = sorted(Path('/sys/bus/i2c/devices').glob('*-003b/hpd'))
touch = [p for p in sorted(Path('/sys/bus/i2c/devices').glob('*-005d/driver')) if p.is_symlink()]
result = {
    'utc': datetime.now(timezone.utc).isoformat(), 'monotonic_seconds': time.monotonic(),
    'boot_id': read('/proc/sys/kernel/random/boot_id'),
    'system': str(Path('/run/current-system').resolve()),
    'profile': str(Path('/nix/var/nix/profiles/system').resolve()),
    'kernel': str(Path('/run/current-system/kernel').resolve()),
    'cmdline': read('/proc/cmdline'), 'services': services,
    'shell_executable': shell_executable,
    'hpd': read(hpd[0]) if len(hpd) == 1 else 'unavailable',
    'drm': {x.parent.name: {'status': read(x), 'enabled': read(x.parent / 'enabled')} for x in sorted(Path('/sys/class/drm').glob('card*-*/status'))},
    'sway_outputs': outputs, 'relevant_inputs': inputs,
    'touch_driver': str(touch[0].resolve()) if len(touch) == 1 else 'unavailable',
    'touch_device': touch[0].parent.name if len(touch) == 1 else 'unavailable',
    'evidence_class': 'serial/sysfs/compositor state; no physical glass or real-touch result inferred',
}
print(json.dumps(result, sort_keys=True), flush=True)
