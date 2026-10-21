"""Guarded paired still/video one/three-card trial at quiet12ms; 8.14 ms real-finger drag steps."""
from pathlib import Path
import hashlib,json,os,re,shlex,shutil,stat,subprocess,sys,time
root=Path(__file__).parent;sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tools'))
from cadence_audit import identity,ipc
from theme_background_metrics import measure
out=Path('/run/k230-touchrate-20261021');out.mkdir(mode=0o700)
m=json.loads((root/'descriptor.json').read_text());before=identity();assert before['system']==before['profile']==m['system'] and before['sway_sha256']==m['normal_sha256']
assert before['apps']==['k230-terminal'] and before['wallpaper']['state']=='still' and before['outputs'][0]['max_render_time']==8 and before['outputs'][0]['transform']=='270'
keys=['StandardOutput','StandardError','LogLevelMax','LogRateLimitIntervalUSec','LogRateLimitBurst']
def props():return {k:subprocess.check_output(['systemctl','show','shell.service','-p',k,'--value'],text=True).strip() for k in keys}
original_props=props();assert original_props['StandardOutput']=='journal' and original_props['StandardError']=='inherit'
override=Path('/run/systemd/system/shell.service.d/98-touchrate.conf');assert not override.exists()
for n in ['94-source3-cadence-timing.conf','95-source3-log-destination.conf','96-source3-quiet-cadence.conf','97-source3-paired12.conf']:assert not (override.parent/n).exists()
assert hashlib.sha256(Path(m['candidate_exe']).read_bytes()).hexdigest()==m['candidate_sha256']
recovery=root/'recovery';recovery.mkdir(mode=0o700)
def theme(*args):
 r=subprocess.run([sys.executable,str(root/'theme.py'),*args],capture_output=True,text=True,timeout=125)
 (recovery/('theme-'+args[0]+'.private.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('private theme adapter failed: '+args[0])
 return json.loads(r.stdout)
prepared=theme('prepare')
restore=recovery/'restore.sh';restore.write_text('#!/bin/sh\nset -eu\n'+sys.executable+' '+str(root/'copy-private.py')+'\nrm -f '+str(override)+'\nsystemctl daemon-reload\nsystemctl restart shell.service shell-ui.service theme-helper.service\n'+sys.executable+' '+str(root/'restore-owned.py')+'\n');restore.chmod(0o700)
unit='k230-touchrate-20261021';subprocess.run(['systemd-run','--quiet','--unit='+unit,'--on-active=720s',str(restore)],check=True);assert subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0
start=subprocess.check_output(['systemctl','show','shell.service','-p','ExecStart','--value'],text=True);old=re.search(r'path=([^;]+);',start).group(1).strip();argv=re.search(r'argv\[\]=([^;]+);',start).group(1).strip();assert argv==old or argv.startswith(old+' ');args=argv[len(old):];assert re.fullmatch(r'[ /A-Za-z0-9_.+?=:-]*',args)
meta={'source_revision':m['source_revision'],'descriptor':m,'before':before,'original_properties':original_props,'theme_baseline':prepared,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'runs':[],'roles':[],'restore_unit':unit}
def save():
 p=root/'result.json';p.write_text(json.dumps(meta,indent=2)+'\n');p.chmod(0o600)
def ready(sha):
 end=time.monotonic()+60
 while time.monotonic()<end:
  try:
   v=identity()
   if v['sway_sha256']==sha and v['apps']==['k230-terminal'] and v['wallpaper']['state']=='still':return v
  except Exception:pass
  time.sleep(.3)
 raise RuntimeError('normal/startup state not ready')
def status():return json.loads(Path('/run/shell/k230-wallpaper-status.json').read_text())
def waitstate(state,generation=None):
 end=time.monotonic()+20
 while time.monotonic()<end:
  v=status()
  if v['state']==state and (generation is None or v['generation']==generation):return v
  time.sleep(.1)
 raise RuntimeError('wallpaper state did not become '+state)
log=out/'session-stderr.private.log'
with log.open('xb') as f:os.fchmod(f.fileno(),0o600)
try:
 override.parent.mkdir(parents=True,exist_ok=True);override.write_text('[Service]\nExecStart=\nExecStart='+m['candidate']+'/bin/sway'+args+'\nStandardError=append:'+str(log)+'\n');subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell','shell-ui','theme-helper'],check=True,timeout=80)
 candidate=ready(m['candidate_sha256']);assert candidate['outputs']==before['outputs'];ipc('output '+before['outputs'][0]['name']+' max_render_time 12');expected=json.loads(json.dumps(before['outputs']));expected[0]['max_render_time']=12;assert identity()['outputs']==expected
 prop=props();assert prop['StandardError'] in ['append','append:'+str(log)] and {k:v for k,v in prop.items() if k!='StandardError'}=={k:v for k,v in original_props.items() if k!='StandardError'}
 pid=subprocess.check_output(['systemctl','show','shell','-p','MainPID','--value'],text=True).strip();fd=Path('/proc',pid,'fd/2').stat();st=log.stat();assert stat.S_ISREG(fd.st_mode) and (fd.st_dev,fd.st_ino)==(st.st_dev,st.st_ino)
 meta['candidate']=identity();ipc('card_shell home');time.sleep(1);meta['basic']=theme('basic');save();print(json.dumps(meta['basic']),flush=True)
 for role in ['static','video']:
  assert identity()['apps']==['k230-terminal'],'foreign app before role'
  ipc('card_shell home');activation=theme('activate',role)
  meta['phase']='activate-'+role;meta['activation_pending']=activation;save()
  first=waitstate('still' if role=='static' else 'playing',activation['generation'])
  assert first['generation']==activation['generation'],'wallpaper generation differs'
  arm={'role':role,'activation':activation,'status_before':first,'idle_resources':measure(12,.25)};meta['roles'].append(arm);save()
  if role=='video':
   try:
    ipc('exec foot --app-id=k230.background.cover --title=Background-cover sh -c '+shlex.quote("printf '\\033[44m\\033[2J\\033[HCovered background trial\\n'; sleep 60"))
    end=time.monotonic()+15
    while 'k230.background.cover' not in identity()['apps']:assert time.monotonic()<end;time.sleep(.1)
    ipc('card_shell back');ipc('[app_id="k230.background.cover"] border none');ipc('[app_id="k230.background.cover"] fullscreen enable');waitstate('paused-covered');time.sleep(1);a=status();time.sleep(2);z=status();arm['covered_before']=a;arm['covered_after']=z;arm['cover_signal']=json.loads(Path('/run/shell/k230-wallpaper-cover.json').read_text());arm['covered_counters_stopped']=all(a[k]==z[k] for k in ['frames_decoded','frames_submitted','frame_callbacks']);assert arm['covered_counters_stopped'] and z['decoder_pid'] is None
   finally:ipc('[app_id="k230.background.cover"] kill');ipc('card_shell home')
   arm['uncovered_before']=waitstate('playing');time.sleep(2);arm['uncovered_after']=status();save()
  for cards in [1,3]:
   label=role+'-'+str(cards)+'-cards';directory=out/label;assert identity()['outputs']==expected
   r=subprocess.run([sys.executable,str(root/'collect.py'),'full',str(directory),'6',m['source_revision'],m['system'],str(cards),'file',str(log)],capture_output=True,text=True,timeout=90);(out/(label+'-collector.private.log')).write_text(r.stdout+r.stderr)
   assert identity()['outputs']==expected
   row={'label':label,'role':role,'cards':cards,'allowance_ms':12,'destination':'file','exit':r.returncode,'status_after':status()};meta['runs'].append(row);save();print(json.dumps({k:row[k] for k in ['label','cards','exit']}),flush=True)
   if r.returncode:raise RuntimeError('card collector failed')
 meta['private_log_bytes']=log.stat().st_size;meta['private_log_sha256']=hashlib.sha256(log.read_bytes()).hexdigest();assert meta['private_log_bytes']<=8*1024*1024
finally:
 r=subprocess.run([str(restore)],capture_output=True,text=True,timeout=140);(recovery/'normal-restore.private.log').write_text(r.stdout+r.stderr);assert r.returncode==0
 meta['theme_restoration']=json.loads(r.stdout);meta['restored']=ready(m['normal_sha256']);meta['restored_properties']=props();assert meta['restored_properties']==original_props
 for key in ['system','profile','boot_id','outputs']:assert meta['restored'][key]==before[key]
 assert meta['restored']['wallpaper']['generation']==before['wallpaper']['generation'] and not override.exists()
 assert meta['theme_restoration']['preferences_sha256']==prepared['preferences_sha256'] and meta['theme_restoration']['app_appearance_generation']==prepared['app_appearance_generation'] and meta['theme_restoration']['fixture_removed']
 meta['test_input_devices']=sum(p.read_text().strip()=='K230 injected touchscreen' for p in Path('/sys/class/input').glob('event*/device/name'));assert meta['test_input_devices']==0
 meta['normal_services']={n:subprocess.run(['systemctl','is-active','--quiet',n]).returncode==0 for n in ['shell','shell-ui','theme-helper']};assert all(meta['normal_services'].values());subprocess.run(['systemctl','stop',unit+'.timer'],check=True);meta['restore_timer_active']=subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0;assert not meta['restore_timer_active']
 meta['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save();print(json.dumps({'restoration':'verified','runs':len(meta['runs'])}),flush=True)
