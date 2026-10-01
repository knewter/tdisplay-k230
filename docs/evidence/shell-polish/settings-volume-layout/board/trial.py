from pathlib import Path
import os,sys,json,time,subprocess,hashlib,fcntl,struct,urllib.request,pwd,uuid
SOURCE='5bb67db128210f830dab4de0d20a4b0eca13c578'
CANDIDATE='/nix/store/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-nixos-system-nixos-26.11.20260919.20b1ddd'
RUST='/nix/store/3hy6h165ii649z6vjzjd36jwg16d37rc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
HELPER='/nix/store/sklk0aqz51qc17nwgpfw5ysavb3xmv1l-handheld-theme-command-0.1'
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
WP='/nix/store/6rp2g29qzvx266gijs50rlvhkpfc0ald-wireplumber-riscv64-unknown-linux-gnu-0.5.17/bin/wpctl'
ROOT=Path('/root/tmp/k230-settings-controls');ROOT.mkdir(parents=True,exist_ok=True)
ENV=['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell/bus','PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin']
STATE=Path('/home/shell/.local/state/omarchy/current')
def call(args,timeout=60):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout).stdout
def boot():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/boot').iterdir() if p.is_file()}
baseline=str(Path('/run/current-system').resolve());profile=str(Path('/nix/var/nix/profiles/system').resolve());before_boot=boot();original=str((STATE/'active').resolve());st=(STATE/'active').lstat()
assert baseline in ['/nix/store/ija989s4f2la7ms4zbr9dnirpnnp8qyg-nixos-system-nixos-26.11.20260919.20b1ddd',CANDIDATE]
for name in ['kernel','initrd','kernel-modules']:assert (Path(baseline)/name).resolve()==(Path(CANDIDATE)/name).resolve()
restore=ROOT/'restore.py';restore.write_text('from pathlib import Path\nimport subprocess,os\np=Path('+repr(str(STATE/'active'))+');t=p.parent/".volume-layout-restore";t.unlink(missing_ok=True);t.symlink_to('+repr(original)+');os.chown(t,'+str(st.st_uid)+','+str(st.st_gid)+',follow_symlinks=False);os.replace(t,p)\nsubprocess.run(['+repr(baseline+'/bin/switch-to-configuration')+',"test"],check=True)\nsubprocess.run(["systemctl","restart","shell-ui","theme-helper"],check=True)\n')
timer='k230-settings-controls-restore';call(['systemd-run','--unit='+timer,'--on-active=900s',PYTHON,str(restore)])
report={'source':SOURCE,'class':'physical-board-runtime-activation-native-captures-and-uinput','candidate':CANDIDATE,'rust':RUST,'helper':HELPER,'checks':{},'captures':[],'started_epoch_s':time.time(),'boot_acceptance':False,'finger_acceptance':False}
def activate(generation):
 code='import sys;from pathlib import Path;sys.path.insert(0,'+repr(HELPER+'/libexec/handheld-theme')+');import theme_transaction as tx;eps=[Path("/run/shell/k230-shell-rust-appearance.sock"),Path("/run/shell/k230-card-appearance.sock")];tx.activate_generation(Path(sys.argv[1]),state_root=Path('+repr(str(STATE))+'),endpoint=eps[0],endpoints=eps)'
 call(ENV+[PYTHON,'-c',code,str(generation)],90)
def route(name):call(ENV+[RUST,'--surface',name]);time.sleep(2)
def capture(name):
 target=Path('/run/shell/settings-controls-'+name);call(ENV+['grim',str(target)]);report['captures'].append({'name':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'generation':(STATE/'active').resolve().name});return target
def png_rows(path):
 import zlib
 data=path.read_bytes();pos=8;parts=[]
 while pos<len(data):
  length=int.from_bytes(data[pos:pos+4],'big');kind=data[pos+4:pos+8];body=data[pos+8:pos+8+length];pos+=12+length
  if kind==b'IHDR':width,height,depth,color=struct.unpack('>IIBB',body[:10])
  if kind==b'IDAT':parts.append(body)
 assert depth==8 and color in [2,6]
 bpp=3 if color==2 else 4;stride=width*bpp;raw=zlib.decompress(b''.join(parts));rows=[];prior=bytearray(stride)
 for y in range(min(height,800)):
  filt=raw[y*(stride+1)];row=bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
  for x in range(stride):
   left=row[x-bpp] if x>=bpp else 0;above=prior[x];corner=prior[x-bpp] if x>=bpp else 0
   if filt==1:value=left
   elif filt==2:value=above
   elif filt==3:value=(left+above)//2
   elif filt==4:
    q=left+above-corner;dl=abs(q-left);da=abs(q-above);dc=abs(q-corner);value=left if dl<=da and dl<=dc else above if da<=dc else corner
   else:assert filt==0;value=0
   row[x]=(row[x]+value)&255
  rows.append(row);prior=row
 return bpp,rows
