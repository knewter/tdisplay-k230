"""Reserved-board navigation trial, verified virtual touch and native captures."""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

os.umask(0o077)
target, url = sys.argv[1:]
assert str(Path('/run/current-system').resolve()) == target
root = Path('/run/k230-home-navigation-install-control')
spec = importlib.util.spec_from_file_location('touch', root / 'touch.py')
touch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(touch)
device = '/dev/input/event1'
touch.verify_device(device)

def shell(*args):
    return subprocess.check_output(['runuser', '-u', 'shell', '--', 'env',
        'XDG_RUNTIME_DIR=/run/shell', 'WAYLAND_DISPLAY=wayland-1', *args], timeout=20)

def ipc(command, kind=None):
    args = ['swaymsg', '-s', '/run/shell/sway-ipc.sock', '-r']
    if kind:
        args += ['-t', kind]
    return json.loads(shell(*args, command))

def scene():
    return dict(re.findall(r'(\w+)=([^ ]+)', ipc('card_shell debug-scene')[0]['error']))

def nodes(n):
    yield n
    for c in n.get('nodes', []) + n.get('floating_nodes', []):
        yield from nodes(c)

def apps():
    return {str(n['id']): n['app_id'] for n in nodes(ipc('', 'get_tree')) if n.get('app_id')}

def focus():
    return next((str(n['id']) for n in nodes(ipc('', 'get_tree')) if n.get('focused') and n.get('app_id')), None)

def wait(pred):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(.2)
    raise AssertionError('navigation condition timed out')

def upload(name, data):
    urllib.request.urlopen(urllib.request.Request(url + '/' + name, data=data, method='POST'), timeout=20).read()

def capture(name):
    path = '/run/shell/k230-home-navigation-' + name
    shell('grim', path)
    upload(name, Path(path).read_bytes())

def swipe(end=850):
    touch.native_touch(device, 284, 1210, 284, end)
    time.sleep(.7)

shell('k230-shell-rust', '--surface', 'hide')
time.sleep(2)
initial = apps()
# Two clean, real Foot windows make identity preservation and icon focus visible.
for label, app_id in [('Terminal', 'k230-terminal'), ('Second app', 'k230-home-navigation-check')]:
    ipc("exec foot --app-id=" + app_id + " sh -c 'printf \"" + label + "\\nHome navigation check\\n\"; exec cat'")
    time.sleep(2)
wait(lambda: len(apps()) >= len(initial) + 2)
before = apps()
focused_before = focus()
assert focused_before
swipe()
wait(lambda: scene()['mode'] == '1')
capture('before.png')
# Hold at a measured 160px displacement, then release to Home.
held = {}
def measure():
    held.update(scene())
    assert abs(float(held['home_offset']) - 160) <= 2
    time.sleep(.15)
touch.native_touch(device, 284, 1210, 284, 1050, held=measure)
wait(lambda: scene()['home_selected'] == '1' and scene()['home_settling'] == '0')
assert apps() == before and focus() is None
capture('after.png')
swipe()
wait(lambda: scene()['drawer_mapped'] == '1')
time.sleep(2)
capture('picker.png')
assert apps() == before and scene()['home_selected'] == '1'
shell('k230-shell-rust', '--surface', 'hide')
time.sleep(2)
# The actual persisted Home layout determines the Terminal dock slot.
layout = json.loads(Path('/home/shell/.local/state/k230-shell/home.json').read_text())
slot = layout['dock'].index('foot.desktop')
width = (568 - 44 - 54) / 4
x = round(22 + slot * (width + 18) + width / 2)
touch.native_touch(device, x, 1154)
wait(lambda: scene()['home_selected'] == '0' and focus() in before and before[focus()] == 'k230-terminal')
assert apps() == before
capture('reopened.png')
# Return to Home for the user; leave both test windows available in Overview.
swipe()
wait(lambda: scene()['mode'] == '1')
swipe()
wait(lambda: scene()['home_selected'] == '1')
assert apps() == before
runtime = {}
for unit in ('shell.service', 'shell-ui.service', 'theme-helper.service', 'shell-keyboard.service'):
    pid = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '--value'], text=True).strip()
    runtime[unit] = {'exe': os.readlink('/proc/' + pid + '/exe'), 'active': subprocess.check_output(['systemctl', 'is-active', unit], text=True).strip()}
result = {'result': 'PASS', 'evidence_class': 'physical-board-injected-touch-native-capture',
    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'system': target,
    'windows_before': before, 'windows_after': apps(), 'held_offset': held['home_offset'],
    'checks': ['app to Overview', 'Overview to Home', 'held displacement 1:1', 'Home to Drawer',
               'window IDs preserved', 'Home Terminal icon focuses existing window', 'returned to Home'],
    'real_finger_acceptance': False}
(root / 'result.json').write_text(json.dumps(result))
upload('runtime.json', json.dumps(runtime).encode())
upload('result.json', json.dumps(result).encode())
print('K230_TRACE_HOME_NAVIGATION_PASS', flush=True)
