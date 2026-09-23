#!/usr/bin/env python3
"""Installed-image, injected-touch regression. Run only on the reserved board."""
import datetime, hashlib, json, os, pathlib, signal, socket, subprocess, sys, time
sys.path.insert(0, '/run')
import rollback_check as pixels

os.environ.update(XDG_RUNTIME_DIR='/run/shell', WAYLAND_DISPLAY='wayland-1', SWAYSOCK='/run/shell/sway-ipc.sock')
OUT=pathlib.Path('/run/card-board-restore'); OUT.mkdir(exist_ok=True)
result={'provenance':'injected-touch on physical board; no real-finger claim', 'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks':{}}
result['system']=os.path.realpath('/run/current-system')
result['boot_id']=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def command(args):
    return subprocess.check_output(args, text=True, timeout=15)
def wait(test,label,seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=test()
            if value:return value
        except (OSError,ValueError,subprocess.CalledProcessError):pass
        time.sleep(.25)
    raise RuntimeError(label)
def record(label):
    result['checks'][label]=True
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',label,flush=True)
def tap(x,y,x2=None,y2=None):
    args=['/run/inject-tap.sh','/dev/input/event1',str(x),str(y)]
    if x2 is not None:args += [str(x2),str(y2)]
    subprocess.run(args,check=True,timeout=12);time.sleep(.4)
def nodes():
    root=json.loads(command(['swaymsg','-t','get_tree','-r']))
    def walk(n):
        yield n
        for c in n.get('nodes',[])+n.get('floating_nodes',[]):yield from walk(c)
    return list(walk(root))
def focused(app):return any(n.get('app_id')==app and n.get('focused') for n in nodes())
def launcher():
    p=subprocess.run(['pgrep','-x','k230-touch-laun'],capture_output=True,text=True)
    return int(p.stdout.split()[0]) if p.returncode==0 else None
def shot(name):
    path=OUT/(name+'.png');subprocess.run(['grim',str(path)],check=True,timeout=8)
    return pixels.png_pixels(path)
def canvas(name):return hashlib.sha256(pixels.canvas_bytes(shot(name))).hexdigest()
def bar():
    path=OUT/'bar.png'
    subprocess.run(['grim','-g','0,0 568x56',str(path)],check=True,timeout=8)
    return hashlib.sha256(path.read_bytes()).hexdigest()
def apps():
    tap(110,25);wait(launcher,'Apps launcher missing');time.sleep(.4)
def close_apps():tap(280,1165);wait(lambda:not launcher(),'Back did not close Apps')
def ipc_property(name):
    state=json.loads(pathlib.Path('/run/shell/k230-video.pid').read_text())
    path='/run/shell/k230-video-'+str(state['controller'])+'.sock'
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(2);s.connect(path);s.sendall((json.dumps({'command':['get_property',name],'request_id':43})+'\n').encode())
        stream=s.makefile('r')
        for line in stream:
            reply=json.loads(line)
            if reply.get('request_id')==43:return reply.get('data')
def video_present():return any(n.get('app_id')=='k230-video-software' for n in nodes())

try:
    for service in ('shell','seatd','k230-wifi'):
        assert command(['systemctl','is-active',service]).strip()=='active'
    record('normal_services_active')
    subprocess.run(['pkill','-USR1','-x','wvkbd-mobintl'],check=True)
    apps(); first=canvas('apps-first')
    tap(470,1165);assert canvas('apps-next')!=first
    tap(105,1165);assert canvas('apps-previous')==first
    record('apps_next_previous')
    tap(370,25);assert pixels.launcher_bounds(shot('keyboard-visible'))[1]==776
    tap(370,25);assert pixels.launcher_bounds(shot('keyboard-hidden'))[1]==1176
    record('keyboard_toggle_preserves_apps')
    tap(280,320);wait(lambda:focused('k230-terminal'),'Terminal not focused')
    shot('terminal');record('terminal_app')
    apps();close_apps();record('apps_back')
    result['status']='PASS'
except Exception as e:
    result['status']='FAIL';result['error']=type(e).__name__+': '+str(e);raise
finally:
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
