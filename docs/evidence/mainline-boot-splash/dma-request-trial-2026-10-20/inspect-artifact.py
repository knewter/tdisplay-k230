from pathlib import Path
import json,hashlib,struct,gzip,subprocess,datetime
b=Path(__file__).parent
candidate=Path((b/'splash-dma-candidate-stage1.path').read_text().strip())
original=b/'splash-dma-board'
sha=lambda d:hashlib.sha256(d).hexdigest()
files=lambda p:{x.name:dict(bytes=x.stat().st_size,sha256=sha(x.read_bytes())) for x in p.iterdir() if x.is_file()}
cf=files(candidate)
d=(candidate/'fn_ug_u-boot.bin').read_bytes()
assert d[:4]==b'K230'
n,en=struct.unpack('<II',d[4:12]);assert en==0 and n+528==len(d) and sha(d[528:])==d[12:44].hex()
msg=d[528:];assert msg[:4]==bytes(4) and msg[4:8]==bytes.fromhex('27051956')
import zlib
h=bytearray(msg[4:68]);header_crc=struct.unpack('>I',h[4:8])[0];h[4:8]=bytes(4)
assert zlib.crc32(h)==header_crc and struct.unpack('>I',h[12:16])[0]==len(msg)-68 and zlib.crc32(msg[68:])==struct.unpack('>I',h[24:28])[0]
z=bytearray(msg[68:]);assert z[:4]==bytes.fromhex('1f8b0900');z[2]=8;new=gzip.decompress(z)
old=(original/'u-boot-original.bin').read_bytes();assert len(old)==len(new)==765480
old_path='/nix/store/zzz867rp8drrwkhibj0rlqc04sk9g7f8-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10/lib'
new_path='/nix/store/blay9yis41g5wr52kwwr46m8sfxdkl68-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10/lib'
assert old.count(old_path.encode())==1 and new.count(new_path.encode())==1
normalized=old.replace(old_path.encode(),new_path.encode())
diff=[i for i,(a,z) in enumerate(zip(normalized,new)) if a!=z];assert diff==[35566]
assert old[35564:35568].hex()=='13070004' and new[35564:35568].hex()=='1307f004'
assert (candidate/'fn_u-boot-spl.bin').read_bytes()==(original/'spl-a-original.bin').read_bytes()==(original/'spl-b-original.bin').read_bytes()
unchanged={}
for dirname,names in [('rr7f6q64svn9kxlbc6f0ghm8367xxjv1-k230-stage1-env',['env.env','tdisplay.env']),('7qrz2jiip1f26pkf9fvhb01qbk3kaiih-k230-fw-jump',['fw_jump.bin','fw_jump_add_uboot_head.bin'])]:
 for name in names:
  p=Path('/nix/store')/dirname/name;assert (candidate/name).read_bytes()==p.read_bytes();unchanged[name]=str(p)
pre=json.loads((original/'preflight.json').read_text());assert cf['fw_jump_add_uboot_head.bin']['sha256']==pre['boot_files']['fw_jump_add_uboot_head.bin']['sha256']
patch=Path('nix/patches/uboot-k230/0004-rm69a10-logo-port.patch').read_bytes();assert patch==(b/'splash-dma-request-candidate.patch').read_bytes()
delta=subprocess.check_output(['git','diff','30dacf01','HEAD','--','nix/patches/uboot-k230/0004-rm69a10-logo-port.patch'],text=True)
assert delta.count('-+    writel(0x40,')==1 and delta.count('++    writel(0x4f,')==1
paths=subprocess.check_output(['git','diff','--name-only','30dacf01','HEAD'],text=True).splitlines();assert [x for x in paths if not x.startswith(('docs/','openspec/'))]==['nix/patches/uboot-k230/0004-rm69a10-logo-port.patch']
v=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),candidate_stage1=str(candidate),candidate_files=cf,baseline_class='Verified installed original bootloader/SPL raw backup; evaluated unchanged baseline environment/OpenSBI artifact references, with current boot OpenSBI hash match. No baseline rebuild claimed.',unchanged_files=unchanged,spl_matches_both_installed_copies=True,installed_uboot_comparison=dict(original_sha256=sha(old),candidate_sha256=sha(new),uncompressed_bytes=len(new),unmodified_byte_difference_count=sum(a!=z for a,z in zip(old,new)),build_metadata_path_before=old_path,build_metadata_path_after=new_path,normalized_byte_difference_offsets=diff,instruction_offset=35564,instruction_before_hex='13070004',instruction_after_hex='1307f004',instruction_before='addi a4,zero,64',instruction_after='addi a4,zero,79'),source_delta_only_dma_request=True,source_patch_sha256=sha(patch),firmware_sha_and_legacy_crc_checks=True,host_checks_passed=True,physical_fix_verified=False,baseline_command_disposition='Initial nix build <drv> selected the derivation file, not its output. Corrected output rebuild queued then cancelled while still waiting/no descendants: actual installed-byte comparison proves the needed behavior delta without an unnecessary rebuild.')
(b/'splash-dma-artifact-inspection.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v,indent=2))
