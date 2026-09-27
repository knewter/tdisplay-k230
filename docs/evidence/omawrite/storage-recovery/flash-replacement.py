import datetime, hashlib, json, os, subprocess
from pathlib import Path
os.umask(0o077)
subprocess.run(['python3','/tmp/k230-replacement-preflight.py'],check=True)
root=Path(Path('/tmp/k230-demo-backup-dir').read_text().strip())
p=json.loads((root/'flash-preflight.json').read_text())
probe=json.loads((root/'capacity-probe-result.json').read_text())
assert probe['exit_code']==0 and probe['sampled_restore_matches_backup']
for tool in ['dd','date','stat','readlink','lsblk','xargs','bc','sync']:
 import shutil
 assert shutil.which(tool),tool
assert os.access(p['target'],os.W_OK)
saved_image=root/'nixos-replacement.img'
assert not saved_image.exists()
subprocess.run(['cp','--reflink=auto','--sparse=always',p['image'],str(saved_image)],check=True)
with saved_image.open('rb') as f:
 os.fsync(f.fileno())
 assert hashlib.file_digest(f,'sha256').hexdigest()==p['image_sha256']
with (root/'SHA256SUMS').open('a') as f:
 f.write(p['image_sha256']+'  nixos-replacement.img\n');f.flush();os.fsync(f.fileno())
args=['bash','tools/flash.sh',p['image'],p['target']]
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (root/'flash.log').open('w') as log:
 r=subprocess.run(args,input=p['target'][-12:]+'\n',text=True,stdout=log,stderr=subprocess.STDOUT)
result={'status':'PASS' if r.returncode==0 else 'FAIL','exit_code':r.returncode,'started_at_utc':started,'completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image':p['image'],'image_sha256':p['image_sha256'],'image_bytes':p['image_bytes'],'target_bytes':p['target_bytes'],'source_revision':p['source_revision'],'system':p['system'],'backup_sha256':p['backup_sha256'],'saved_replacement_image':'nixos-replacement.img','full_flash_readback':False,'board_boot_verified':False,'writer':'tools/flash.sh (dd oflag=sync conv=fsync)','authorization':'User requested preserving demo card in ~/tmp then installing current NixOS system.'}
(root/'flash-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
raise SystemExit(r.returncode)
