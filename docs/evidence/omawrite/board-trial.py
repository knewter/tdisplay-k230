"""Reserved-board Omawrite trial: private scratch HOME, injected input, native capture."""
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import tomllib
import urllib.request
from writer import WriterKeyboard
import touch

os.umask(0o077)
target, url = sys.argv[1:]
assert str(Path('/run/current-system').resolve()) == target
root = Path('/run/k230-omawrite-install-control')
home = Path('/run/shell/omawrite-proof')
device = '/dev/input/event1'
touch.verify_device(device)

def shell(*args):
    return subprocess.check_output(['runuser', '-u', 'shell', '--', 'env',
        'XDG_RUNTIME_DIR=/run/shell', 'WAYLAND_DISPLAY=wayland-1',
        'XDG_DATA_DIRS=/run/current-system/sw/share', *args], timeout=30)

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
    return [n for n in nodes(ipc('', 'get_tree')) if n.get('app_id') == 'omawrite']

def app():
    return next(iter(apps()), None)

def wait(pred, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(.2)
    raise AssertionError('Omawrite trial condition timed out')

def upload(name, data):
    urllib.request.urlopen(urllib.request.Request(url + '/' + name, data=data, method='POST'), timeout=30).read()

def capture(name):
    print('K230_TRACE_CAPTURE='+name, flush=True)
    path = '/run/shell/omawrite-proof-' + name
    shell('grim', path)
    upload(name, Path(path).read_bytes())

def swipe():
    touch.native_touch(device, 284, 1210, 284, 850)
    time.sleep(.8)

def keyboard_visibility(shown):
    state, signal = ('show', 'USR2') if shown else ('hide', 'USR1')
    shell('sh', '-c', 'printf %s '+state+' > /run/shell/k230-keyboard-visible; pkill -'+signal+' -x wvkbd-mobintl')
    time.sleep(1)

assert not apps(), 'Omawrite already open; preserve it instead of testing against user work'
shell('mkdir', '-m', '700', str(home))
shell('mkdir', '-p', str(home/'.local/state/omarchy'))
shell('ln', '-s', '/home/shell/.local/state/omarchy/current', str(home/'.local/state/omarchy/current'))
scratch = home/'writing.md'
shell('sh', '-c', 'printf "Scratch document\\n" > '+shlex.quote(str(scratch)))
assert shell('xdg-mime', 'query', 'default', 'text/markdown').decode().strip() == 'k230-editor.desktop'
shell('k230-shell-rust', '--surface', 'hide')
keyboard_visibility(False)
launch = 'env PATH=/run/current-system/sw/bin:/run/wrappers/bin XDG_DATA_DIRS=/run/current-system/sw/share XDG_CONFIG_DIRS=/etc/xdg XDG_CURRENT_DESKTOP=sway XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 HOME='+shlex.quote(str(home))+' XDG_CONFIG_HOME='+shlex.quote(str(home/'.config'))+' XDG_DATA_HOME='+shlex.quote(str(home/'.local/share'))+' XDG_STATE_HOME='+shlex.quote(str(home/'.local/state'))+' QT_FORCE_STDERR_LOGGING=1 xdg-open '+shlex.quote(str(scratch))+' > '+shlex.quote(str(home/'app.log'))+' 2>&1'
started = time.monotonic()
ipc('exec '+launch)
print('K230_TRACE_WAITING_FOR_MAP', flush=True)
wait(app, 60)
first_map_seconds = time.monotonic()-started
keyboard = WriterKeyboard('/run/shell/wayland-1')
try:
    time.sleep(2)
    keyboard.key('a', 4)
    keyboard.text('# Omawrite on the K230\n\nWritten and saved on the physical board.\n')
    keyboard.key('s', 4)
    wait(lambda: scratch.read_text().startswith('# Omawrite on the K230'))
    capture('writing.png')
    original_id = app()['id']
    original_height = app()['rect']['height']
    keyboard_visibility(True)
    wait(lambda: app()['rect']['height'] < original_height)
    capture('keyboard.png')
    before = scratch.read_text()
    # Mid-keyboard letter row; verifies the real wvkbd client sends text.
    touch.native_touch(device, 284, 1045)
    time.sleep(.5)
    keyboard.key('s', 4)
    wait(lambda: scratch.read_text() != before)
    osk_added = scratch.read_text()[len(before):]
    keyboard_visibility(False)
    wait(lambda: app()['rect']['height'] == original_height)
    # Native taps on the actual footer controls, rather than shortcuts only.
    rect = app()['rect']
    touch.native_touch(device, rect['x']+96, rect['y']+rect['height']-80)
    time.sleep(1)
    capture('open-dialog.png')
    keyboard.key('Escape')
    time.sleep(.3)
    keyboard.key('s', 5)
    time.sleep(1)
    capture('save-dialog.png')
    keyboard.key('a', 4)
    keyboard.text('saved-from-dialog.md')
    keyboard.key('Return')
    second = home/'saved-from-dialog.md'
    wait(lambda: second.exists() and second.read_text() == scratch.read_text())
    saved = scratch.read_text()
    keyboard.key('o', 4)
    time.sleep(.5)
    keyboard.text('writing.md')
    keyboard.key('Return')
    wait(lambda: app().get('name', '').endswith('writing.md - Omawrite'))
    keyboard.key('s', 4)
    assert scratch.read_text() == saved
    capture('reopened.png')
    swipe()
    wait(lambda: scene()['mode'] == '1')
    capture('overview.png')
    swipe()
    wait(lambda: scene()['home_selected'] == '1')
    capture('home.png')
    layout = json.loads(Path('/home/shell/.local/state/k230-shell/home.json').read_text())
    slot = layout['dock'].index('k230-editor.desktop')
    width = (568-44-54)/4
    x = round(22+slot*(width+18)+width/2)
    touch.native_touch(device, x, 1154)
    wait(lambda: scene()['home_selected'] == '0' and app()['focused'])
    assert len(apps()) == 1 and app()['id'] == original_id
    assert scratch.read_text() == saved
    assert 'omawrite renderer=software platform=wayland' in (home/'app.log').read_text()
    pid = app()['pid']
    exe = os.readlink('/proc/'+str(pid)+'/exe')
    # Close only the saved scratch window, then prove the real Home pin launches
    # a fresh app with the ordinary user HOME and the installed desktop entry.
    ipc('[con_id='+str(original_id)+'] kill')
    wait(lambda: not apps())
    if scene().get('home_selected') != '1':
        swipe()
        if scene().get('home_selected') != '1':
            swipe()
    wait(lambda: scene()['home_selected'] == '1')
    touch.native_touch(device, x, 1154)
    wait(app, 45)
    wait(lambda: scene()['home_selected'] == '0')
    assert app()['id'] != original_id
    result = dict(result='PASS', timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        evidence_class='physical-board-injected-touch-keyboard-native-capture',
        system=target, executable=exe, first_map_seconds=first_map_seconds,
        osk_added_text=osk_added, scratch_text=saved,
        checks=['default Markdown handler opens Omawrite', 'software Wayland launch', 'scratch edit/save', 'real wvkbd surface types through injected touch',
                'keyboard show/hide resize', 'native Open control', 'Save As chooser', 'saved document reopened',
                'Overview/Home return', 'Editor Home pin focuses same window', 'Editor Home pin launches new app'],
        real_finger_acceptance=False,
        expected_theme_background=tomllib.loads(Path('/home/shell/.local/state/omarchy/current/active/theme/colors.toml').read_text())['background'])
    upload('result.json', json.dumps(result, indent=2).encode())
    (root/'result.json').write_text(json.dumps(result))
    print('K230_TRACE_OMAWRITE_PASS', flush=True)
finally:
    keyboard.close()
    keyboard_visibility(False)
