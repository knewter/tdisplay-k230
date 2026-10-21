"""Private theme rollback and named workload adapter for one owned board trial."""
from pathlib import Path
import base64,hashlib,importlib.util,json,os,pwd,shutil,subprocess,sys,time
root=Path(__file__).parent;code=Path('/run/k230-source3-paired12-code-20261021-attempt4');sys.path.insert(0,str(code/'tools'))
s=importlib.util.spec_from_file_location('trial',code/'tools/handheld-theme-trial.py');trial=importlib.util.module_from_spec(s);s.loader.exec_module(trial)
from theme_transaction import _pointer,_public_links
from theme_preferences import _read

def env_now():
 end=time.monotonic()+60
 while time.monotonic()<end:
  try:
   pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip()
   env={k.decode():v.decode() for k,v in (x.split(b'=',1) for x in Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in x)}
   if all(k in env for k in ['K230_THEME_STATE_ROOT','K230_THEME_COMMAND','K230_THEME_DEFAULT_GENERATION','XDG_RUNTIME_DIR']):return env
  except (OSError,ProcessLookupError):pass
  time.sleep(.3)
 raise RuntimeError('configured UI environment did not become ready')
def drop():
 u=pwd.getpwnam('shell');os.setgroups([]);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
def save(path,value):
 with path.open('x') as f:os.fchmod(f.fileno(),0o600);json.dump(value,f,indent=2);f.write('\n')
def call(env,*args):
 p=subprocess.run([env['K230_THEME_COMMAND'],*args,'--json'],env=env,preexec_fn=drop,capture_output=True,text=True,timeout=30)
 if p.returncode:raise RuntimeError('theme command failed; private child output withheld')
 return json.loads(p.stdout)
mode=sys.argv[1];env=env_now();state=Path(env['K230_THEME_STATE_ROOT'])
if mode=='prepare':
 previous=_pointer(state);prefs,_=_read(state);app=trial.app_pointer(state)
 snapshot={'previous':str(previous) if previous else None,'preferences':base64.b64encode(prefs).decode() if prefs else None,'missing_links':[p.name for p in _public_links(state)],'app_appearance':str(app) if app else None}
 assert previous.name=='2e583fb7dc1947e9d444c171'
 save(root/'recovery/theme.private.json',snapshot)
 entries=[e for e in call(env,'list')['themes'] if e['name']=='source3-background-paired12' and e['origin']=='user'];assert len(entries)==1
 p=call(env,'preview',entries[0]['id']);choices={}
 for role,kind in [('static','image'),('video','video')]:
  matches=[x for x in p['backgrounds'] if x['kind']==kind];assert len(matches)==1;choices[role]={'theme_name':'source3-background-paired12','origin':'user','background_id':matches[0]['id']}
 d=json.loads((root/'descriptor.json').read_text());w=code/'workload.json'
 m={'schema':1,'source_revision':d['source_revision'],'system':d['system'],'theme_command':env['K230_THEME_COMMAND'],'capture_command':str(Path('/run/current-system/sw/bin/grim').resolve()),'default_generation':env['K230_THEME_DEFAULT_GENERATION'],'state_root':str(state),'rust_socket':'/run/shell/k230-shell-rust-appearance.sock','deck_socket':'/run/shell/k230-card-appearance.sock','workload':{'id':'cards-shade-static-v1','sha256':hashlib.sha256(w.read_bytes()).hexdigest(),'artifact':str(w)},'themes':{'dark':'retro-82','light':'catppuccin-latte'},'background_trial':{'duration_seconds':12,'interval_seconds':.25,'choices':choices}}
 save(root/'candidate.private.json',m)
 print(json.dumps({'original_generation':previous.name,'preferences_sha256':hashlib.sha256(prefs or b'').hexdigest(),'preferences_bytes':len(prefs or b''),'app_appearance_generation':app.name if app else None,'choices':choices}))
elif mode=='basic':
 m=json.loads((root/'candidate.private.json').read_text());runtime=Path('/run/shell');p=runtime/'source3-paired12-attempt4-candidate.private.json';save(p,m);u=pwd.getpwnam('shell');os.chown(p,u.pw_uid,u.pw_gid)
 r=subprocess.run([sys.executable,str(code/'tools/handheld-theme-trial.py'),'--candidate-manifest',str(p),'--workload','backgrounds','--output',str(runtime/'source3-paired12-attempt4-basic-result'),'--raw-private-dir',str(runtime/'source3-paired12-attempt4-basic-private')],env=env,preexec_fn=drop,capture_output=True,text=True,timeout=110)
 (root/'recovery/basic-command.private.log').write_text(r.stdout+r.stderr)
 result=json.loads((runtime/'source3-paired12-attempt4-basic-result/result.json').read_text());save(Path('/run/k230-source3-paired12-20261021-attempt4/basic-result.json'),result)
 assert r.returncode==0 and result['restoration']=='passed'
 print(json.dumps({'named_background_command_exit':r.returncode,'trial':result['trial'],'restoration':result['restoration']}))
elif mode=='activate':
 role=sys.argv[2];m=json.loads((root/'candidate.private.json').read_text());c=m['background_trial']['choices'][role]
 e=[x for x in call(env,'list')['themes'] if x['name']==c['theme_name'] and x['origin']==c['origin']];assert len(e)==1
 p=call(env,'preview',e[0]['id'],'--background',c['background_id'],'--fit','crop');a=call(env,'activate',e[0]['id'],'--background',c['background_id'],'--fit','crop','--expected-generation',p['generation']);assert a.get('activated') is True
 print(json.dumps({'role':role,'generation':p['generation'],'background_id':c['background_id']}))
elif mode=='restore':
 snap=json.loads((root/'recovery/theme.private.json').read_text());m=json.loads((root/'candidate.private.json').read_text());receipt=json.loads((root/'fixture.private.json').read_text());assert str(state)==m['state_root']
 os.environ.update(env);drop();end=time.monotonic()+45
 while True:
  try:trial.restore(snap,state_root=state,default_generation=Path(m['default_generation']),endpoints=(Path(m['rust_socket']),Path(m['deck_socket'])));break
  except Exception:
   if time.monotonic()>end:raise
   time.sleep(.5)
 prefs,_=_read(state);before=base64.b64decode(snap['preferences']) if snap['preferences'] else None;assert prefs==before
 assert str(_pointer(state))==snap['previous'];app=trial.app_pointer(state);assert (str(app) if app else None)==snap['app_appearance']
 print(json.dumps({'theme_restored':True,'generation':_pointer(state).name,'preferences_sha256':hashlib.sha256(prefs or b'').hexdigest(),'preferences_bytes':len(prefs or b''),'app_appearance_generation':app.name if app else None}))
else:raise RuntimeError('unknown private theme adapter mode')
