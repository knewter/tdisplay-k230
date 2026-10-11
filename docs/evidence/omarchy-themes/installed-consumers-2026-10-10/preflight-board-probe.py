from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
services={s:subprocess.check_output(['systemctl','is-active',s],text=True).strip() for s in ['shell','shell-ui','theme-helper','k230-touch-trackpad']}
def executable(s):
 pid=subprocess.check_output(['systemctl','show',s,'-p','MainPID','--value'],text=True).strip()
 return str(Path('/proc',pid,'exe').resolve(strict=True))
selection=Path('/home/shell/.local/state/omarchy/current/active'); active=selection.resolve(strict=True) if selection.exists() or selection.is_symlink() else None
preferences=Path('/home/shell/.local/state/omarchy/background-selections.json')
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system':str(Path('/run/current-system').resolve()),'profile':str(Path('/nix/var/nix/profiles/system').resolve()),'kernel':str(Path('/run/booted-system/kernel').resolve()),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'services':services,'shell_executable':executable('shell-ui'),'sway_executable':executable('shell'),'normal_boot_files':{n:hashlib.sha256((Path('/boot')/n).read_bytes()).hexdigest() for n in ['Image','initrd.uimg','k230-tdisplay.dtb','bootargs.txt','fw_jump_add_uboot_head.bin','force_dtb','lcd_dtb','hdmi_dtb']},'appearance':{'generation':active.name if active else None,'report_sha256':hashlib.sha256((active/'report.json').read_bytes()).hexdigest() if active and (active/'report.json').exists() else None},'background_preferences_sha256':hashlib.sha256(preferences.read_bytes()).hexdigest() if preferences.exists() else None,'root_free_bytes':shutil.disk_usage('/').free,'evidence_class':'read-only physical-board serial identity; no new finger observation'}
print('K230_THEME_PREFLIGHT '+json.dumps(report),flush=True)
