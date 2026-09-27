import datetime, fcntl, hashlib, json, os, stat, struct, subprocess, time
from pathlib import Path
os.umask(0o077)
root=Path('/tmp/k230-demo-backup-dir').read_text().strip()
root=Path(root)
meta=json.loads((root/'source.json').read_text())
target=Path(meta['target'])
assert str(target).startswith('/dev/disk/by-id/usb-')
assert str(target.resolve())==meta['device']
assert Path('/sys/class/block',target.resolve().name,'removable').read_text().strip()=='1'
mounts=subprocess.check_output(['lsblk','-nro','MOUNTPOINTS',str(target)],text=True)
assert not mounts.strip(), 'all card partitions must be unmounted'
size=meta['size']
assert size==64088965120
partial=root/'demo-card.img.partial'
image=root/'demo-card.img'
assert not image.exists()
start=time.monotonic(); count=0; digest=hashlib.sha256();last=0
with target.open('rb',buffering=0) as src, partial.open('xb',buffering=0) as dst:
 assert stat.S_ISBLK(os.fstat(src.fileno()).st_mode)
 assert struct.unpack('Q',fcntl.ioctl(src,0x80081272,b'\0'*8))[0]==size
 while count<size:
  b=src.read(min(4*1024*1024,size-count))
  if not b:raise RuntimeError('unexpected end of card')
  digest.update(b)
  view=memoryview(b)
  while view:
   n=dst.write(view)
   if not n:raise RuntimeError('short backup write')
   view=view[n:]
  count+=len(b)
  now=time.monotonic()
  if now-last>=15 or count==size:
   status={'phase':'reading-card','bytes':count,'total':size,'percent':round(count*100/size,2),'elapsed_seconds':round(now-start,1)}
   (root/'progress.json').write_text(json.dumps(status)+'\n')
   print(json.dumps(status),flush=True);last=now
 os.fsync(dst.fileno())
 assert struct.unpack('Q',fcntl.ioctl(src,0x80081272,b'\0'*8))[0]==size
(root/'progress.json').write_text(json.dumps({'phase':'verifying-backup-file','bytes':count,'total':size})+'\n')
with partial.open('rb') as saved:check=hashlib.file_digest(saved,'sha256').hexdigest()
assert check==digest.hexdigest(), 'backup verification mismatch'
assert partial.stat().st_size==size
partial.rename(image)
(root/'SHA256SUMS').write_text(check+'  demo-card.img\n')
result={'status':'PASS','source_bytes':size,'backup_bytes':image.stat().st_size,'sha256':check,'image':'demo-card.img','source_read_errors':0,'method':'single full source read with SHA-256, fsync, then independent SHA-256 reread of saved backup','completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-start,1)}
(root/'backup-result.json').write_text(json.dumps(result,indent=2)+'\n')
(root/'progress.json').write_text(json.dumps({'phase':'complete',**result})+'\n')
fd=os.open(root,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(result),flush=True)
