import fcntl,importlib.util,json,os,re,shlex,time,uuid
from pathlib import Path
import serial
os.umask(0o077)
wt=Path('/home/jadams/tmp/k230-row-memtrace'); d=Path.home()/'tmp/k230-session-b-install';e=wt/'docs/evidence/theme-picker/board-session-2026-10-12b/install'
spec=importlib.util.spec_from_file_location('rd',wt/'tools/mainline-drm-initrd-shell-trial.py');rd=importlib.util.module_from_spec(spec);spec.loader.exec_module(rd)
code='''from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
services={s:subprocess.check_output(['systemctl','is-active',s],text=True).strip() for s in ['shell','shell-ui','theme-helper','k230-touch-trackpad']}
def executable(s):
 pid=subprocess.check_output(['systemctl','show',s,'-p','MainPID','--value'],text=True).strip()
 return str(Path('/proc',pid,'exe').resolve(strict=True))
selection=Path('/home/shell/.local/state/omarchy/current/active'); active=selection.resolve(strict=True) if selection.exists() or selection.is_symlink() else None
preferences=Path('/home/shell/.local/state/omarchy/background-selections.json')
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system':str(Path('/run/current-system').resolve()),'profile':str(Path('/nix/var/nix/profiles/system').resolve()),'kernel':str(Path('/run/booted-system/kernel').resolve()),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'services':services,'shell_executable':executable('shell-ui'),'sway_executable':executable('shell'),'normal_boot_files':{n:hashlib.sha256((Path('/boot')/n).read_bytes()).hexdigest() for n in ['Image','initrd.uimg','k230-tdisplay.dtb','bootargs.txt','fw_jump_add_uboot_head.bin','force_dtb','lcd_dtb','hdmi_dtb']},'appearance':{'generation':active.name if active else None,'report_sha256':hashlib.sha256((active/'report.json').read_bytes()).hexdigest() if active and (active/'report.json').exists() else None},'background_preferences_sha256':hashlib.sha256(preferences.read_bytes()).hexdigest() if preferences.exists() else None,'root_free_bytes':shutil.disk_usage('/').free,'evidence_class':'read-only physical-board serial identity; no new finger observation'}
print('K230_THEME_PREFLIGHT '+json.dumps(report),flush=True)
'''
with open('/tmp/k230-board.lock','a') as lock,(d/('preflight-'+uuid.uuid4().hex+'.private.log')).open('xb',buffering=0) as log:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=rd.PrivateSession(serial,log)
 try:
  s.write(b'\r');assert s.wait_for(b'root@nixos',20),'board root prompt absent'
  token=uuid.uuid4().hex; s.upload_text('/run/k230-mainline-theme-preflight.py',code,token)
  marker='K230_THEME_PREFLIGHT_RC_'+token
  s.line(shlex.join([rd.BOARD_PYTHON,'-I','/run/k230-mainline-theme-preflight.py'])+"; printf '\n"+marker+"=%s\n' $?",interrupt=False)
  end=time.monotonic()+90;m=None
  while time.monotonic()<end and not m:s.pump();m=re.search(rb'\n'+marker.encode()+rb'=([0-9]+)\r?\n',s.buffer)
  assert m and int(m[1])==0,'preflight failed; raw UART is private'
  raw=s.buffer[s.buffer.rindex(b'K230_THEME_PREFLIGHT {')+len(b'K230_THEME_PREFLIGHT '):]
  report,_=json.JSONDecoder().raw_decode(re.sub(rb'[\r\n]',b'',raw).decode());known=json.loads((wt/'docs/evidence/theme-picker/row-sprites-2026-10-12/ordinary-runtime.json').read_text())
  for k in ['system','profile','kernel','shell_executable','sway_executable','normal_boot_files']:assert report[k]==known[k],'baseline differs: '+k
  assert all(x=='active' for x in report['services'].values()),'baseline service health differs'
  (e/'preflight.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: accepted baseline identities and four active services; appearance saved',flush=True)
 finally:s.close()
