from pathlib import Path
import os,subprocess,json,pwd,time,sys,socket,struct,shlex,hashlib
stage=Path('/run/shell/source3-background-trial-20261021');py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip()
env={k.decode():v.decode() for k,v in (v.split(b'=',1) for v in Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in v)}
u=pwd.getpwnam('shell')
def drop():os.setgroups([]);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
def ipc(c='',kind=0):
 p=c.encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(20);s.connect('/run/shell/sway-ipc.sock');s.sendall(b'i3-ipc'+struct.pack('=II',len(p),kind)+p)
  def read(n):
   b=b''
   while len(b)<n:
    q=s.recv(n-len(b));assert q;b+=q
   return b
  n,_=struct.unpack('=II',read(14)[6:]);v=json.loads(read(n))
 if kind==0:assert all(x.get('success') for x in v)
 return v
def theme(*a):
 p=subprocess.run([env['K230_THEME_COMMAND'],*a,'--json'],capture_output=True,text=True,env=env,preexec_fn=drop,timeout=30)
 if p.returncode:raise RuntimeError('theme request failed')
 return json.loads(p.stdout)
def status():return json.loads(Path('/run/shell/k230-wallpaper-status.json').read_text())
def waitstate(want,timeout=12):
 until=time.monotonic()+timeout
 while time.monotonic()<until:
  v=status()
  if v['state']==want:return v
  time.sleep(.1)
 raise RuntimeError('wallpaper did not reach '+want)
def apps(n):
 out=[n['app_id']] if n.get('app_id') else []
 for x in n.get('nodes',[])+n.get('floating_nodes',[]):out+=apps(x)
 return out
out=stage/'cards';out.mkdir(mode=0o700)
meta={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'arms':[],'restoration':'pending','interaction_provenance':'injected','physical_contact':'UNVERIFIED'}
assert set(apps(ipc(kind=4)))=={'k230-terminal'}
m=json.loads((stage/'candidate.json').read_text())
meta['candidate']=m;meta['original_generation']=str((Path(m['state_root'])/'active').resolve())
assert Path(meta['original_generation']).name=='2e583fb7dc1947e9d444c171'
try:
 for role in ['static','video']:
  ipc('card_shell home');choice=m['background_trial']['choices'][role]
  entry=[x for x in theme('list')['themes'] if x['name']==choice['theme_name'] and x['origin']==choice['origin']];assert len(entry)==1
  v=theme('preview',entry[0]['id'],'--background',choice['background_id'],'--fit','crop')
  a=theme('activate',entry[0]['id'],'--background',choice['background_id'],'--fit','crop','--expected-generation',v['generation']);assert a.get('activated') is True
  time.sleep(2)
  arm={'role':role,'generation':v['generation'],'before':status(),'runs':[]};meta['arms'].append(arm)
  (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
  if role=='video':
   arm['playing']=waitstate('playing')
   assert 'k230.background.cover' not in apps(ipc(kind=4))
   try:
    ipc('exec foot --app-id=k230.background.cover --title=Background-cover sh -c '+shlex.quote("printf '\\033[44m\\033[2J\\033[HCovered background trial\\n'; sleep 60"))
    until=time.monotonic()+15
    while 'k230.background.cover' not in apps(ipc(kind=4)):
     assert time.monotonic()<until;time.sleep(.1)
    ipc('card_shell back');ipc('[app_id="k230.background.cover"] fullscreen enable')
    arm['covered_before']=waitstate('paused-covered');time.sleep(2);arm['covered_after']=status()
    arm['covered_counters_stopped']=all(arm['covered_before'][k]==arm['covered_after'][k] for k in ['frames_decoded','frames_submitted','frame_callbacks'])
   finally:ipc('[app_id="k230.background.cover"] kill');ipc('card_shell home')
   arm['uncovered_before']=waitstate('playing');time.sleep(2);arm['uncovered_after']=status()
  sampler_code="import sys,json;sys.path.insert(0,"+repr(str(stage/'tools'))+");from theme_background_metrics import measure;print(json.dumps(measure(60,.25)))"
  sampler=subprocess.Popen([py,'-c',sampler_code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,preexec_fn=drop,text=True)
  try:
   for cards in [1,3]:
    dest=out/(role+'-'+str(cards)+'-cards')
    p=subprocess.run([py,str(stage/'tools/background-collect-cards.py'),'full',str(dest),'6',m['source_revision'],m['system'],str(cards)],capture_output=True,text=True,timeout=90)
    (out/(role+'-'+str(cards)+'-collector.private.log')).write_text(p.stdout+p.stderr)
    arm['runs'].append({'cards':cards,'exit':p.returncode,'directory':str(dest),'status_after':status()})
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    if p.returncode:raise RuntimeError('card collection failed')
  finally:
   sampleout,sampleerr=sampler.communicate(timeout=65)
   (out/(role+'-resources.private.log')).write_text(sampleout+sampleerr)
   if sampler.returncode==0:arm['resources']=json.loads(sampleout)
   else:arm['resource_error']=sampler.returncode
  arm['after']=status()
  (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
finally:
 code="import sys,json;from pathlib import Path;sys.path.insert(0,"+repr(str(stage/'tools'))+");import importlib.util;s=importlib.util.spec_from_file_location('trial',"+repr(str(stage/'tools/handheld-theme-trial.py'))+");t=importlib.util.module_from_spec(s);s.loader.exec_module(t);m=json.loads(Path("+repr(str(stage/'candidate.json'))+").read_text());v=json.loads(Path("+repr(str(stage/'raw-basic/recovery.json'))+").read_text());t.restore(v,state_root=Path(m['state_root']),default_generation=Path(m['default_generation']),endpoints=(Path(m['rust_socket']),Path(m['deck_socket'])))"
 p=subprocess.run([py,'-c',code],capture_output=True,text=True,env=env,preexec_fn=drop,timeout=35)
 (out/'restore.private.log').write_text(p.stdout+p.stderr)
 meta['restoration']='passed' if p.returncode==0 and (Path(m['state_root'])/'active').resolve()==Path(meta['original_generation']) else 'FAILED'
 ipc('card_shell home');meta['restored_status']=status();meta['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
 (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
 print(json.dumps(meta))
