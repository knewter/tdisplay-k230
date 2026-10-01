from pathlib import Path
import os,re,json,subprocess,time,hashlib
ROOT=Path('/root/tmp/k230-home-menu');ROOT.mkdir(parents=True,exist_ok=True)
RUST='/nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
HELPER='/nix/store/l6qm7fykcf6bmlhp3wcj7va4v2k4v2fg-handheld-theme-command-0.1'
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
SOURCE='288535289172c8465c4fa408eaa8ba2c7ab8a5ac'
def call(args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=60).stdout
owned=[Path('/run/systemd/system/'+unit+'.service.d/94-home-app-actions.conf') for unit in ['shell-ui','theme-helper']]
assert not any(p.exists() for p in owned)
assert Path(RUST).is_file()
normal=call(['systemctl','show','shell-ui','-p','ExecStart','--value'])
wrapper=Path(re.search(r'path=(/nix/store/[^ ;]+/bin/k230-shell-rust)',normal).group(1))
before_pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']))
before_exe=os.readlink('/proc/'+str(before_pid)+'/exe')
system=str(Path('/run/current-system').resolve());profile=str(Path('/nix/var/nix/profiles/system').resolve())
text,n=re.subn(r'(?m)^\s*exec /nix/store/[^ ]+/bin/k230-shell-rust','export K230_THEME_COMMAND='+HELPER+'/bin/k230-theme\nexec '+RUST,wrapper.read_text());assert n==1
candidate=Path('/run/shell/k230-home-menu-wrapper');candidate.write_text(text);candidate.chmod(0o555)
h=call(['systemctl','show','theme-helper','-p','ExecStart','--value'])
h=re.search(r'argv\[\]=(.*?) ;',h).group(1)
h,n=re.subn(r'^/nix/store/[^ ;]+/bin/k230-theme-helperd',HELPER+'/bin/k230-theme-helperd',h);assert n==1
restore=ROOT/'restore.py'
restore.write_text('from pathlib import Path\nimport subprocess\nfor f in '+repr([str(p) for p in owned])+':Path(f).unlink(missing_ok=True)\nsubprocess.run(["systemctl","daemon-reload"],check=True)\nsubprocess.run(["systemctl","restart","theme-helper","shell-ui"],check=True)\n')
timer='k230-home-app-actions-restore-2'
call(['systemd-run','--unit='+timer,'--on-active=1800s',PYTHON,str(restore)])
try:
 for p,command in zip(owned,[str(candidate)+' --serve',h]):
  p.parent.mkdir(exist_ok=True);p.write_text('[Service]\nExecStart=\nExecStart='+command+'\n')
 call(['systemctl','daemon-reload']);call(['systemctl','restart','theme-helper','shell-ui']);time.sleep(4)
 pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']))
 assert os.readlink('/proc/'+str(pid)+'/exe')==RUST
 assert call(['systemctl','is-active','shell','shell-ui','theme-helper']).splitlines()==['active']*3
 assert str(Path('/run/current-system').resolve())==system
 assert str(Path('/nix/var/nix/profiles/system').resolve())==profile
 env=['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin']
 call(env+[RUST,'--surface','hide']);call(env+['swaymsg','card_shell home'])
 report={'source':SOURCE,'rust':RUST,'helper':HELPER,'original_exe':before_exe,'current_system':system,'profile_unchanged':True,'normal_services_active':True,'class':'physical-board-runtime-component-install','started_epoch_s':time.time(),'restoration_after_s':1800,'restore_command':PYTHON+' '+str(restore),'boot_or_finger_acceptance':False}
 (ROOT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 print('K230_HOME_MENU_RUNTIME_READY '+json.dumps(report))
except BaseException:
 call([PYTHON,str(restore)]);call(['systemctl','stop',timer+'.timer']);raise
