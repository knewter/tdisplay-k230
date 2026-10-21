from pathlib import Path
import subprocess,time,json,shlex,select,datetime,hashlib
b=Path(__file__).parent;out=b/'splash-dma-camera-calibration';out.mkdir(mode=0o700);ssh=['ssh','-F','/home/jadams/tmp/k230-coordination/ssh_config.private','k230'];py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3';v={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'board_lease_pid':2427792,'purpose':'Empirical optical timestamp check using reversible panel-brightness transitions on accepted ordinary session; not a boot defect/fix proof.'};camera=None;remote=None
ctl=lambda *a:subprocess.run(['v4l2-ctl','--device=/dev/video0',*a],check=True,capture_output=True,text=True).stdout
try:
 ctl('--set-fmt-video=width=960,height=720,pixelformat=MJPG','--set-parm=30')
 ctl('--set-ctrl=auto_exposure=1,exposure_dynamic_framerate=0,focus_automatic_continuous=0,white_balance_automatic=0')
 ctl('--set-ctrl=exposure_time_absolute=100,gain=0')
 v['camera_controls']=ctl('--get-fmt-video','--get-parm','--list-ctrls')
 log=(out/'camera.log').open('w');camera=subprocess.Popen([str(b/'capture-boot-camera'),'/dev/video0',str(out/'camera'),'18','128','600'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  if camera.poll() is not None:raise RuntimeError('camera failed before calibration')
  p=out/'camera/frames.jsonl'
  if p.exists() and p.read_text().count('"kind":"frame"')>=45:break
  time.sleep(.1)
 else:raise RuntimeError('camera readiness')
 code='''from pathlib import Path
import time,json,sys
p=Path('/sys/class/backlight/canaan-dsi-backlight/brightness');old=p.read_text().strip();print(json.dumps(dict(ready=True,original=old)),flush=True)
try:
 for line in sys.stdin:
  value=int(line);m0=time.monotonic_ns();r0=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
  if value>=0:p.write_text(str(value))
  r1=time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW);m1=time.monotonic_ns()
  print(json.dumps(dict(value=value,before_raw_ns=r0,after_raw_ns=r1,before_monotonic_ns=m0,after_monotonic_ns=m1,readback=p.read_text().strip())),flush=True)
finally:p.write_text(old)
'''
 remote=subprocess.Popen(ssh+[py+' -u -c '+shlex.quote(code)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/'remote.private.stderr').open('w'),text=True)
 def receive():
  if not select.select([remote.stdout],[],[],8)[0]:raise RuntimeError('remote timeout')
  return json.loads(remote.stdout.readline())
 v['remote_ready']=receive();assert v['remote_ready']['original']=='255';v['samples']=[]
 def sample(value):
  h0=time.monotonic_ns();remote.stdin.write(str(value)+'\n');remote.stdin.flush();d=receive();h1=time.monotonic_ns();d.update(host_before_ns=h0,host_after_ns=h1);v['samples'].append(d)
 for _ in range(20):sample(-1)
 for value in [32,255,32,255,32,255,32,255]:
  sample(value);time.sleep(1)
 for _ in range(20):sample(-1)
 remote.stdin.close();assert remote.wait(timeout=10)==0;remote=None
 v['camera_exit']=camera.wait(timeout=25);camera=None;log.close();rows=[json.loads(x) for x in (out/'camera/frames.jsonl').read_text().splitlines()];v['camera_summary']=rows[-1];assert v['camera_exit']==0 and rows[-1]['capture_complete'];v['status']='CAPTURED_PENDING_OPTICAL_ANALYSIS';v['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
finally:
 if remote is not None:
  if remote.poll() is None:remote.stdin.close();remote.wait(timeout=10)
 if camera is not None and camera.poll() is None:camera.terminate();camera.wait(timeout=10)
 # Explicit independent restoration even if the sample subprocess failed.
 r=subprocess.run(ssh+["printf 255 > /sys/class/backlight/canaan-dsi-backlight/brightness; cat /sys/class/backlight/canaan-dsi-backlight/brightness"],capture_output=True,text=True,timeout=15);v['brightness_restoration']={'exit':r.returncode,'readback':r.stdout.strip()}
 ctl('--set-ctrl=auto_exposure=3,exposure_dynamic_framerate=1,focus_automatic_continuous=1,white_balance_automatic=1');ctl('--set-fmt-video=width=640,height=480,pixelformat=YUYV','--set-parm=30');v['restored_camera_controls']=ctl('--get-fmt-video','--get-parm','--list-ctrls');(out/'manifest.json').write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps({k:v[k] for k in ['status','camera_exit','camera_summary','brightness_restoration']},indent=2))
