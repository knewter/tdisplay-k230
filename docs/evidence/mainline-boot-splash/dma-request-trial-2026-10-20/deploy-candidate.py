"""Guarded, once-only U-Boot-proper write; invoke only under pane23 board lease."""
from pathlib import Path
import subprocess,shlex,json,hashlib,datetime
b=Path(__file__).parent;out=b/'splash-dma-board';pre=json.loads((out/'preflight.json').read_text());build=json.loads((b/'splash-dma-artifact-inspection.json').read_text());assert build['host_checks_passed'] and build['source_delta_only_dma_request'];artifact=Path(build['candidate_stage1'])/'fn_ug_u-boot.bin';payload=artifact.read_bytes();sha=hashlib.sha256(payload).hexdigest();assert 528<len(payload)<1048576;assert sha==build['candidate_files']['fn_ug_u-boot.bin']['sha256'];assert pre['backup_verified_both_sides'];stage='/var/lib/k230/splash-dma-request-20261020';ssh=['ssh','-F','/home/jadams/tmp/k230-coordination/ssh_config.private','k230'];py='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
# Send to a new protected regular file; remote verifies before any raw write.
code='''from pathlib import Path
import os,sys,hashlib,json,struct,subprocess
root=Path(STAGE);backup=root/'preboot-first-4MiB.bin';old=backup.read_bytes();assert len(old)==4194304 and hashlib.sha256(old).hexdigest()==BACKUP_SHA
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT_ID
assert os.path.realpath('/run/current-system')==SYSTEM
assert Path('/sys/class/block/mmcblk1p1/start').read_text().strip()=='8192'
saved=json.loads((root/'preflight.json').read_text())
for name,record in saved['boot_files'].items():
 p=Path('/boot')/name;assert p.stat().st_size==record['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],'boot file changed since backup'
new=sys.stdin.buffer.read();assert len(new)==NEW_LEN and hashlib.sha256(new).hexdigest()==NEW_SHA
assert new[:4]==b'K230';length,encryption=struct.unpack('<II',new[4:12]);assert length+528==len(new) and encryption==0
assert hashlib.sha256(new[528:]).digest()==new[12:44]
candidate=root/'candidate-fn_ug_u-boot.bin'
with candidate.open('xb') as f:f.write(new);f.flush();os.fsync(f.fileno())
with open('/dev/mmcblk1','r+b',buffering=0) as f:
 before=subprocess.check_output(['dd','if=/dev/mmcblk1','bs=4096','count=1024','iflag=direct','status=none']);assert before==old,'boot region changed since backup; stop'
 f.seek(2097152);written=f.write(new);assert written==len(new);os.fsync(f.fileno());f.seek(0);after=subprocess.check_output(['dd','if=/dev/mmcblk1','bs=4096','count=1024','iflag=direct','status=none'])
 expected=old[:2097152]+new+old[2097152+len(new):]
 if after!=expected:
  f.seek(2097152);assert f.write(old[2097152:3145728])==1048576;os.fsync(f.fileno());f.seek(0);assert f.read(4194304)==old;raise RuntimeError('candidate readback mismatch; original restored')
report=dict(status='CANDIDATE_WRITTEN_AND_READBACK_VERIFIED',candidate_sha256=hashlib.sha256(new).hexdigest(),candidate_bytes=len(new),offset=2097152,after_first4MiB_sha256=hashlib.sha256(after).hexdigest(),unchanged_prefix=after[:2097152]==old[:2097152],unchanged_after_candidate=after[2097152+len(new):]==old[2097152+len(new):],backup_sha256=hashlib.sha256(old).hexdigest(),reboot_requested=False,direct_readback=True)
(root/'deployment.json').write_text(json.dumps(report,indent=2)+'\\n');print(json.dumps(report))
'''
values={'STAGE':stage,'BACKUP_SHA':pre['backup_sha256'],'BOOT_ID':pre['boot_id'],'SYSTEM':pre['systems']['/run/current-system'],'NEW_LEN':len(payload),'NEW_SHA':sha}
for key,value in values.items():code=code.replace(key,repr(value))
p=subprocess.run(ssh+[py+' -c '+shlex.quote(code)],input=payload,capture_output=True,timeout=60);(out/'deploy.private.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode();v=json.loads(p.stdout);v.update(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),command_driver=str(Path(__file__)),candidate_stage1=str(artifact.parent));(out/'deployment.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2))
