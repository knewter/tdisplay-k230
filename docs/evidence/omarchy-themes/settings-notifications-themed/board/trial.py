from pathlib import Path
import os,sys,json,subprocess,time,re,hashlib,uuid,pwd,urllib.request
os.umask(0o077)
SOURCE='288535289172c8465c4fa408eaa8ba2c7ab8a5ac'
RUST='/nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
HELPER='/nix/store/l6qm7fykcf6bmlhp3wcj7va4v2k4v2fg-handheld-theme-command-0.1'
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
root=Path('/root/tmp/k230-settings-themed')
userroot=Path('/run/shell/settings-themed-trial-'+sys.argv[-1])
state=Path('/home/shell/.local/state/omarchy/current')
url=sys.argv[1]
def call(args,timeout=40):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout

def user_phase():
 sys.path.insert(0,HELPER+'/libexec/handheld-theme')
 import theme_transaction as tx
 import importlib.util
 ns=importlib.util.spec_from_file_location('notifications',sys.argv[2]);nm=importlib.util.module_from_spec(ns);ns.loader.exec_module(nm);notify=nm.call
 endpoints=(Path('/run/shell/k230-shell-rust-appearance.sock'),Path('/run/shell/k230-card-appearance.sock'))
 report={'source':SOURCE,'class':'physical-board-native-captures','rust':RUST,'helper':HELPER,'started_epoch_s':time.time(),'phases':[]}
 def generation(name):
  data=json.loads(call([HELPER+'/bin/omarchy-theme-set',name,'--prepare-only'],timeout=90))
  p=Path(data['generation_path']);assert p.is_relative_to(state/'generations')
  report['phases'].append({'prepare':name,'generation':p.name,'coverage':{k:data['report'].get(k,[]) for k in ['applied','adapted','unavailable','unknown']},'sections':json.loads((p/'appearance.json').read_text())['sections']})
  return p
 dark=generation('catppuccin');light=generation('catppuccin-latte')
 def activate(p):return tx.activate_generation(p,state_root=state,endpoint=endpoints[0],endpoints=endpoints)
 def capture(label,surface):
  call([RUST,'--surface',surface]);time.sleep(8 if surface=='settings' else 2)
  target=userroot/(label+'.png');call(['grim',str(target)])
  report['phases'].append({'capture':label,'surface':surface,'active_generation':(state/'active').resolve().name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
 def emit(label):
  answer=notify(userroot/'notifications.sock',{'operation':'emit','summary':'Theme verification','body':label+' palette on the handheld','tag':'settings-theme-trial','private':False})
  assert answer['state']=='accepted',answer
 for label,g in [('dark',dark),('light',light)]:
  activate(g);assert (state/'active').resolve()==g
  # Only fixture text is emitted into the isolated real notification daemon.
  call([PYTHON,str(userroot/'emit.py'),str(userroot/'notifications.sock'),label])
  capture(label+'-settings','settings');capture(label+'-shade','shade')
 activate(dark)
 rollback_seen=[]
 def failing_transport(endpoint,phase,generation):
  if endpoint==endpoints[1] and phase=='commit':
   raise tx.TransactionError('deliberate second-receiver commit failure')
  tx.exchange(endpoint,phase,generation)
  if phase=='rollback':rollback_seen.append(str(endpoint))
 try:
  tx.activate_generation(light,state_root=state,endpoint=endpoints[0],endpoints=endpoints,transport=failing_transport)
 except tx.TransactionError as error:
  assert str(error)=='commit failed; previous generation restored',str(error)
 else:raise AssertionError('deliberate commit failure did not abort')
 assert (state/'active').resolve()==dark
 assert set(rollback_seen)=={str(p) for p in endpoints}
 report['rollback']={'failure':'deliberate second-receiver commit failure','receivers_acknowledged':len(rollback_seen),'restored_generation':dark.name}
 capture('rollback-settings','settings');capture('rollback-shade','shade')
 (userroot/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 return

if '--user-phase' in sys.argv:
 # Notification emit must be root to preserve trusted-source metadata. The
 # child emits through a root-created one-shot helper request file instead.
 raise RuntimeError('root orchestrates user commands in this trial')

u=pwd.getpwnam('shell');userroot.mkdir(mode=0o700,exist_ok=False);os.chown(userroot,u.pw_uid,u.pw_gid)
original=str((state/'active').resolve(strict=True));active_stat=(state/'active').lstat()
current=str(Path('/run/current-system').resolve())
profile=str(Path('/nix/var/nix/profiles/system').resolve())
def boot_hashes():
 return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/boot').iterdir() if p.is_file()}
before_boot=boot_hashes()
before_pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']))
before_exe=os.readlink('/proc/'+str(before_pid)+'/exe')
normal=call(['systemctl','show','shell-ui','-p','ExecStart','--value']);match=re.search(r'path=(/nix/store/[^ ;]+/bin/k230-shell-rust)',normal);assert match
original_wrapper=Path(match[1]).read_text()
wrapper,n=re.subn(r'(?m)^\s*exec /nix/store/[^ ]+/bin/k230-shell-rust', 'export K230_THEME_COMMAND='+HELPER+'/bin/k230-theme\nexport K230_NOTIFICATION_SOCKET='+str(userroot/'notifications.sock')+'\nexec '+RUST,original_wrapper)
assert n==1
wp=userroot/'shell-wrapper';wp.write_text(wrapper);wp.chmod(0o555)
normal_helper=call(['systemctl','show','theme-helper','-p','ExecStart','--value'])
helper_args=re.search(r'argv\[\]=(.*?) ;',normal_helper).group(1)
helper_args,n=re.subn(r'^/nix/store/[^ ;]+/bin/k230-theme-helperd',HELPER+'/bin/k230-theme-helperd',helper_args);assert n==1
owned=[Path('/run/systemd/system/'+unit+'.service.d/93-settings-theme-trial.conf') for unit in ['shell-ui','theme-helper']]
assert not any(p.exists() for p in owned)
notification_unit='k230-settings-theme-notifications-'+sys.argv[-1]
cleanup=root/'restore.py'
cleanup.write_text('''from pathlib import Path
import os,subprocess,uuid
p=Path('/home/shell/.local/state/omarchy/current/active')
t=p.parent/('.settings-restore-'+uuid.uuid4().hex)
t.symlink_to('''+repr(original)+''')
os.chown(t,'''+str(active_stat.st_uid)+','+str(active_stat.st_gid)+''',follow_symlinks=False)
os.replace(t,p)
for f in '''+repr([str(p) for p in owned])+''':Path(f).unlink(missing_ok=True)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','restart','theme-helper','shell-ui'],check=True)
subprocess.run(['systemctl','stop','''+repr(notification_unit+'.service')+'''],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
''')
# The watchdog runs as root even if the coordinator or serial command dies.
timer='k230-settings-theme-restore-'+sys.argv[-1]
call(['systemd-run','--unit='+timer,'--on-active=480s',PYTHON,str(cleanup)])
try:
 # Isolate screenshot data from the operator's notification history while
 # exercising the exact real daemon/socket and Rust notification parser.
 notification_script=Path('/run/current-system/sw/bin/k230-notifications').resolve()
 notify_source=re.search(r'(/nix/store/[^ ]+notification_center.py)',notification_script.read_text()).group(1)
 call(['systemd-run','--unit='+notification_unit,'--collect','--uid=shell','--property=RuntimeMaxSec=480s',PYTHON,notify_source,'serve','--socket',str(userroot/'notifications.sock')])
 for p,command in zip(owned,[str(wp)+' --serve',helper_args]):
  p.parent.mkdir(exist_ok=True);p.write_text('[Service]\nExecStart=\nExecStart='+command+'\n')
 call(['systemctl','daemon-reload']);call(['systemctl','restart','theme-helper','shell-ui']);time.sleep(4)
 pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']));assert os.readlink('/proc/'+str(pid)+'/exe')==RUST
 # Execute the transaction/presentation phase as shell. Emitting as this
 # unlisted app is deliberately private; only known public fixture text is
 # present in its isolated history, so no operator data can enter captures.
 child=Path(__file__).read_text().split("if '--user-phase' in sys.argv:")[0]
 child=child.replace("call([PYTHON,str(userroot/'emit.py'),str(userroot/'notifications.sock'),label])",'emit(label)')
 child+='\nuser_phase()\n'
 phase=userroot/'phase.py';phase.write_text(child);phase.chmod(0o444)
 call(['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin',PYTHON,str(phase),url,notify_source,sys.argv[-1]],timeout=300)
finally:
 call([PYTHON,str(cleanup)],timeout=60)
 call(['systemctl','stop',timer+'.timer'])
assert (state/'active').resolve()==Path(original)
assert str(Path('/run/current-system').resolve())==current
assert str(Path('/nix/var/nix/profiles/system').resolve())==profile
assert boot_hashes()==before_boot
assert call(['systemctl','is-active','shell','shell-ui','theme-helper']).splitlines()==['active']*3
restored_pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']))
assert os.readlink('/proc/'+str(restored_pid)+'/exe')==before_exe
report=json.loads((userroot/'result.json').read_text());report['current_system']=current;report['normal_restored']=True;report['original_generation_restored']=True;report['notification_history']='isolated actual daemon; operator history untouched';report['installed_candidate_pid']=pid;report['restored_normal_exe']=before_exe;report['boot_and_profile_unchanged']=True;report['result']='PASS'
(root/'result.json').write_text(json.dumps(report,indent=2)+'\n')
for name in ['dark-settings.png','light-settings.png','dark-shade.png','light-shade.png','rollback-settings.png','rollback-shade.png']:
 urllib.request.urlopen(urllib.request.Request(url+'/'+name,data=(userroot/name).read_bytes(),method='POST'),timeout=25).read()
urllib.request.urlopen(urllib.request.Request(url+'/result.json',data=(root/'result.json').read_bytes(),method='POST'),timeout=25).read()
print('K230_SETTINGS_THEME_TRIAL_PASS',flush=True)
