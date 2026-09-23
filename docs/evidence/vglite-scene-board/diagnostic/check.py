#!/usr/bin/env python3
import datetime,json,os,pathlib,socket,struct,subprocess,time
OUT=pathlib.Path('/run/gpu-diagnostic-evidence');OUT.mkdir(exist_ok=True)
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
SWAY='/nix/store/a78y0w6zaiyy86dhixgvdfalcj8b5bsc-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
CLIENT='/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client'
result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evidence_class':'board synthetic scene diagnostic; no real finger or optical claim','source_revision':'1b155b621303dc78c50a6ad1df224eafe5ce30fa','compositor':SWAY,'client':CLIENT,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'normal_system':os.path.realpath('/run/current-system'),'captures':[]}
def ipc(path,kind=4):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(2);s.connect(str(path));s.sendall(b'i3-ipc'+struct.pack('=II',0,kind))
  def read(n):
   data=b''
   while len(data)<n:
    c=s.recv(n-len(data));assert c;data+=c
   return data
  h=read(14);return json.loads(read(struct.unpack('=II',h[6:])[0]))
def nodes(t):
 yield t
 for c in t.get('nodes',[])+t.get('floating_nodes',[]):yield from nodes(c)
log=(OUT/'raw-private.log').open('w');os.chmod(OUT/'raw-private.log',0o600)
proc=subprocess.Popen([PYTHON,'/run/vglite-root-scene-trial.py','--seconds','25','--compositor',SWAY,'--',CLIENT,'--app-id','k230.card.one','--duration','12'],stdout=log,stderr=log)
try:
 deadline=time.monotonic()+18; runtime=None
 while time.monotonic()<deadline and proc.poll() is None:
  for d in pathlib.Path('/run').glob('k230-vglite-trial-*'):
   try:
    if any(n.get('app_id')=='k230.card.one' for n in nodes(ipc(d/'control/sway-ipc.sock'))):runtime=d;break
   except (OSError,AssertionError,ValueError):pass
  if runtime:break
  time.sleep(.2)
 if runtime:
  env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime/'display'),WAYLAND_DISPLAY=str(runtime/'display/wayland-1'))
  for name in ['scene-first','scene-later']:
   subprocess.run(['grim',str(OUT/(name+'.png'))],env=env,check=True,timeout=8);result['captures'].append(name);time.sleep(1)
  state=pathlib.Path('/sys/kernel/debug/dri/0/state').read_text();result['scanout_format']=[s.strip() for s in state.splitlines() if 'format=' in s]
  result['sway_processes']=subprocess.check_output(['pgrep','-x','sway'],text=True).split()
 else:result['scene_mapped']=False
 result['trial_exit']=proc.wait(timeout=45)
finally:
 if proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=40)
  except subprocess.TimeoutExpired:result['controller_still_running']=True
 log.close()
 result['normal_shell_active']=subprocess.run(['systemctl','is-active','--quiet','shell']).returncode==0
 result['seatd_active']=subprocess.run(['systemctl','is-active','--quiet','seatd']).returncode==0
 raw=(OUT/'raw-private.log').read_text()
 records=[line[line.index('VG-Lite '):] for line in raw.splitlines() if 'VG-Lite decision v=1 ' in line or 'VG-Lite operation v=1 ' in line]
 (OUT/'decisions.log').write_text('\n'.join(records)+'\n')
 result['gpu_full_frames']=raw.count('VG-Lite full frame submitted')
 result['pixman_replayed_frames']=raw.count('VG-Lite full pass replayed with Pixman')
 result['restoration_marker']='RESTORED shell.service active; diagnostic compositor cgroup stopped' in raw
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
