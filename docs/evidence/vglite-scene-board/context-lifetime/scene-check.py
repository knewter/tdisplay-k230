#!/usr/bin/env python3
import datetime,json,os,pathlib,socket,struct,subprocess,time,sys
FORCE='--force-pixman' in sys.argv
ROUND=sys.argv[sys.argv.index('--round')+1] if '--round' in sys.argv else '1'
assert ROUND in ('1','2','3')
OUT=pathlib.Path('/run/gpu-context-'+('pixman' if FORCE else 'gpu')+'-'+ROUND);OUT.mkdir(exist_ok=False)
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
SWAY='/nix/store/n7gh7bnvx2c2rifrcz4vysyyhvry792b-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
CLIENT='/nix/store/bxiz9zkb33m4v97gkgzx91aswfm7cf9f-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client'
result={'round':int(ROUND),'profile_enabled':True,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'evidence_class':'board synthetic scene diagnostic; no real finger or optical claim','forced_pixman':FORCE,'source_revision':'f656f199059af0924f6e84411f283ea2bc5df136','compositor':SWAY,'client':CLIENT,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'normal_system':os.path.realpath('/run/current-system'),'captures':[]}
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
proc=subprocess.Popen([PYTHON,'/run/vglite-root-scene-trial.py','--seconds','45','--profile','--compositor',SWAY]+(['--force-pixman'] if FORCE else [])+['--',CLIENT,'--app-id','k230.card.one','--duration','30'],stdout=log,stderr=log)
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
  # Require an actually captured recognizable parent, not merely IPC map.
  ready=False
  for attempt in range(12):
   capture=OUT/'prerequisite.ppm'
   subprocess.run(['grim','-t','ppm',str(capture)],env=env,check=True,timeout=8)
   header=capture.read_bytes().split(b'\n',3)
   if len(header)!=4 or header[:3]!=[b'P6',b'568 1232',b'255']:raise RuntimeError('unexpected native capture layout')
   pixels=header[3]
   if len(pixels)!=568*1232*3:raise RuntimeError('incomplete native capture')
   samples=[pixels[(y*568+x)*3:(y*568+x)*3+3] for y in (400,700,1000) for x in (100,300,500)]
   if sum(b>g>r and g>20 for r,g,b in samples)>=6:ready=True;break
   time.sleep(.2)
  result['visible_frame_prerequisite']=ready
  if not ready:
   subprocess.run(['grim',str(OUT/'no-visible-scene.png')],env=env,check=True,timeout=8)
   result['captures'].append('no-visible-scene');raise RuntimeError('recognizable scene never reached native capture')
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
 costs=[line[line.index('VG-Lite cost '):] for line in raw.splitlines() if 'VG-Lite cost v=1 ' in line]
 (OUT/'costs.log').write_text('\n'.join(costs)+'\n')
 result['gpu_full_frames']=raw.count('VG-Lite full frame submitted')
 result['pixman_replayed_frames']=raw.count('VG-Lite full pass replayed with Pixman')
 result['restoration_marker']='RESTORED shell.service active; diagnostic compositor cgroup stopped' in raw
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
