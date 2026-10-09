#!/usr/bin/env python3
"""Run the UX task's console proof, retaining only identity fields publicly."""
import argparse
import shlex
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

COMMAND = ('readlink -f /run/current-system; systemctl is-active shell.service; '
           'systemctl show shell.service -p MainPID -p ExecStart; '
           'readlink -f /proc/$(systemctl show shell.service -p MainPID --value)/exe')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(mode=0o700, exist_ok=False)
repo = next(p for p in Path(__file__).resolve().parents
            if (p / 'tools/console.py').is_file())
command = ['flock', '/tmp/k230-board.lock', 'python3', 'tools/console.py',
           '/dev/ttyACM0', '--wait=3', 'env SYSTEMD_PAGER=cat SYSTEMD_COLORS=0 bash -c ' + shlex.quote(COMMAND)]
result = subprocess.run(command, cwd=repo, capture_output=True, timeout=30, check=True)
(args.output / 'uart.private.log').write_bytes(result.stdout + result.stderr)
text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', result.stdout.decode(errors='replace')).replace('\r', '')
lines = []
for line in text.splitlines():
    line = line.strip()
    if line == 'active' or re.fullmatch(r'MainPID=\d+', line) or re.fullmatch(r'/nix/store/[a-z0-9]{32}-[^\s]+', line):
        lines.append(line)
    elif line.startswith('ExecStart='):
        match = re.search(r'path=(/nix/store/[a-z0-9]{32}-[^ ;}]+)', line)
        if match:
            lines.append('ExecStart_executable=' + match[1])
assert any(line.startswith('MainPID=') for line in lines)
assert 'active' in lines
assert len([x for x in lines if x.startswith('/nix/store/')]) >= 2
assert not any('>' in x for x in lines)
(args.output / 'console.json').write_text(json.dumps({
    'utc': datetime.now(timezone.utc).isoformat(), 'command': command,
    'sanitized_console': lines,
    'sanitization': 'Prompt/echo and ExecStart arguments omitted; system, activity, PID and executable fields retained.',
    'evidence_class': 'physical serial-console identity observation; no optical or finger proof'
}, indent=2) + '\n')
print('Recorded the exact task console command with sanitized identity fields.')
