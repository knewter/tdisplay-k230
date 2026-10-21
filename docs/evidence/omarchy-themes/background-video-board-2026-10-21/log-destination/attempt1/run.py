"""Guarded same-binary, same-workload journal/file/journal diagnostic."""
import hashlib,json,os,re,stat,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from cadence_audit import identity
root=Path(__file__).parent
out=Path('/run/k230-source3-log-destination-20261021');out.mkdir(mode=0o700)
m=json.loads((root/'descriptor.json').read_text());before=identity()
assert before['system']==m['system'] and before['profile']==m['system']
assert before['sway_sha256']==m['normal_sha256'] and before['apps']==['k230-terminal']
assert before['wallpaper']['state']=='still' and len(before['outputs'])==1
assert before['outputs'][0]['transform']=='270' and before['outputs'][0]['max_render_time']==8
keys=['StandardOutput','StandardError','LogLevelMax','LogRateLimitIntervalUSec','LogRateLimitBurst']
def properties():return {k:subprocess.check_output(['systemctl','show','shell.service','-p',k,'--value'],text=True).strip() for k in keys}
original_properties=properties();assert original_properties['StandardOutput']=='journal' and original_properties['StandardError']=='inherit'
override=Path('/run/systemd/system/shell.service.d/95-source3-log-destination.conf');assert not override.exists()
assert not Path('/run/systemd/system/shell.service.d/94-source3-cadence-timing.conf').exists()
stable=root/'recovery';stable.mkdir(mode=0o700)
start=subprocess.check_output(['systemctl','show','shell.service','-p','ExecStart','--value'],text=True)
old=re.search(r'path=([^;]+);',start).group(1).strip();argv=re.search(r'argv\[\]=([^;]+);',start).group(1).strip()
assert argv==old or argv.startswith(old+' ')
args=argv[len(old):];assert re.fullmatch(r'[ /A-Za-z0-9_.+?=:-]*',args)
assert re.fullmatch(r'/nix/store/[0-9a-z]{32}-k230-card-shell-hdmi-trial',m['candidate'])
assert hashlib.sha256(Path(m['candidate_exe']).read_bytes()).hexdigest()==m['candidate_sha256']
gc=Path('/nix/var/nix/gcroots/source3-cadence-elapsed-20261021');assert gc.is_symlink() and str(gc.resolve())==m['candidate']
restore=stable/'restore.sh';restore.write_text('#!/bin/sh\nset -eu\nrm -f '+str(override)+'\nsystemctl daemon-reload\nsystemctl restart shell.service shell-ui.service theme-helper.service\n');restore.chmod(0o700)
unit='k230-source3-log-destination-20261021'
subprocess.run(['systemd-run','--quiet','--unit='+unit,'--on-active=480s',str(restore)],check=True)
assert subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0
meta={'source_revision':m['source_revision'],'descriptor':m,'before':before,'original_properties':original_properties,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'runs':[],'restore_unit':unit}
(stable/'before.private.json').write_text(json.dumps({**meta,'normal_exec_start':start},indent=2)+'\n')
def ready(sha,timeout=60):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  try:
   v=identity()
   if v['sway_sha256']==sha and v['apps']==['k230-terminal'] and v['wallpaper']['state']=='still':return v
  except Exception:pass
  time.sleep(.3)
 raise RuntimeError('expected compositor/startup terminal/still background not ready')
try:
 for label,destination in [('journal','journal'),('file','file'),('journal-return','journal')]:
  if meta['runs']:
   assert identity()['apps']==['k230-terminal'],'foreign app opened during probe'
  directory=out/label;directory.mkdir(mode=0o700)
  log=directory/'session-stderr.private.log'
  stderr='inherit'
  if destination=='file':
   with log.open('xb') as f:os.fchmod(f.fileno(),0o600)
   stderr='append:'+str(log)
  override.parent.mkdir(parents=True,exist_ok=True)
  override.write_text('[Service]\nExecStart=\nExecStart='+m['candidate']+'/bin/sway'+args+'\nStandardError='+stderr+'\n')
  subprocess.run(['systemctl','daemon-reload'],check=True)
  subprocess.run(['systemctl','restart','shell.service','shell-ui.service','theme-helper.service'],check=True,timeout=80)
  installed=ready(m['candidate_sha256'])
  assert installed['outputs']==before['outputs'] and installed['wallpaper']['generation']==before['wallpaper']['generation']
  prop=properties();assert prop=={**original_properties,'StandardError':stderr}
  pid=int(subprocess.check_output(['systemctl','show','shell.service','-p','MainPID','--value'],text=True))
  fd=Path('/proc',str(pid),'fd/2');fdstat=fd.stat()
  if destination=='file':
   assert stat.S_ISREG(fdstat.st_mode) and (fdstat.st_dev,fdstat.st_ino)==(log.stat().st_dev,log.stat().st_ino)
  else:assert stat.S_ISSOCK(fdstat.st_mode)
  command=[sys.executable,str(root/'collect.py'),'full',str(directory/'3-cards'),'6',m['source_revision'],m['system'],'3',destination,str(log) if destination=='file' else '-']
  r=subprocess.run(command,capture_output=True,text=True,timeout=90)
  (directory/'collector.private.log').write_text(r.stdout+r.stderr)
  row={'label':label,'destination':destination,'cards':3,'exit':r.returncode,'pid':pid,'fd2_kind':'regular-file' if destination=='file' else 'journal-stream','properties':prop,'identity':installed}
  if destination=='file':
   row['private_log_bytes']=log.stat().st_size;row['private_log_sha256']=hashlib.sha256(log.read_bytes()).hexdigest();assert row['private_log_bytes']<=8*1024*1024
  meta['runs'].append(row);(root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
  print(json.dumps({k:row[k] for k in ['label','destination','exit','fd2_kind']}),flush=True)
  if r.returncode:raise RuntimeError('collector failed')
finally:
 subprocess.run([str(restore)],check=True,timeout=80)
 meta['restored']=ready(m['normal_sha256']);meta['restored_properties']=properties()
 assert meta['restored_properties']==original_properties
 for key in ['system','profile','boot_id','outputs']:assert meta['restored'][key]==before[key]
 assert meta['restored']['wallpaper']['generation']==before['wallpaper']['generation'] and not override.exists()
 meta['test_input_devices']=sum(p.read_text().strip()=='K230 injected touchscreen' for p in Path('/sys/class/input').glob('event*/device/name'));assert meta['test_input_devices']==0
 meta['normal_services']={n:subprocess.run(['systemctl','is-active','--quiet',n]).returncode==0 for n in ['shell','shell-ui','theme-helper']};assert all(meta['normal_services'].values())
 subprocess.run(['systemctl','stop',unit+'.timer'],check=True)
 meta['restore_timer_active']=subprocess.run(['systemctl','is-active','--quiet',unit+'.timer']).returncode==0;assert not meta['restore_timer_active']
 meta['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());(root/'result.json').write_text(json.dumps(meta,indent=2)+'\n')
 print(json.dumps({'restoration':'verified','runs':len(meta['runs'])}),flush=True)
