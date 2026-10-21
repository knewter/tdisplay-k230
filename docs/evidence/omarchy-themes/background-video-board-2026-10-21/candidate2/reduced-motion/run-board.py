from pathlib import Path
import subprocess,os,json,pwd,time,re,hashlib,importlib.util
stage=Path('/run/shell/source3-background-trial-20261021');stable=Path('/var/lib/k230/background-video-trial-20261021');py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
u=pwd.getpwnam('shell')
def drop():os.setgroups([]);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
def current_env():
 pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip()
 return {k.decode():v.decode() for k,v in (v.split(b'=',1) for v in Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in v)}
env=current_env();m=json.loads((stage/'candidate.json').read_text());out=stage/'reduced-motion';out.mkdir(mode=0o700);os.chown(out,u.pw_uid,u.pw_gid)
def theme(*args):
 p=subprocess.run([env['K230_THEME_COMMAND'],*args,'--json'],env=env,preexec_fn=drop,capture_output=True,text=True,timeout=30);assert p.returncode==0;return json.loads(p.stdout)
def status():return json.loads(Path('/run/shell/k230-wallpaper-status.json').read_text())
def waitstate(want):
 until=time.monotonic()+20
 while time.monotonic()<until:
  try:
   e=current_env();v=status()
   if v['state']==want and e.get('K230_SETTINGS_REDUCED_MOTION')==('1' if want=='paused-reduced-motion' else '0'):return v
  except (OSError,ValueError,subprocess.CalledProcessError):pass
  time.sleep(.1)
 raise RuntimeError('expected wallpaper state unavailable: '+want)
assert (Path(m['state_root'])/'active').resolve().name=='2e583fb7dc1947e9d444c171'
assert env['K230_SETTINGS_REDUCED_MOTION']=='0'
original=subprocess.check_output(['systemctl','show','shell-ui','-p','ExecStart','--value'],text=True)
path=re.search(r'path=([^;]+);',original).group(1).strip();argv=re.search(r'argv\[\]=([^;]+);',original).group(1).strip();assert argv.startswith(path);args=argv[len(path):];assert re.fullmatch(r'[ /A-Za-z0-9_.+?=:-]*',args)
source=Path(path).read_text();needle='export K230_SETTINGS_REDUCED_MOTION=0';assert source.count(needle)==1
wrapper=stage/'reduced-motion-wrapper';wrapper.write_text(source.replace(needle,'export K230_SETTINGS_REDUCED_MOTION=1'));wrapper.chmod(0o755);os.chown(wrapper,u.pw_uid,u.pw_gid)
override=Path('/run/systemd/system/shell-ui.service.d/93-source3-background-motion.conf');assert not override.exists()
restore=stable/'restore-compositor.sh';text=restore.read_text();marker='systemctl daemon-reload\n';assert text.count(marker)==1
if str(override) not in text:restore.write_text(text.replace(marker,'rm -f '+str(override)+'\n'+marker));restore.chmod(0o700)
a={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'original_exec_start':path,'original_wrapper_sha256':hashlib.sha256(source.encode()).hexdigest(),'flag_change':'Only the installed wrapper export0 to1; same underlying Rust executable. Read-only session setting, no live Settings-toggle claim.','restoration':'pending'}
try:
 c=m['background_trial']['choices']['video'];entry=[x for x in theme('list')['themes'] if x['name']==c['theme_name'] and x['origin']==c['origin']];assert len(entry)==1
 v=theme('preview',entry[0]['id'],'--background',c['background_id']);r=theme('activate',entry[0]['id'],'--background',c['background_id'],'--expected-generation',v['generation']);assert r['activated']
 subprocess.run(['/run/current-system/sw/bin/swaymsg','-s','/run/shell/sway-ipc.sock','card_shell home'],capture_output=True,check=True,timeout=20)
 a['playing_before']=waitstate('playing')
 override.parent.mkdir(exist_ok=True,parents=True);override.write_text('[Service]\nExecStart=\nExecStart='+str(wrapper)+args+'\n')
 subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell-ui.service'],check=True,timeout=60)
 a['paused_first']=waitstate('paused-reduced-motion');time.sleep(1);a['paused_before']=status();time.sleep(3);a['paused_after']=status();a['decoder_absent']=a['paused_after']['decoder_pid'] is None;a['counters_stopped']=all(a['paused_before'][k]==a['paused_after'][k] for k in ['frames_decoded','frames_submitted','frame_callbacks'])
 subprocess.run(['/run/current-system/sw/bin/grim','-o','DSI-1',str(out/'paused.png')],env=current_env(),preexec_fn=drop,capture_output=True,check=True,timeout=20)
finally:
 override.unlink(missing_ok=True);subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell-ui.service'],check=True,timeout=60)
 try:
  a['playing_after']=waitstate('playing');time.sleep(2);a['playing_after_progress']=status()
 finally:
  code="import sys,json;from pathlib import Path;sys.path.insert(0,"+repr(str(stage/'tools'))+");import importlib.util;s=importlib.util.spec_from_file_location('trial',"+repr(str(stage/'tools/handheld-theme-trial.py'))+");t=importlib.util.module_from_spec(s);s.loader.exec_module(t);m=json.loads(Path("+repr(str(stage/'candidate.json'))+").read_text());v=json.loads(Path("+repr(str(stage/'raw-basic/recovery.json'))+").read_text());t.restore(v,state_root=Path(m['state_root']),default_generation=Path(m['default_generation']),endpoints=(Path(m['rust_socket']),Path(m['deck_socket'])))"
  p=subprocess.run([py,'-c',code],env=current_env(),preexec_fn=drop,capture_output=True,text=True,timeout=30);(out/'restore.private.log').write_text(p.stdout+p.stderr)
  a['restoration']='passed' if p.returncode==0 and (Path(m['state_root'])/'active').resolve().name=='2e583fb7dc1947e9d444c171' else 'FAILED'
  a['flag_restored']=current_env().get('K230_SETTINGS_REDUCED_MOTION')=='0';a['owned_override_absent']=not override.exists();a['finished_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());(out/'result.json').write_text(json.dumps(a,indent=2)+'\n');print(json.dumps(a))
