import json,os,pathlib,pwd,socket,stat,subprocess,time
R=pathlib.Path('/run/shell'); S=R/'k230-video.pid'; DEV=pathlib.Path('/dev/video0'); OUT=pathlib.Path('/run/video-recovery-check-v2.json')
U=pwd.getpwnam('shell'); SESSION='/nix/store/krqszp7x14mi9xyyz0k6bp2p3ywvhkyn-k230-video-session/bin/k230-video-session'
ENV=['XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock']
def command(mode,extra=()):return ['runuser','-u','shell','--','env',*ENV,*extra,SESSION,mode]
def proc(pid):
 p=pathlib.Path('/proc')/str(pid);a=p.joinpath('stat').read_text().rsplit(') ',1)[1].split()
 return {'pid':pid,'start':int(a[19]),'pgrp':int(a[2]),'uid':p.stat().st_uid,'state':a[0]}
def state():
 try:
  d=json.loads(S.read_text());assert d['uid']==U.pw_uid
  for k in ('controller','child'):
   if d[k]:
    p=proc(d[k]);assert p['uid']==U.pw_uid and p['start']==d[k+'_start'] and p['state']!='Z'
  return d
 except (OSError,ValueError,KeyError,AssertionError):return None
def ipc(d,key='time-pos'):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(2);s.connect(str(R/f"k230-video-{d['controller']}.sock"))
  with s.makefile('rwb',buffering=0) as f:
   f.write((json.dumps({'command':['get_property',key],'request_id':1})+'\n').encode())
   end=time.monotonic()+2
   while time.monotonic()<end:
    line=f.readline()
    if not line:raise RuntimeError('IPC closed')
    r=json.loads(line)
    if r.get('request_id')==1:
     assert r.get('error')=='success'
     return r['data']
  raise RuntimeError('IPC deadline')
def clean(identities):
 live=[]
 for path in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   p=proc(int(path.name))
   if any((p['pid']==d['controller'] and p['start']==d['controller_start']) or (d['child'] and p['pgrp']==d['child']) for d in identities):live.append(p)
  except (OSError,ValueError,IndexError):pass
 return {'state_absent':not S.exists(),'socket_absent':not list(R.glob('k230-video-*.sock')),'groups_absent':not live}
def stop():subprocess.run(command('stop'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8,check=True)
def remember(d,ids):
 if d and d not in ids:ids.append(d)
report={'session':SESSION,'provenance':'physical board; source-built transferred controller; root fault injection; shell UID player','cases':[]}
assert os.geteuid()==0
stop()
for case in ('network-error','mvx-init-fallback'):
 row={'case':case};report['cases'].append(row);ids=[];p=None;playlist=R/'k230-video-recovery.playlist';saved=None;errfile=None
 try:
  if case=='network-error':
   assert not playlist.exists();playlist.write_text('http://127.0.0.1:9/unavailable.mpd\n');os.chown(playlist,U.pw_uid,U.pw_gid);playlist.chmod(0o600)
   p=subprocess.Popen(command('run',[f'K230_VIDEO_URL_FILE={playlist}']),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   end=time.monotonic()+45
   while p.poll() is None and time.monotonic()<end:remember(state(),ids);time.sleep(.05)
   row['spontaneous_exit']=p.poll();assert row['spontaneous_exit'] is not None and row['spontaneous_exit']!=0,'no spontaneous failure'
   row['cleanup']=clean(ids);row['playlist_removed']=not playlist.exists()
   assert ids and all(row['cleanup'].values()) and row['playlist_removed']
  else:
   st=DEV.stat();saved=(stat.S_IMODE(st.st_mode),st.st_uid,st.st_gid);DEV.chmod(0)
   row.update(mvx_seen=False,software_seen=False)
   errfile=open('/run/video-recovery-controller.stderr','w+b');os.chmod(errfile.name,0o600)
   p=subprocess.Popen(command('run-mvx'),stdout=subprocess.DEVNULL,stderr=errfile)
   end=time.monotonic()+45;first=None;software_id=None
   while time.monotonic()<end and p.poll() is None:
    d=state();remember(d,ids)
    if d and d['child']:
     try:argv=pathlib.Path(f"/proc/{d['child']}/cmdline").read_bytes().split(b'\0')
     except OSError:argv=[]
     if b'--vd=h264_v4l2m2m,-' in argv:row['mvx_seen']=True
     if b'--vd=h264' in argv:
      row['software_seen']=True
      if saved:os.chown(DEV,saved[1],saved[2]);DEV.chmod(saved[0]);saved=None
      try:pos=ipc(d)
      except (OSError,ValueError,AssertionError,RuntimeError):pos=None
      if pos is not None:
       if first is None:first=(time.monotonic(),pos);software_id=d.copy()
       elif time.monotonic()-first[0]>=2:
        assert d==software_id,'software player identity changed'
        row['media_times']=[first[1],pos];assert pos>first[1]
        row['video_params']=ipc(d,'video-params');row['vid']=ipc(d,'vid');row['video_codec']=ipc(d,'video-codec')
        assert row['vid']==6 and row['video_params']['w']==480 and row['video_params']['h']==270
        break
    time.sleep(.1)
   assert row['mvx_seen'] and row['software_seen'] and 'media_times' in row,'fallback playback not proven'
   stop();p.wait(timeout=8);row['cleanup']=clean(ids);assert all(row['cleanup'].values())
   errfile.seek(0);row['fallback_marker']=b'MVX decoder failed; falling back to software H.264' in errfile.read(8192)
   assert row['fallback_marker']
  row['identities']=ids;row['result']='pass'
 except Exception as e:row['result']='fail';row['error']=str(e);row['identities']=ids
 finally:
  if saved:os.chown(DEV,saved[1],saved[2]);DEV.chmod(saved[0])
  try:stop()
  except Exception:row['safety_cleanup_error']=True
  if p:
   try:p.wait(timeout=8)
   except subprocess.TimeoutExpired:row['unreaped_controller']=True
  if errfile:errfile.close()
  OUT.write_text(json.dumps(report,indent=2)+'\n')
 if row['result']!='pass':break
print('RECOVERY_RESULTS',[(r['case'],r['result']) for r in report['cases']])
raise SystemExit(0 if len(report['cases'])==2 and all(r['result']=='pass' for r in report['cases']) else 1)
