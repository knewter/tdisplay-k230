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
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+display,'grim','-t','jpeg','-q','85','/run/shell/search-'+label+'.jpg'],check=True,timeout=15)
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
 pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip()
 rust=os.path.realpath('/proc/'+pid+'/exe')
 def route(name):
  subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell',rust,'--surface',name],check=True,timeout=5)
 def mapped(name):return name+'_mapped=1 ' in scene()
 route('hide');time.sleep(.3);route('drawer');wait(lambda:mapped('drawer'));time.sleep(.5)
 capture('unfocused');tap(284,76);wait(lambda:mapped('keyboard'));time.sleep(.6);capture('focused')
 tap(28,998);capture('typed-q')
 tap(525,1132);wait(lambda:mapped('drawer') and mapped('keyboard'));capture('corrected')
 tap(525,1198);wait(lambda:not mapped('keyboard'));assert mapped('drawer');capture('dismissed')
 tap(284,76);wait(lambda:mapped('keyboard'));capture('reopened')
 Path('/root/tmp/k230-deployment/search-board-result.json').write_text(json.dumps({'evidence_class':'board-injected-uinput-and-native-capture','rust':rust,'drawer_stays_mapped_after_real_keyboard_backspace':True,'enter_hides_keyboard_only':True,'tap_reopens_keyboard':True,'scene':scene(),'limits':['Synthetic touch, not real-finger acceptance. Query changes and caret require capture inspection.']},indent=2))
 print('SEARCH_BOARD_CHECK_COMPLETE')
finally:
 fcntl.ioctl(f,0x5502);os.close(f)
