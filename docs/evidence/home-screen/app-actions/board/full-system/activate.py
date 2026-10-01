from pathlib import Path
import os,json,time,subprocess,hashlib
CANDIDATE='/nix/store/ija989s4f2la7ms4zbr9dnirpnnp8qyg-nixos-system-nixos-26.11.20260919.20b1ddd'
RUST='/nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
ROOT=Path('/root/tmp/k230-system-activation');ROOT.mkdir(parents=True,exist_ok=True)
def call(args,timeout=90):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout
baseline=str(Path('/run/current-system').resolve());profile=str(Path('/nix/var/nix/profiles/system').resolve())
assert baseline=='/nix/store/xphf8zb00gz9hiyqkkh399rldr2ljykb-nixos-system-nixos-26.11.20260919.20b1ddd'
assert Path(CANDIDATE+'/bin/switch-to-configuration').exists()
for name in ['kernel','initrd','kernel-modules']:
 assert (Path(baseline)/name).resolve()==(Path(CANDIDATE)/name).resolve(),name
def boot_hashes():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/boot').iterdir() if p.is_file()}
before_boot=boot_hashes()
owned=[Path('/run/systemd/system/'+unit+'.service.d/94-home-app-actions.conf') for unit in ['shell-ui','theme-helper']]
backup={str(p):p.read_text() for p in owned if p.exists()}
wrapper=Path('/run/shell/k230-home-menu-wrapper');wrapper_text=wrapper.read_text() if wrapper.exists() else None
restore=ROOT/'restore.py'
restore.write_text('from pathlib import Path\nimport subprocess\nsubprocess.run(['+repr(baseline+'/bin/switch-to-configuration')+',"test"],check=True)\n'+('p=Path("/run/shell/k230-home-menu-wrapper");p.write_text('+repr(wrapper_text)+');p.chmod(0o555)\n' if wrapper_text is not None else '')+'for p,s in '+repr(backup)+'.items():\n f=Path(p);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)\nsubprocess.run(["systemctl","daemon-reload"],check=True)\nsubprocess.run(["systemctl","restart","theme-helper","shell-ui"],check=True)\n')
(ROOT/'baseline.json').write_text(json.dumps({'baseline':baseline,'profile':profile,'boot':before_boot,'overrides':backup},indent=2)+'\n')
timer='k230-full-runtime-restore'
call(['systemd-run','--unit='+timer,'--on-active=1200s',PYTHON,str(restore)])
try:
 # The new independent timer owns recovery before retiring the older trial.
 call(['systemctl','stop','k230-home-app-actions-restore-2.timer'])
 for p in owned:p.unlink(missing_ok=True)
 call(['systemctl','daemon-reload'])
 call([CANDIDATE+'/bin/switch-to-configuration','test'],timeout=180)
 time.sleep(5)
 assert str(Path('/run/current-system').resolve())==CANDIDATE
 assert str(Path('/nix/var/nix/profiles/system').resolve())==profile
 assert boot_hashes()==before_boot
 assert call(['systemctl','is-active','shell','shell-ui','theme-helper']).splitlines()==['active']*3
 pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']))
 assert os.readlink('/proc/'+str(pid)+'/exe')==RUST
 env=['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin']
 call(env+[RUST,'--surface','hide']);call(env+['swaymsg','card_shell home'])
 report={'source':'288535289172c8465c4fa408eaa8ba2c7ab8a5ac','class':'physical-board-full-system-runtime-test-activation','candidate':CANDIDATE,'baseline':baseline,'rust':RUST,'profile_unchanged':True,'boot_files_unchanged':True,'normal_services_active':True,'component_overrides_removed':True,'started_epoch_s':time.time(),'restoration_after_s':1200,'restore_command':PYTHON+' '+str(restore),'boot_acceptance':False,'result':'PASS'}
 (ROOT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('K230_FULL_RUNTIME_READY '+json.dumps(report),flush=True)
except BaseException:
 call([PYTHON,str(restore)],timeout=180)
 call(['systemctl','stop',timer+'.timer'])
 raise
