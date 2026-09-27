import fcntl, hashlib, json, os, stat, struct, subprocess
from pathlib import Path
root=Path(Path('/tmp/k230-demo-backup-dir').read_text().strip())
meta=json.loads((root/'source.json').read_text())
proof=json.loads((root/'backup-result.json').read_text())
assert proof['status']=='PASS' and proof['source_read_errors']==0
assert proof['source_bytes']==proof['backup_bytes']==meta['size']==64088965120
backup=root/proof['image']
assert backup.stat().st_size==meta['size']
assert (root/'SHA256SUMS').read_text().split()[0]==proof['sha256']
target=Path(meta['target'])
assert str(target).startswith('/dev/disk/by-id/usb-')
assert str(target.resolve())==meta['device']
assert Path('/sys/class/block',target.resolve().name,'removable').read_text().strip()=='1'
assert not subprocess.check_output(['lsblk','-nro','MOUNTPOINTS',str(target)],text=True).strip()
with target.open('rb',buffering=0) as src,backup.open('rb',buffering=0) as old:
 assert stat.S_ISBLK(os.fstat(src.fileno()).st_mode)
 assert struct.unpack('Q',fcntl.ioctl(src,0x80081272,b'\0'*8))[0]==meta['size']
 for off in [0,meta['size']//2,meta['size']-1024*1024]:
  src.seek(off);old.seek(off)
  assert src.read(1024*1024)==old.read(1024*1024),'card changed since backup'
image=Path('/tmp/k230-replacement-image.out').read_text().strip()
assert image.startswith('/nix/store/') and Path(image).is_file()
assert 128*1024*1024<Path(image).stat().st_size<meta['size']
with open(image,'rb') as f:image_hash=hashlib.file_digest(f,'sha256').hexdigest()
layout=json.loads(subprocess.check_output(['sfdisk','--json',image],text=True))['partitiontable']
assert layout['label']=='dos'
parts=layout['partitions']
assert len(parts)==2 and parts[0]['start']==8192 and parts[1]['start']==262144
assert all(p['type']=='83' for p in parts)
result={'status':'PASS','backup_directory':str(root),'backup_sha256':proof['sha256'],'image':image,'image_sha256':image_hash,'image_bytes':Path(image).stat().st_size,'target':str(target),'target_bytes':meta['size'],'target_matches_backup_samples':True,'system':'/nix/store/cmhsqwvzwp3bad15wv5znk4w35wx65d5-nixos-system-nixos-26.11.20260919.20b1ddd','source_revision':meta['source_revision']}
(root/'flash-preflight.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='target'},indent=2))
