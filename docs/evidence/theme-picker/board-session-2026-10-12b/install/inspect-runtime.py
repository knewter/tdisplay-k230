"""Verify exact deployed userspace and boot identities; no new finger/pixel claim."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, importlib.util, json, os, subprocess, sys, urllib.request
os.umask(0o077)
stage=Path(sys.argv[1]); endpoint=sys.argv[2]; mode=sys.argv[3]
assert mode in ('candidate','ordinary')
state=json.loads((stage/'state.json').read_text()); candidate=state['candidate']
expected=json.loads(Path('/run/k230-mainline-theme-expected.json').read_text())
def call(args):return subprocess.check_output(args,text=True,timeout=30).strip()
def executable(service):
 pid=call(['systemctl','show',service,'-p','MainPID','--value'])
 return str(Path('/proc',pid,'exe').resolve(strict=True))
services={s:call(['systemctl','is-active',s]) for s in ('shell','shell-ui','theme-helper','k230-touch-trackpad')}
assert all(x=='active' for x in services.values()), 'service not active'
system=str(Path('/run/current-system').resolve()); profile=str(Path('/nix/var/nix/profiles/system').resolve())
assert system==candidate['system'] and profile==(system if mode=='ordinary' else state['normal_profile'])
assert str(Path('/run/booted-system/kernel').resolve())==candidate['kernel']
assert [v for v in Path('/proc/cmdline').read_text().split() if v.startswith('init=')]==['init='+system+'/init']
assert executable('shell-ui')==expected['rust'] and executable('shell')==expected['sway']
assert expected['helper']+'/bin/k230-theme-helperd' in call(['systemctl','show','theme-helper','-p','ExecStart','--value'])
normal={n:hashlib.sha256((Path('/boot')/n).read_bytes()).hexdigest() for n in state['normal_files']}
installation=json.loads((stage/'install-result.json').read_text()) if mode=='ordinary' else None
assert normal=={n:v['sha256'] for n,v in (installation['after'] if installation else state['normal_files']).items()}
selection=Path('/home/shell/.local/state/omarchy/current/active'); active=selection.resolve(strict=True) if selection.exists() or selection.is_symlink() else None
appearance={'generation':active.name if active else None,'report_sha256':hashlib.sha256((active/'report.json').read_bytes()).hexdigest() if active and (active/'report.json').exists() else None}
preferences=Path('/home/shell/.local/state/omarchy/background-selections.json')
prefhash=hashlib.sha256(preferences.read_bytes()).hexdigest() if preferences.exists() else None
assert appearance==expected['baseline_appearance'] and prefhash==expected['baseline_preferences_sha256']
roots=('system-gc-root','rollback-profile-root','rollback-init-root') if mode=='ordinary' else ('system-gc-root',)
assert all((stage/name).is_symlink() and (stage/name).exists() for name in roots)
outputs=json.loads(call(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','SWAYSOCK=/run/shell/sway-ipc.sock','swaymsg','-t','get_outputs','-r']))
assert any(out.get('active') for out in outputs),'no active display output'
report={'utc':datetime.now(timezone.utc).isoformat(),'result':'PASS','evidence_class':'physical-board serial identity/service/output checks; no new finger or pixel observation','mode':mode,'bundle':candidate['bundle'],'system':system,'profile':profile,'kernel':candidate['kernel'],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'shell_executable':expected['rust'],'sway_executable':expected['sway'],'theme_helper':expected['helper'],'services':services,'normal_boot_files':normal,'appearance':appearance,'background_preferences_sha256':prefhash,'appearance_preserved':True,'rollback_roots_valid':True,'sway_outputs':[{k:out.get(k) for k in ('name','active','current_mode','transform','scale','rect')} for out in outputs],'operator_real_finger_observed':False,'additional_physical_collection_waived':True}
if installation:
 assert installation['result']=='PASS' and installation['qualification_evidence_class']=='operator-authorized-userspace-update'
 assert appearance==installation['appearance_before']==installation['appearance_after']
 report['installation_qualification_class']=installation['qualification_evidence_class']
body=(json.dumps(report,indent=2)+'\n').encode()
with urllib.request.urlopen(urllib.request.Request(endpoint+'/'+mode+'-runtime.json',data=body,method='POST'),timeout=30) as response:response.read()
print('K230_THEME_RUNTIME_PASS',flush=True)
