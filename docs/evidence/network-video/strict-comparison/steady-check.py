import json,os,pathlib,pwd,socket,subprocess,time
R=pathlib.Path('/run/shell');S=R/'k230-video.pid';LOG=R/'k230-video.log';OUT=pathlib.Path('/run/video-comparison-steady');OUT.mkdir(exist_ok=True)
SESSION=os.environ.get('K230_COMPARE_SESSION','/run/current-system/sw/bin/k230-video-session');U=pwd.getpwnam('shell')
ENV=['XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','K230_PRESENTATION_TRACE=1']
def command(mode):return ['runuser','-u','shell','--','env',*ENV,SESSION,mode]
def proc(pid):
 p=pathlib.Path('/proc')/str(pid);a=p.joinpath('stat').read_text().rsplit(') ',1)[1].split()
 return {'pid':pid,'start':int(a[19]),'uid':p.stat().st_uid,'utime':int(a[11]),'stime':int(a[12]),'rss_pages':int(a[21]),'state':a[0]}
def owned():
 d=json.loads(S.read_text());assert d['uid']==U.pw_uid and d['child']>0
 for k in ('controller','child'):
  p=proc(d[k]);assert p['uid']==d['uid'] and p['start']==d[k+'_start'] and p['state']!='Z'
 return d
class IPC:
 def __init__(self,d):
  self.s=socket.socket(socket.AF_UNIX);self.s.settimeout(3);self.s.connect(str(R/f"k230-video-{d['controller']}.sock"));self.f=self.s.makefile('rwb',buffering=0);self.n=0
 def call(self,cmd):
  self.n+=1;self.f.write((json.dumps({'command':cmd,'request_id':self.n})+'\n').encode());end=time.monotonic()+3
  while time.monotonic()<end:
   line=self.f.readline()
   if not line:raise RuntimeError('IPC closed')
   r=json.loads(line)
   if r.get('request_id')==self.n:return r
  raise RuntimeError('IPC deadline')
 def get(self,key):
  r=self.call(['get_property',key]);return r.get('data') if r.get('error')=='success' else {'error':r.get('error')}
 def close(self):self.f.close();self.s.close()
def stop():subprocess.run(command('stop'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=8)
report={'source':'production session profiles, public BBB; instrumented wlshm presentation','clock_ticks':os.sysconf('SC_CLK_TCK'),'page_size':os.sysconf('SC_PAGE_SIZE'),'session':SESSION,'trials':[]}
stop()
for mode in ('software','mvx'):
 row={'mode':mode,'samples':[]};report['trials'].append(row);p=None;ip=None;offset=LOG.stat().st_size if LOG.exists() else 0
 try:
  p=subprocess.Popen(command('run' if mode=='software' else 'run-mvx'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  end=time.monotonic()+45;d=None
  while time.monotonic()<end:
   try:
    d=owned();ip=IPC(d);pos=ip.get('time-pos')
    if isinstance(pos,(int,float)):break
    ip.close();ip=None
   except (OSError,ValueError,KeyError,AssertionError,RuntimeError):
    if ip:ip.close();ip=None
   time.sleep(.2)
  assert ip is not None and isinstance(pos,(int,float)),'playback readiness timed out'
  row['identity']=d
  argv=pathlib.Path(f"/proc/{d['child']}/cmdline").read_bytes().split(b'\0')
  wanted=b'--vd=h264' if mode=='software' else b'--vd=h264_v4l2m2m,-'
  row['requested_decoder_confirmed']=wanted in argv;assert row['requested_decoder_confirmed'],'trial fell back or used wrong profile'
  row['seek']=ip.call(['seek',45,'absolute+exact']);assert row['seek'].get('error')=='success'
  # Seek is a diagnostic action, outside the shipped controls. Require
  # actual post-seek media progression before the fixed comparison window.
  warm=time.monotonic();base=None;last=None
  while time.monotonic()-warm<30:
   last=ip.get('time-pos')
   if base is None and isinstance(last,(int,float)) and last>=45:base=last
   if isinstance(base,(int,float)) and isinstance(last,(int,float)) and last-base>=3:break
   time.sleep(.2)
  else:raise RuntimeError('post-seek media did not warm up')
  row['warmup']={'wall_seconds':round(time.monotonic()-warm,3),'first_media':base,'last_media':last}
  start=time.monotonic()
  for i in range(8):
   assert owned()==d,'player identity changed'
   sample={'elapsed':round(time.monotonic()-start,3),'player':proc(d['child'])}
   for key in ('time-pos','vid','video-codec','video-format','video-params','container-fps','frame-drop-count','decoder-frame-drop-count','demuxer-cache-duration','paused-for-cache','hwdec-current'):
    sample[key]=ip.get(key)
   row['samples'].append(sample)
   if i<7:time.sleep(max(0,start+(i+1)*5-time.monotonic()))
  positions=[x['time-pos'] for x in row['samples']];assert all(isinstance(x,(float,int)) for x in positions) and positions[-1]-positions[0]>30,'media did not advance30s'
  ip.close();ip=None;stop();row['controller_exit']=p.wait(timeout=8)
  row['state_absent']=not S.exists();row['socket_absent']=not list(R.glob('k230-video-*.sock'));assert row['state_absent'] and row['socket_absent']
  row['result']='pass'
 except Exception as e:row['result']='fail';row['error']=str(e)
 finally:
  if ip:ip.close()
  stop()
  if p:p.wait(timeout=8)
  if LOG.exists():
   with LOG.open('rb') as f:f.seek(offset);data=f.read().decode(errors='replace')
   kept=[line for line in data.splitlines() if 'K230_' in line or line.startswith('VO:') or line.startswith('Exiting...') or line.startswith('Decoder init failed')]
   (OUT/f'{mode}-presentation.log').write_text('\n'.join(kept)+'\n')
  (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 if row['result']!='pass':break
print('VIDEO_COMPARISON',[(r['mode'],r['result']) for r in report['trials']])
raise SystemExit(0 if len(report['trials'])==2 and all(r['result']=='pass' for r in report['trials']) else 1)
