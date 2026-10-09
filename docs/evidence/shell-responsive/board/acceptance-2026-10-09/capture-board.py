#!/usr/bin/env python3
"""Capture sanitized geometry and native Home over the reserved UART."""
import argparse
import base64
import fcntl
import hashlib
import importlib.util
import json
import re
import shlex
import uuid
from pathlib import Path

import serial

BOARD_PROGRAM = r'''
import base64,contextlib,hashlib,io,json,re,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import runpy
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
    runpy.run_path('/run/k230-mainline-runtime-state.py',run_name='__main__')
state=json.loads(buf.getvalue())
assert any(o['name']=='HDMI-A-1' and o['active'] for o in state['sway_outputs'])
ipc=['runuser','-u','shell','--','env','SWAYSOCK=/run/shell/sway-ipc.sock','swaymsg']
subprocess.run(ipc+['card_shell home'],check=True,stdout=subprocess.DEVNULL,timeout=5)
time.sleep(1)
png=Path('/run/shell/responsive-closeout-home.png')
capture=['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','grim','-c',str(png)]
subprocess.run(capture,check=True,stdout=subprocess.DEVNULL,timeout=8)
data=png.read_bytes()
assert len(data)<420000
logs=subprocess.check_output(['journalctl','-b','-u','shell-ui','--no-pager','-o','cat','-n','10000'],text=True,timeout=8)
configures=[]
for line in logs.splitlines():
    m=re.search(r'\b((?:home-|wallpaper-)?configure) (\d+)x(\d+)\b',line)
    if m:
        row={'surface_event':m[1],'width':int(m[2]),'height':int(m[3])}
        if row not in configures: configures.append(row)
pid=int(subprocess.check_output(['systemctl','show','shell','-p','MainPID','--value'],text=True,timeout=5))
result={'runtime':state,'compositor_pid':pid,'compositor_executable':str(Path('/proc/'+str(pid)+'/exe').resolve()),'configure_records':configures,'capture_utc':datetime.now(timezone.utc).isoformat(),'capture_commands':[ipc+['card_shell home'],capture],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'png_base64':base64.b64encode(data).decode(),'evidence_class':'native board capture after injected Home command; operator touch acceptance recorded separately'}
print(json.dumps(result),flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New protected directory for captures and private UART log')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    repo = next(p for p in Path(__file__).resolve().parents
                if (p / 'tools/mainline-drm-initrd-shell-trial.py').is_file())
    spec = importlib.util.spec_from_file_location(
        'protocol', repo / 'tools/mainline-drm-initrd-shell-trial.py')
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)
    token = uuid.uuid4().hex
    begin, end = 'CAPTURE_BEGIN_' + token, 'CAPTURE_END_' + token
    program = 'print(' + repr(begin) + ',flush=True);\n' + BOARD_PROGRAM
    program += '\nprint(' + repr(end) + ',flush=True)'
    raw_path = args.output / 'uart.private.log'
    with open('/tmp/k230-board.lock', 'a') as lock, raw_path.open('xb', buffering=0) as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session = protocol.PrivateSession(serial, log)
        try:
            session.write(b'\r')
            assert session.wait_for(b'root@nixos', 20)
            session.line(protocol.BOARD_PYTHON + ' -I -c ' + shlex.quote(program), interrupt=False)
            assert session.wait_for(end.encode() + b'\r\n', 55), 'capture did not complete'
        finally:
            session.close()
    raw = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw_path.read_text(errors='replace')).replace('\r', '')
    start = raw.rindex('\n' + begin + '\n') + len(begin) + 2
    stop = raw.index('\n' + end + '\n', start)
    result = json.loads(raw[start:stop])
    png = base64.b64decode(result.pop('png_base64'), validate=True)
    assert hashlib.sha256(png).hexdigest() == result['sha256']
    assert len(png) == result['bytes']
    (args.output / 'home.png').write_bytes(png)
    (args.output / 'capture.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Captured sanitized runtime/configures and native Home; board/host PNG hashes match.')


if __name__ == '__main__':
    main()
