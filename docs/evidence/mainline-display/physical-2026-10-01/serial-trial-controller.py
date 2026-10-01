from pathlib import Path
import importlib.util,fcntl,time,json,re,sys,uuid
p=Path('/home/jadams/tmp/k230-coordination');m=json.loads((p/'mainline-boot-manifest.json').read_text());mode=sys.argv[1]
if mode=='baseline':
 m['files']=m['backup'];m['system']='/nix/store/x1xbs5qdb5gn91j6s7gsi8mg18qra5ah-nixos-system-nixos-26.11.20260919.20b1ddd'
trial_dir='backup' if mode=='baseline' else 'candidate'
out=p/('mainline-boot-'+mode+'.private.log')
spec=importlib.util.spec_from_file_location('ums',Path.cwd()/'tools/ums-session.py');ums=importlib.util.module_from_spec(spec);spec.loader.exec_module(ums)
class Session(ums.Session):
 def send_line(self,text,kill=True):
  if kill:self.port.write(b'\x15');self.port.flush();time.sleep(.05)
  self.note('sending: '+text);self.buf=b'';self.port.write(text.encode()+b'\r');self.port.flush()
 def pump(self):
  chunk=self.port.read(65536)
  if chunk:self.log.write(chunk);self.buf=(self.buf+chunk)[-131072:]
  return chunk
 def note(self,text):self.log.write((self.stamp()+'--- '+text+' ---\n').encode())
with open('/tmp/k230-board.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=Session('/dev/ttyACM0',115200,str(out));in_uboot=False
 try:
  s.port.write(b'\x03\r');s.port.flush();time.sleep(.4);s.pump();s.send_line('reboot');deadline=time.monotonic()+35
  while time.monotonic()<deadline:
   s.pump()
   if b'Hit any key to stop autoboot' in s.buf:
    s.port.write(b' ');s.port.flush()
   if b'K230# ' in s.buf:break
  else:raise RuntimeError('No U-Boot prompt; no file load attempted')
  in_uboot=True
  if mode in ('candidate','diagnostic','candidate2','baseline'):
   for cmd in ['mmc list','ext4ls mmc 1:1 /','printenv bootcmd','printenv blinux']:
    if s.cmd_output(cmd,30) is None:raise RuntimeError('preflight command failed')
   for name,part,addr in [('bootargs.txt','1:2','0x7000000'),('fw_jump_add_uboot_head.bin','1:1','0x8000000'),('Image-mainline-drm','1:2','0x200000'),('k230-tdisplay-mainline-drm.dtb','1:2','0x8400000'),('initrd.uimg','1:2','0x9000000')]:
    path='/fw_jump_add_uboot_head.bin' if part=='1:1' else '/var/lib/k230-mainline-drm-trial/'+name
    reply=s.cmd_output('ext4load mmc '+part+' '+addr+' '+path,90);expected=m['files'][name]
    if reply is None or re.findall(rb'(?m)^([0-9]+) bytes read',reply)!=[str(expected['bytes']).encode()]:raise RuntimeError('load-size mismatch '+name)
    reply=s.cmd_output('crc32 '+addr+' '+hex(expected['bytes']),40)
    if reply is None or re.findall(rb'==> ([0-9a-fA-F]{8})',reply)!=[expected['crc32'].encode()]:raise RuntimeError('CRC mismatch '+name)
   reply=s.cmd_output('env import -t 0x7000000 '+hex(m['files']['bootargs.txt']['bytes']),15)
   if mode=='diagnostic':
    reply=s.cmd_output('setenv bootargs \"${bootargs} systemd.log_level=debug systemd.log_target=console systemd.show_status=1 rd.udev.log_level=debug\"',15)
   reply=s.cmd_output('printenv bootargs',15)
   if reply is None or ('init='+m['system']+'/init').encode() not in reply:raise RuntimeError('wrong trial init')
   s.send_line('bootm 0x8000000 0x9000000 0x8400000');in_uboot=False
  elif mode=='persistent':s.send_line('boot');in_uboot=False
  elif mode=='restore':s.send_line('reset');in_uboot=False
  else:raise ValueError(mode)
  if not s.wait_for(b'nixos login:',180):raise RuntimeError('Linux login deadline exceeded')
  s.wait_for(b'root@nixos',30);s.send_line('echo K230_PHYSICAL_BOOT_IDENTITY; uname -r; cat /proc/cmdline; readlink -f /run/current-system; readlink -f /nix/var/nix/profiles/system; cat /proc/sys/kernel/random/boot_id; findmnt /; cat /proc/bus/input/devices; dmesg | grep -iE \'drm|dsi|panel|power|goodix|touch|failed|error\'; echo K230_PHYSICAL_BOOT_END')
  if not s.wait_for(b'\r\nK230_PHYSICAL_BOOT_END\r\n',90):raise RuntimeError('postboot evidence incomplete')
  print('Physical '+mode+' boot reached Linux and identity/services were captured; inspect transcript')
 except Exception as e:
  print('Boot trial failure:',str(e))
  if in_uboot:
   s.send_line('reset');print('Reset to untouched normal boot files; login observed:',s.wait_for(b'nixos login:',180))
  raise
 finally:s.port.close();s.log.close()
