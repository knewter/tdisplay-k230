#!/usr/bin/env python3
"""Installed-image, injected-touch regression. Run only on the reserved board."""
import datetime, hashlib, json, os, pathlib, signal, socket, subprocess, sys, time
sys.path.insert(0, '/run')
import rollback_check as pixels

os.environ.update(XDG_RUNTIME_DIR='/run/shell', WAYLAND_DISPLAY='wayland-1', SWAYSOCK='/run/shell/sway-ipc.sock')
OUT=pathlib.Path('/run/final-shell-check'); OUT.mkdir(exist_ok=True)
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
    if '--video-only' not in sys.argv:
        for service in ('shell','seatd','k230-wifi'):
            assert command(['systemctl','is-active',service]).strip()=='active'
        record('normal_services_active')
        subprocess.run(['pkill','-USR1','-x','wvkbd-mobintl'],check=True)
        apps(); first=canvas('apps-first');home_bar=bar()
        tap(470,1165);assert canvas('apps-next')!=first
        tap(105,1165);assert canvas('apps-previous')==first
        record('apps_next_previous')
        apps_header=pixels.header_hash(shot('apps-before-help'))
        tap(280,995)
        # Help is distinguished from Applications by its rendered header.
        help_header=pixels.header_hash(shot('help-header'))
        assert help_header!=apps_header
        tap(280,1165);assert pixels.header_hash(shot('help-back'))!=help_header
        record('help_back_returns_apps')
        tap(280,320);wait(lambda:focused('k230-terminal'),'Terminal not focused')
        record('terminal_app')
        apps();tap(280,550);wait(lambda:focused('k230-monitor'),'Monitor not focused')
        record('monitor_app')
        apps();tap(370,25);assert pixels.launcher_bounds(shot('keyboard-visible'))[1]==776
        tap(370,25);assert pixels.launcher_bounds(shot('keyboard-hidden'))[1]==1176
        record('keyboard_toggle_preserves_apps')
        apps_header=pixels.header_hash(shot('before-overview'))
        tap(284,460,284,210);assert pixels.header_hash(shot('overview'))!=apps_header
        tap(284,300,284,600);assert pixels.header_hash(shot('overview-back'))==apps_header
        close_apps();record('overview_up_down_back')
        tap(500,25);wait(lambda:bar()!=home_bar,'System bar did not appear');system_bar=bar()
        shot('system');tap(90,25);wait(lambda:bar()!=system_bar,'Reboot confirmation did not appear')
        shot('reboot-confirm');tap(430,25);wait(lambda:bar()==home_bar,'Cancel did not return to home bar')
        # Cancel returns to the normal bar without rebooting.
        assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==result['boot_id']
        apps();close_apps();record('system_confirmation_cancel_apps')
        apps();failed_pid=launcher()
        subprocess.run(['prlimit','--pid',str(failed_pid),'--as=1'],check=True)
        tap(470,1165);wait(lambda:not pathlib.Path('/proc/'+str(failed_pid)).exists(),'Constrained launcher did not exit')
        apps();recovered=canvas('after-render-failure')
        tap(470,1165);assert canvas('recovered-next')!=recovered
        tap(105,1165);assert canvas('recovered-previous')==recovered
        close_apps();record('forced_render_allocation_failure_apps_buttons_back_recovery')
    else:
        prior=json.loads((OUT/'result.json').read_text())
        assert prior['boot_id']==result['boot_id']
        result['checks']=prior['checks']
        result['resumed_video_only']=True
        home_bar=bar()
    for action,x in [('stop',185),('back',510),('home',295)]:
        apps();tap(470,1165);tap(470,1165);tap(280,550)
        wait(video_present,'Video surface missing',35)
        wait(lambda:(ipc_property('time-pos') or 0)>1,'Video media time did not advance',45)
        state=json.loads(pathlib.Path('/run/shell/k230-video.pid').read_text())
        result.setdefault('video_sessions',{})[action]=state
        tap(245,25);wait(lambda:bar()!=home_bar,'Windows controls did not appear');tap(x,25)
        wait(lambda:not pathlib.Path('/run/shell/k230-video.pid').exists(),'Video state persisted',12)
        assert not list(pathlib.Path('/run/shell').glob('k230-video-*.sock'))
        assert not video_present()
        for key in ('controller','child'):
            if isinstance(state.get(key),int):wait(lambda:not pathlib.Path('/proc/'+str(state[key])).exists(),'Video process persisted: '+key,12)
        if action=='home':wait(lambda:focused('k230-terminal'),'Home failed to focus Terminal')
        wait(lambda:bar()==home_bar,'Video recovery did not return to home bar')
        record('video_apps_launch_'+action+'_cleanup')
    for service in ('shell','seatd','k230-wifi'):
        assert command(['systemctl','is-active',service]).strip()=='active'
    apps();close_apps();record('post_video_apps_back_services')
    result['result']='pass'
except Exception as error:
    result['result']='fail';result['error_type']=type(error).__name__;result['error']=str(error)
    raise
finally:
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
