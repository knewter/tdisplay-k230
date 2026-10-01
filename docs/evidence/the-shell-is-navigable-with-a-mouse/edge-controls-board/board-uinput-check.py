import os,fcntl,struct,time,socket,json,subprocess
from pathlib import Path

def ipc(command):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect('/run/shell/sway-ipc.sock');b=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(b),0)+b)
  def read(n):
   b=b''
   while len(b)<n:
    c=s.recv(n-len(b));assert c;b+=c
   return b
  h=read(14);r=json.loads(read(struct.unpack('=II',h[6:])[0]));assert all(x['success'] for x in r),r;return r

def scene():return ipc('card_shell debug-scene')[0]['error']
def wait(p):
 end=time.monotonic()+5
 while time.monotonic()<end:
  if p():return
  time.sleep(.04)
 raise RuntimeError(scene())
def capture(label):
 display=next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+display,'grim','-t','jpeg','-q','85','/run/shell/edge-'+label+'.jpg'],check=True,timeout=15)
f=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
try:
 for bit in [1,3]:fcntl.ioctl(f,0x40045564,bit)
 fcntl.ioctl(f,0x40045565,0x14a);fcntl.ioctl(f,0x4004556e,1)
 for code,m in [(0x2f,9),(0x39,65535),(0x35,567),(0x36,1231)]:
  fcntl.ioctl(f,0x40045567,code);fcntl.ioctl(f,0x401c5504,struct.pack('=H2xiiiiii',code,0,0,m,0,0,20 if code in [0x35,0x36] else 0))
 fcntl.ioctl(f,0x405c5503,struct.pack('=HHHH80sI',3,0x1234,0x5678,1,b'K230 Shell Gesture Test Source',0));fcntl.ioctl(f,0x5501);time.sleep(.7)
 def tap(x,y):
  for events in [[(3,0x2f,0),(3,0x39,101),(3,0x35,x),(3,0x36,y),(1,0x14a,1),(0,0,0)],[(3,0x2f,0),(3,0x39,-1),(1,0x14a,0),(0,0,0)]]:
   t=time.monotonic_ns();os.write(f,b''.join(struct.pack('=qqHHi',t//10**9,t//1000%1000000,*e) for e in events));time.sleep(.09)
  time.sleep(.25)
 ipc('card_shell home');time.sleep(.35)
 tap(284,1220);wait(lambda:'active=1 ' in scene());capture('home-handle-overview')
 ipc('card_shell home');time.sleep(.35)
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','/nix/store/qbi2i7cq00i6z8mshh17bq8vcr7dk3ds-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust','--surface','drawer'],check=True,timeout=5)
 wait(lambda:'drawer_mapped=1 ' in scene());time.sleep(.5)
 tap(284,76);tap(50,972);capture('search-q')
 tap(60,1214);wait(lambda:'drawer_mapped=1 ' in scene());capture('search-backspace')
 Path('/root/tmp/k230-deployment/edge-board-result.json').write_text(json.dumps({'evidence_class':'board-injected-uinput-and-native-capture','home_handle_overview':True,'drawer_stays_mapped_after_bottom_backspace':True,'scene':scene(),'limits':['Captured query mutation and physical feel need separate inspection/acceptance.']}))
 print('EDGE_BOARD_CHECK_COMPLETE')
finally:
 fcntl.ioctl(f,0x5502);os.close(f)
