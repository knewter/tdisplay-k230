import json,os,pathlib,socket,time
out=pathlib.Path('/run/video-installed-observation.json')
state=pathlib.Path('/run/shell/k230-video.pid')
start=time.monotonic(); samples=[]
props=['time-pos','vid','video-codec','video-format','video-params','container-fps','estimated-vf-fps','frame-drop-count','decoder-frame-drop-count','demuxer-cache-duration','paused-for-cache','pause','eof-reached','hwdec-current']
def proc(pid):
 p=pathlib.Path('/proc')/str(pid); f=p.joinpath('stat').read_text().rsplit(') ',1)[1].split()
 return {'pid':pid,'uid':p.stat().st_uid,'state':f[0],'pgrp':int(f[2]),'start':int(f[19]),'utime':int(f[11]),'stime':int(f[12]),'rss_pages':int(f[21])}
for index in range(21):
 sample={'elapsed':round(time.monotonic()-start,3)}
 try:
  d=json.loads(state.read_text()); c=proc(d['controller']); p=proc(d['child'])
  assert c['start']==d['controller_start'] and p['start']==d['child_start']
  assert c['uid']==p['uid']==d['uid'] and c['state']!='Z' and p['state']!='Z'
  sample.update(controller=c,player=p)
  s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/shell/k230-video-%d.sock'%d['controller']);f=s.makefile('rwb',buffering=0)
  for req,key in enumerate(props,1):
   f.write((json.dumps({'command':['get_property',key],'request_id':req})+'\n').encode())
   while True:
    r=json.loads(f.readline())
    if r.get('request_id')==req:break
   sample[key]=r.get('data') if r.get('error')=='success' else {'error':r.get('error')}
  f.close();s.close()
 except Exception as e:sample['error']=type(e).__name__
 samples.append(sample)
 out.write_text(json.dumps({'clock_ticks':os.sysconf('SC_CLK_TCK'),'page_size':os.sysconf('SC_PAGE_SIZE'),'samples':samples},indent=2)+'\n')
 if index<20:time.sleep(max(0,start+(index+1)*5-time.monotonic()))
print('VIDEO_OBSERVATION_DONE',len(samples))
