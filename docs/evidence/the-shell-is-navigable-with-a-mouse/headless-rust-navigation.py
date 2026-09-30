import os,json,socket,struct,subprocess,time,tempfile
from pathlib import Path
SWAY='/nix/store/79la7mgp4dg2p0nxkiw0lqwvfmz7ygp2-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway'
RUST='/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/navigation-ux/nix/rust-shell-client/target/debug/k230-shell-rust'
procs=[];checks=[]
with tempfile.TemporaryDirectory(prefix='navigation-host-',dir='/home/jadams/tmp') as d:
 p=Path(d);(p/'apps').mkdir();(p/'state').mkdir();conf=p/'sway.conf';conf.write_text('output HEADLESS-1 mode 1080x1920\nseat seat0 fallback true\nfocus_follows_mouse no\n')
 env=dict(os.environ,XDG_RUNTIME_DIR=d,XDG_DATA_HOME=str(p/'apps'),XDG_DATA_DIRS=str(p/'apps'),XDG_STATE_HOME=str(p/'state'),WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_SHELL='1',SWAY_K230_CARD_TOUCH_FIRST='1',SWAY_K230_CARD_SURFACE_HELPER=RUST,K230_SETTINGS='/bin/false',K230_THEME_HELPER_SOCKET='',K230_THEME_COMMAND='',K230_CARD_APPEARANCE_SOCKET='')
 sl=(p/'sway.log').open('w');rl=(p/'rust.log').open('w')
 def wait(pred,seconds=25):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   r=pred()
   if r:return r
   time.sleep(.04)
  raise AssertionError('timeout: '+(p/'rust.log').read_text()[-1700:])
 def ipc(command):
  with socket.socket(socket.AF_UNIX) as sock:
   sock.settimeout(10);sock.connect(env['SWAYSOCK']);b=command.encode();sock.sendall(b'i3-ipc'+struct.pack('=II',len(b),0)+b)
   def read(n):
    b=b''
    while len(b)<n:b+=sock.recv(n-len(b))
    return b
   h=read(14);r=json.loads(read(struct.unpack('=II',h[6:])[0]));assert all(x['success'] for x in r),r
   return r
 def state():
  import re
  text=(p/'rust.log').read_text();matches=re.findall(r'pointer-state (.+)',text)
  return matches[-1] if matches else ''
 def click(x,y):
  ipc(f'seat seat0 cursor set {x} {y}; seat seat0 cursor press button1; seat seat0 cursor release button1');time.sleep(.7)
 def request(route):subprocess.run([RUST,'--surface',route],env=env,check=True);time.sleep(.8)
 def passed(label):checks.append(label);print('PASS '+label,flush=True)
 try:
  procs.append(subprocess.Popen(['/usr/bin/qemu-riscv64-static',SWAY,'-c',str(conf),'-d'],env=env,stdout=sl,stderr=sl))
  env['SWAYSOCK']=str(wait(lambda:next(iter(p.glob('sway-ipc.*.sock')),None)))
  env['WAYLAND_DISPLAY']=wait(lambda:next((x.name for x in p.glob('wayland-*') if not x.name.endswith('.lock')),None))
  import sys;sys.path.insert(0,'/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/navigation-ux/tests');from card_virtual_keyboard import Keyboard
  virtual=Keyboard.__new__(Keyboard);virtual.socket=socket.socket(socket.AF_UNIX);virtual.socket.settimeout(10);virtual.socket.connect(str(p/env['WAYLAND_DISPLAY']));virtual.serial=2;virtual.globals={};virtual.send(1,1,struct.pack('=I',2));virtual.roundtrip();virtual.bind('zwlr_virtual_pointer_manager_v1',4);virtual.bind('wl_seat',5);virtual.send(4,0,struct.pack('=II',5,6));virtual.serial=6;virtual.roundtrip()
  procs.append(subprocess.Popen([RUST,'--serve'],env=env,stdout=rl,stderr=rl));wait(lambda:bool((p/'rust.log').read_text()),seconds=60);time.sleep(5)
  request('drawer');click(540,42);wait(lambda:'drawer_mapped=0 ' in ipc('card_shell debug-scene')[0]['error']);passed('drawer handle dismiss')
  request('shade');click(980,75);wait(lambda:'route=Settings' in state());passed('shade Settings click')
  click(980,132);wait(lambda:'themes=List' in state());passed('Themes click')
  click(80,70);wait(lambda:'themes=Controls' in state());passed('Themes Back')
  click(1000,70);wait(lambda:'drawer_mapped=0 ' in ipc('card_shell debug-scene')[0]['error']);passed('Settings Done')
  Path('/home/jadams/tmp/k230-coordination/navigation-host-shell-result.json').write_text(json.dumps({'evidence_class':'headless-cross-compositor-native-rust-shell-injected-pointer','checks':checks,'limits':['No physical device proof.','Settings services unavailable deliberately; checks concern routing and dismissal.','Theme candidate wheel and actual Wi-Fi helpers require board matrix.']},indent=2)+'\n')
 finally:
  for proc in reversed(procs):
   if proc.poll() is None:proc.terminate()
   try:proc.wait(timeout=4)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  sl.close();rl.close()
  for name in ['sway','rust']:Path('/home/jadams/tmp/k230-coordination/navigation-host-'+name+'.log').write_text((p/(name+'.log')).read_text())
