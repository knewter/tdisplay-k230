from pathlib import Path
import subprocess,shutil,hashlib,zlib,struct,json,os
system='/nix/store/xphf8zb00gz9hiyqkkh399rldr2ljykb-nixos-system-nixos-26.11.20260919.20b1ddd'
kernel='/nix/store/03zyl0mjsxbjyisb3lhjaxswpxm71ap6-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie/Image'
root=Path('/var/lib/k230-normal-boot-20261001');stage=root/'candidate';backup=root/'backup';assert not backup.exists()
assert Path('/run/current-system').resolve()==Path(system)
assert Path(system+'/kernel').resolve()==Path(kernel)
assert not Path('/nix-path-registration').exists()
assert subprocess.check_output(['findmnt','-nro','FSTYPE','/'],text=True).strip()=='ext4'
assert subprocess.check_output(['findmnt','-nro','LABEL','/'],text=True).strip()=='NIXOS_SD'
assert subprocess.check_output(['findmnt','-nro','SOURCE','/boot'],text=True).strip()=='/dev/mmcblk1p1'
assert shutil.disk_usage('/').free>400*1024**2
backup.mkdir(parents=True);stage.mkdir()
(root/'normal-profile.txt').write_text(str(Path('/nix/var/nix/profiles/system').resolve())+'\n')
files=['Image','initrd.uimg','k230-tdisplay.dtb','bootargs.txt','fw_jump_add_uboot_head.bin','force_dtb','lcd_dtb','hdmi_dtb']
for name in files: subprocess.run(['cp','--sparse=always','--preserve=mode,timestamps','/boot/'+name,str(backup/name)],check=True)
for name in ['k230-tdisplay.dtb','bootargs.txt']:shutil.copy2(Path(__file__).parent/name,stage/name)
subprocess.run(['cp','--sparse=always',kernel,str(stage/'Image')],check=True)
shutil.copy2(backup/'fw_jump_add_uboot_head.bin',stage/'fw_jump_add_uboot_head.bin')
payload=Path(system+'/initrd').read_bytes();header=struct.pack('>7I4B32s',0x27051956,0,0,len(payload),0,0,zlib.crc32(payload),5,26,3,0,b'initrd')
header=header[:4]+struct.pack('>I',zlib.crc32(header))+header[8:];(stage/'initrd.uimg').write_bytes(header+payload)
assert (stage/'bootargs.txt').read_text().endswith('init='+system+'/init\n')
def item(p):
 data=p.read_bytes();return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'crc32':f'{zlib.crc32(data):08x}'}
manifest={'system':system,'kernel':kernel,'initrd':str(Path(system+'/initrd').resolve()),'dtb_source':'/nix/store/yfda1lasmlgyappdgf6f49g7yj7m8mjd-k230-tdisplay.dtb','files':{p.name:item(p) for p in stage.iterdir()},'backup':{name:item(backup/name) for name in files},'normal_profile':(root/'normal-profile.txt').read_text().strip(),'boot_before':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');os.sync();print('K230_NORMAL_MANIFEST_BEGIN');print(json.dumps(manifest));print('K230_NORMAL_MANIFEST_END')
