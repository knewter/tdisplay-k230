"""Observe an untouched ordinary reboot to the protected panel selection."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import uuid
import serial

os.umask(0o077)
p = argparse.ArgumentParser()
p.add_argument('--state', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
state = json.loads(args.state.read_text())
args.output.mkdir(parents=True, exist_ok=False)
spec = importlib.util.spec_from_file_location('protocol', '/home/jadams/tmp/k230-hdmi-continue/tools/mainline-drm-initrd-shell-trial.py')
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)
report = dict(status='FAIL', command='reboot (no U-Boot intervention)',
              timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              normal_profile=state['normal_profile'],
              persistent_boot_selection_changed=False,
              physical_panel_touch_verified=False,
              controller_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with open('/tmp/k230-board.lock', 'a') as lock, (args.output/'uart.private.log').open('xb', buffering=0) as log:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    s = protocol.PrivateSession(serial, log)
    try:
        s.write(b'\r')
        assert s.wait_for(b'root@nixos', 20), 'no Linux prompt'
        token = uuid.uuid4().hex
        s.line(shlex.join([protocol.BOARD_PYTHON, '-I', state['stage']+'/stage.py', 'check', state['stage'], '--token', token]))
        assert s.wait_for(('\nK230_COHERENT_READY '+token+'\r\n').encode(), 180), 'protected preflight failed'
        s.line('reboot', interrupt=False)
        assert s.wait_for_normal_login(180) == 'login', 'normal login absent'
        assert s.wait_for(b'root@nixos', 30), 'normal root prompt absent'
        code = '''from pathlib import Path; import hashlib,json,subprocess,zlib
def identity(p):
 d=p.read_bytes(); return dict(bytes=len(d),sha256=hashlib.sha256(d).hexdigest(),crc32=f'{zlib.crc32(d):08x}')
print('K230_NORMAL_OBSERVED '+json.dumps(dict(system=str(Path('/run/current-system').resolve()),profile=str(Path('/nix/var/nix/profiles/system').resolve()),kernel=str(Path('/run/booted-system/kernel').resolve()),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),files={n:identity(Path('/boot')/n) for n in ''' + repr(tuple(state['normal_files'])) + '''},panel_status={str(p):p.read_text().strip() for p in Path('/sys/class/drm').glob('*DSI-1/status')},input_names=[p.read_text().strip() for p in Path('/sys/class/input').glob('input*/name')],services=subprocess.run(['systemctl','is-active','shell','shell-ui','theme-helper'],capture_output=True,text=True).stdout.splitlines())))'''
        s.line(shlex.join([protocol.BOARD_PYTHON, '-I', '-c', code])+"; echo K230_NORMAL_END")
        assert s.wait_for(b'\nK230_NORMAL_END\r\n', 120), 'identity deadline'
        text = re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]', b'', s.buffer).replace(b'\r', b'')
        records = re.findall(rb'^K230_NORMAL_OBSERVED (.+)$', text, re.M)
        assert len(records)==1, 'ambiguous identity'
        observed = json.loads(records[0])
        report['observed'] = observed
        assert observed['system']==observed['profile']==state['normal_profile'], 'normal selection changed'
        assert observed['files']==state['normal_files'], 'normal files changed'
        assert observed['panel_status'] and all(v=='connected' for v in observed['panel_status'].values()), 'panel not connected'
        assert 'Goodix Berlin Capacitive TouchScreen' in observed['input_names'], 'touch missing'
        assert observed['services']==['active']*3, 'shell inactive'
        report.update(status='PASS', ordinary_autoboot_observed=True, normal_files_unchanged=True)
        print('Ordinary protected panel boot observed; physical panel taps remain separate.')
    except BaseException as error:
        report['error']=str(error)
        raise
    finally:
        s.close()
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
