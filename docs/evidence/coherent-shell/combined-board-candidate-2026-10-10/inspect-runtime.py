"""Coordinator board check after the guarded temporary boot; transport stays private.

No real-finger acceptance or persistent installation is inferred. Exact stage
state is required; native Help capture is requested programmatically.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, struct, subprocess, sys, time, urllib.request
os.umask(0o077)
stage=Path(sys.argv[1]); endpoint=sys.argv[2]
state=json.loads((stage/'state.json').read_text()); candidate=state['candidate']
RUST='/nix/store/z4j8bc7iwz9m7pap376zy0j0z16295lr-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
SWAY='/nix/store/awym9l5znn6599q37wnhnnch77ggghjh-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
HELPER='/nix/store/y76z6yndmg134z5fyp1p1j9lmlgcfkzf-handheld-theme-command-0.1'
def call(args):return subprocess.check_output(args,text=True,timeout=20).strip()
def executable(service):
 pid=int(call(['systemctl','show',service,'-p','MainPID','--value']))
 return str(Path('/proc',str(pid),'exe').resolve(strict=True))
services={s:call(['systemctl','is-active',s]) for s in ['shell','shell-ui','theme-helper','k230-touch-trackpad']}
assert all(x=='active' for x in services.values()),services
system=str(Path('/run/current-system').resolve()); profile=str(Path('/nix/var/nix/profiles/system').resolve())
assert system==candidate['system'] and profile==state['normal_profile']
assert str(Path('/run/booted-system/kernel').resolve())==candidate['kernel']
assert executable('shell-ui')==RUST and executable('shell')==SWAY
assert HELPER+'/bin/k230-theme-helperd' in call(['systemctl','show','theme-helper','-p','ExecStart','--value'])
normal={name:hashlib.sha256((Path('/boot')/name).read_bytes()).hexdigest() for name in state['normal_files']}
assert normal=={name:entry['sha256'] for name,entry in state['normal_files'].items()}
wayland=[p.name for p in Path('/run/shell').glob('wayland-*') if p.is_socket()]
assert len(wayland)==1,wayland
ENV=['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+wayland[0],'SWAYSOCK=/run/shell/sway-ipc.sock']
call(ENV+[RUST,'--surface','help']);time.sleep(2)
image=Path('/run/shell/k230-combined-help.png')
try:
 call(ENV+['grim',str(image)])
 data=image.read_bytes();assert data[:8]==b'\x89PNG\r\n\x1a\n'
 width,height=struct.unpack('>II',data[16:24])
 urllib.request.urlopen(urllib.request.Request(endpoint+'/help-native.png',data=data,method='POST'),timeout=30).read()
finally:
 call(ENV+[RUST,'--surface','hide']);call(ENV+['swaymsg','card_shell home'])
outputs=json.loads(call(ENV+['swaymsg','-t','get_outputs','-r']))
report={'utc':datetime.now(timezone.utc).isoformat(),'evidence_class':'physical-board serial identity and programmatic native Help capture; no real-finger or camera acceptance',
 'candidate':candidate['bundle'],'system':system,'profile':profile,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 'kernel':candidate['kernel'],'shell_executable':RUST,'sway_executable':SWAY,'theme_helper':HELPER,'services':services,
 'normal_boot_files':normal,'normal_profile_preserved':True,'persistent_boot_selection_changed':False,
 'sway_outputs':[{k:x.get(k) for k in ['name','active','current_mode','transform','scale','rect']} for x in outputs],
 'help_capture':{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'width':width,'height':height,'input':'programmatic help route request'},
 'home_restored_programmatically':True,'operator_real_finger_accepted':False,'result':'PASS'}
body=(json.dumps(report,indent=2)+'\n').encode()
urllib.request.urlopen(urllib.request.Request(endpoint+'/runtime.json',data=body,method='POST'),timeout=30).read()
print('K230_COMBINED_RUNTIME_PASS',flush=True)
