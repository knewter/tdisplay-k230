import json,os,pathlib,socket,subprocess,time,sys
R=pathlib.Path('/run/shell'); STATE=R/'k230-video.pid'; OUT=pathlib.Path('/run/video-control-check.json')
env=['XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','XDG_DATA_DIRS=/run/current-system/sw/share','XDG_CURRENT_DESKTOP=sway','PATH=/nix/store/xqq8bis4yn2099l1h1w2kdd2375vpvmp-xdg-terminal-exec/bin:/nix/store/y5lgjbwdzhp51x1kja5agixhln8qn7j8-foot/bin:/run/current-system/sw/bin']
def user(args,**kw):return subprocess.run(['runuser','-u','shell','--','env',*env,*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kw)
def state():return json.loads(STATE.read_text())
def proc(pid):
 p=pathlib.Path('/proc')/str(pid);f=p.joinpath('stat').read_text().rsplit(') ',1)[1].split()
 return {'pid':pid,'start':int(f[19]),'uid':p.stat().st_uid,'state':f[0],'pgrp':int(f[2])}
def owned(d):
 for key in ['controller','child']:
  p=proc(d[key]);assert p['start']==d[key+'_start'] and p['uid']==d['uid'] and p['state']!='Z'
 return d
def ipc(d,command):
 s=socket.socket(socket.AF_UNIX);s.settimeout(2);s.connect(str(R/('k230-video-%s.sock'%d['controller'])));f=s.makefile('rwb',buffering=0)
 try:
  f.write((json.dumps({'command':command,'request_id':1})+'\n').encode())
  while True:
   r=json.loads(f.readline())
   if r.get('request_id')==1:return r
 finally:f.close();s.close()
def ready(timeout=40):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   d=owned(state());r=ipc(d,['get_property','time-pos'])
   if r.get('error')=='success' and isinstance(r.get('data'),(int,float)):return d,r['data']
  except (OSError,ValueError,KeyError,AssertionError):pass
  time.sleep(.2)
 raise RuntimeError('playback not ready')
def tap(x,y):
 subprocess.run(['/run/inject-tap.sh','/dev/input/event1',str(x),str(y)],check=True,timeout=10);time.sleep(.3)
def clean(d):
 end=time.monotonic()+8
 while time.monotonic()<end:
  live=[]
  for p in pathlib.Path('/proc').glob('[0-9]*'):
   try:
    r=proc(int(p.name))
    if r['pid']==d['controller'] and r['start']==d['controller_start'] or r['pgrp']==d['child']:live.append(r)
   except (OSError,ValueError,IndexError):pass
  sockets=list(R.glob('k230-video-*.sock'))
  if not STATE.exists() and not live and not sockets:return {'state_absent':True,'process_group_absent':True,'socket_absent':True}
  time.sleep(.2)
 raise RuntimeError('video cleanup incomplete')
report={'source':'installed production Apps/Foot/controller','cases':[]}
def save():OUT.write_text(json.dumps(report,indent=2)+'\n')
subprocess.run(['pkill','-x','k230-touch-laun'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for case in ['stop','home','eof']:
 row={'case':case};report['cases'].append(row)
 try:
  row['catalog_launch_exit']=user(['/nix/store/mmc9ag2dasrpp0ph3d890yq5mqcm0pcb-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1/bin/k230-desktop-catalog','launch','k230-video.desktop'],timeout=10).returncode
  assert row['catalog_launch_exit']==0
  d,pos=ready();row['initial_state']=d;row['initial_media_time']=pos
  time.sleep(2);row['next_media_time']=ipc(d,['get_property','time-pos'])['data'];assert row['next_media_time']>pos
  if case=='eof':
   log_offset=(R/'k230-video.log').stat().st_size
   duration=ipc(d,['get_property','duration'])['data'];row['duration']=duration
   row['seek']=ipc(d,['seek',max(0,duration-2),'absolute+exact'])
   end=time.monotonic()+25
   while STATE.exists() and time.monotonic()<end:time.sleep(.2)
   assert not STATE.exists(),'natural EOF did not finish'
   # Public profile log only: retain the reason, never a whole log or arbitrary URL.
   row['natural_eof_marker']='Exiting... (End of file)' in (R/'k230-video.log').read_bytes()[log_offset:].decode(errors='replace')
   assert row['natural_eof_marker']
  else:
   tap(245,25);tap(185 if case=='stop' else 295,25)
  row['cleanup']=clean(d)
  if case=='home':
   snap=json.loads(subprocess.check_output([sys.executable,'/run/focus-snapshot.py'],text=True));row['focused_apps']=[w['app_id'] for w in snap['windows'] if w['focused']];assert row['focused_apps']==['k230-terminal']
  row['result']='pass'
 except Exception as e:row['result']='fail';row['error']=str(e)
 finally:
  save();user(['/run/current-system/sw/bin/k230-video-session','stop'],timeout=8)
 if row['result']!='pass':break
print('VIDEO_CONTROLS_DONE',[(r['case'],r['result']) for r in report['cases']])