fd=None;old_volume=None;captures=[]
try:
 call([CANDIDATE+'/bin/switch-to-configuration','test'],180);time.sleep(5)
 assert str(Path('/run/current-system').resolve())==CANDIDATE
 pid=int(call(['systemctl','show','shell-ui','-p','MainPID','--value']));assert os.readlink('/proc/'+str(pid)+'/exe')==RUST
 assert call(['systemctl','is-active','shell','shell-ui','theme-helper']).splitlines()==['active']*3
 report['checks']['full_runtime_and_services_match_build']=True
 fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
 for bit in [1,3]:fcntl.ioctl(fd,0x40045564,bit)
 fcntl.ioctl(fd,0x40045565,0x14a);fcntl.ioctl(fd,0x4004556e,1)
 for code,m in [(0x2f,9),(0x39,65535),(0x35,567),(0x36,1231)]:
  fcntl.ioctl(fd,0x40045567,code);fcntl.ioctl(fd,0x401c5504,struct.pack('=H2xiiiiii',code,0,0,m,0,0,20 if code in [0x35,0x36] else 0))
 fcntl.ioctl(fd,0x405c5503,struct.pack('=HHHH80sI',3,0x1234,0x5678,1,b'K230 Shell Gesture Test Source',0));fcntl.ioctl(fd,0x5501);time.sleep(.7)
 def emit(events):
  t=time.monotonic_ns();os.write(fd,b''.join(struct.pack('=qqHHi',t//10**9,t//1000%1000000,*e) for e in events+[(0,0,0)]))
 def down(x,y):emit([(3,0x2f,0),(3,0x39,101),(3,0x35,int(x)),(3,0x36,int(y)),(1,0x14a,1)])
 def move(x,y):emit([(3,0x35,int(x)),(3,0x36,int(y))])
 def up():emit([(3,0x39,-1),(1,0x14a,0)]);time.sleep(.7)
 def tap(x,y):down(x,y);time.sleep(.09);up()
 route('settings');time.sleep(10)
 pre=Path('/run/shell/settings-controls-precondition.png');call(ENV+['grim',str(pre)]);bpp,rows=png_rows(pre)
 assert rows[500][100*bpp:101*bpp]!=rows[515][100*bpp:101*bpp],'Settings volume slider was not loaded before the tap'
 report['checks']['settings_volume_loaded_before_picker_tap']=True
 old_volume=call(ENV+[WP,'get-volume','@DEFAULT_AUDIO_SINK@']).strip()
 before=call(['journalctl','-u','shell-ui','--no-pager','-o','cat']).count('volume-hud-commit')
 tap(260,457)
 picker=capture('output-picker.png')
 # Capture before reading the full journal: its I/O can outlast HUD auto-hide.
 after=call(['journalctl','-u','shell-ui','--no-pager','-o','cat']).count('volume-hud-commit')
 assert after>before,'Moved output-detail tap did not map the volume HUD'
 report['checks']['moved_output_detail_maps_picker']=True
 new_bpp,new_rows=png_rows(picker);assert bpp==new_bpp
 before_region=b''.join(r[300*bpp:558*bpp] for r in rows[470:790]);after_region=b''.join(r[300*bpp:558*bpp] for r in new_rows[470:790]);assert before_region!=after_region,'Expanded picker did not change its actual pixels'
 report['checks']['expanded_picker_pixels_change']=True;captures.append(picker)
 # Retire the expanded HUD before testing the track independently.
 call(['systemctl','restart','shell-ui']);time.sleep(5);route('settings')
 down(100,500);time.sleep(.09)
 for i in range(1,10):move(100+(328-100)*i/9,500);time.sleep(.035)
 up();time.sleep(2)
 current=call(ENV+[WP,'get-volume','@DEFAULT_AUDIO_SINK@']).strip()
 report['checks']['slider_changes_real_sink']=current!=old_volume
 assert report['checks']['slider_changes_real_sink'],'Slider did not change the real sink'
 import re
 old_value=re.search(r'Volume: ([0-9.]+)',old_volume).group(1)
 call(ENV+[WP,'set-volume','@DEFAULT_AUDIO_SINK@',old_value]);call(ENV+[WP,'set-mute','@DEFAULT_AUDIO_SINK@','1' if 'MUTED' in old_volume else '0']);time.sleep(3)
 for label,name in [('dark','catppuccin'),('light','catppuccin-latte')]:
  prepared=json.loads(call(ENV+[HELPER+'/bin/omarchy-theme-set',name,'--prepare-only'],90));generation=Path(prepared['generation_path']);activate(generation);route('settings');time.sleep(5);captures.append(capture(label+'-settings.png'))
 activate(original);call(['systemctl','restart','shell-ui']);time.sleep(4);route('hide');call(ENV+['swaymsg','card_shell home'])
 report['checks']['original_theme_restored']=(STATE/'active').resolve()==Path(original)
 report['checks']['boot_and_profile_preserved']=boot()==before_boot and str(Path('/nix/var/nix/profiles/system').resolve())==profile
 report['checks']['volume_restored']=call(ENV+[WP,'get-volume','@DEFAULT_AUDIO_SINK@']).strip()==old_volume
 report['checks']['final_services_active']=call(['systemctl','is-active','shell','shell-ui','theme-helper']).splitlines()==['active']*3
 assert all(report['checks'].values()),report['checks']
 call(['systemctl','stop',timer+'.timer']);report['result']='PASS';report['runtime_retained']=True;report['restore_command']=PYTHON+' '+str(restore)
 (ROOT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 for target in captures:urllib.request.urlopen(urllib.request.Request(sys.argv[1]+'/'+target.name.replace('settings-controls-',''),data=target.read_bytes(),method='POST'),timeout=30).read()
 urllib.request.urlopen(urllib.request.Request(sys.argv[1]+'/result.json',data=(ROOT/'result.json').read_bytes(),method='POST'),timeout=30).read()
 print('K230_SETTINGS_CONTROLS_PASS',flush=True)
except BaseException:
 if old_volume:
  import re
  call(ENV+[WP,'set-volume','@DEFAULT_AUDIO_SINK@',re.search(r'Volume: ([0-9.]+)',old_volume).group(1)]);call(ENV+[WP,'set-mute','@DEFAULT_AUDIO_SINK@','1' if 'MUTED' in old_volume else '0'])
 call([PYTHON,str(restore)],180);call(['systemctl','stop',timer+'.timer']);raise
finally:
 if fd is not None:
  fcntl.ioctl(fd,0x5502);os.close(fd)
