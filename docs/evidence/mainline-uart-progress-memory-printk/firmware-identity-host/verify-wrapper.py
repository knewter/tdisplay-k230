"""Reproduce existing OpenSBI wrapper identity; no build or hardware access."""
import argparse,hashlib,json,os,struct,zlib
from pathlib import Path
os.umask(0o077)
p=argparse.ArgumentParser()
p.add_argument('--payload',type=Path,required=True)
p.add_argument('--normal-report',type=Path,required=True)
p.add_argument('--trial-result',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
b=a.payload.read_bytes()
assert len(b)==270744
assert hashlib.sha256(b).hexdigest()=='74d08f8701dc72ea166d74be62fc3e5bff437d7c73ab68ad2f113cab289c38f9'
# nix/stage1.nix: SOURCE_DATE_EPOCH and mkimage -A riscv -O linux
# -T kernel -C none -a 0 -e 0 -n linux. Legacy U-Boot image header:
# magic, header CRC, timestamp, data size, load, entry, data CRC,
# OS/Linux=5, arch/RISC-V=26, type/kernel=2, compression/none=0, name.
h=struct.pack('>7I4B32s',0x27051956,0,1700000000,len(b),0,0,zlib.crc32(b),5,26,2,0,b'linux'.ljust(32,b'\0'))
h=h[:4]+struct.pack('>I',zlib.crc32(h))+h[8:]
wrapped=h+b
r=json.loads(a.normal_report.read_text())['boot_files']['fw_jump_add_uboot_head.bin']
t=json.loads(a.trial_result.read_text())
assert len(wrapped)==r['bytes']==270808
assert hashlib.sha256(wrapped).hexdigest()==r['sha256']=='9627edbeea9b115d7040beea27cc61b23b6aca61cd502fd7760d7ee179f42c99'
assert t['normal_preflight']['boot_files']['fw_jump_add_uboot_head.bin']==r['sha256']
result={'schema':'k230-opensbi-wrapper-identity-host-v1','evidence_class':'host deterministic wrapper reconstruction tied to prior physical protected-file preflight','payload':str(a.payload),'payload_bytes':len(b),'payload_sha256':hashlib.sha256(b).hexdigest(),'wrapper_bytes':len(wrapped),'wrapper_sha256':r['sha256'],'matches_protected_normal_file':True,'matches_nohz_trial_protected_preflight':True,'source_date_epoch':1700000000,'header_crc32':h[4:8].hex(),'payload_crc32':format(zlib.crc32(b),'08x'),'new_firmware_build':False,'new_board_readback':False,'runtime_timer_branch':'UNVERIFIED','fault_cause':'UNVERIFIED'}
with a.output.open('x')as f:f.write(json.dumps(result,indent=2)+'\n')
print('Existing OpenSBI payload plus deterministic header matches the protected wrapper SHA256; no build or board access.')
