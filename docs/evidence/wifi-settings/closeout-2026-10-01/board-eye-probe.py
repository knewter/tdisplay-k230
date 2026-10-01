"""UI-only dummy Wi-Fi entry on the actual board; never opens the radio."""
import os,fcntl,struct,time,socket,json,subprocess,threading
from pathlib import Path
ROOT=Path('/run/k230-wifi-eye-proof'); ROOT.mkdir(mode=0o750,exist_ok=True);os.chown(ROOT,0,995)
srv=socket.socket(socket.AF_UNIX);sock=ROOT/'broker.sock';sock.unlink(missing_ok=True);srv.bind(str(sock));os.chmod(sock,0o660);os.chown(sock,0,995);srv.listen(4)
operations=[]
def broker():
 while True:
  try:c,_=srv.accept()
  except OSError:return
  with c:
   c.settimeout(3);b=b''
   while not b.endswith(b'\n') and len(b)<=4096:
    part=c.recv(4096)
    if not part:break
    b+=part
   v=json.loads(b);op=v['op'];assert op in ('scan','status'), 'fixture must never connect or change saved config';operations.append(op)
   a={'schema':1,'state':'ok','current':None,'saved':[],'error':None}
   if op=='scan':a['networks']=[{'ssid':'Example','security':'wpa2-psk'}]
   c.sendall(json.dumps(a).encode()+b'\n')
threading.Thread(target=broker,daemon=True).start()
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
def mapped(name):return name+'_mapped=1 ' in scene()
def wait(p):
 end=time.monotonic()+12
 while time.monotonic()<end:
  if p():return
  time.sleep(.05)
 raise RuntimeError('expected state not reached: '+scene())
def capture(label):
 display=next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+display,'grim','-t','jpeg','-q','85','/run/shell/wifi-eye-'+label+'.jpg'],check=True,timeout=20)

override=Path('/run/systemd/system/shell-ui.service.d/97-wifi-eye-proof.conf');override.parent.mkdir(parents=True,exist_ok=True);override.write_text('[Service]\nEnvironment=K230_WIFI_SOCKET='+str(sock)+'\n')
subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell-ui'],check=True);time.sleep(3)
f=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
try:
 for bit in [1,3]:fcntl.ioctl(f,0x40045564,bit)
 fcntl.ioctl(f,0x40045565,0x14a);fcntl.ioctl(f,0x4004556e,1)
 for code,m in [(0x2f,9),(0x39,65535),(0x35,567),(0x36,1231)]:
  fcntl.ioctl(f,0x40045567,code);fcntl.ioctl(f,0x401c5504,struct.pack('=H2xiiiiii',code,0,0,m,0,0,20 if code in [0x35,0x36] else 0))
 fcntl.ioctl(f,0x405c5503,struct.pack('=HHHH80sI',3,0x1234,0x5678,1,b'K230 Shell Gesture Test Source',0));fcntl.ioctl(f,0x5501);time.sleep(.7)
 def tap(x,y):
  for events in [[(3,0x2f,0),(3,0x39,101),(3,0x35,x),(3,0x36,y),(1,0x14a,1),(0,0,0)],[(3,0x2f,0),(3,0x39,-1),(1,0x14a,0),(0,0,0)]]:
   t=time.monotonic_ns();os.write(f,b''.join(struct.pack('=qqHHi',t//10**9,t//1000%1000000,*e) for e in events));time.sleep(.10)
  time.sleep(.35)
 pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip();rust=os.path.realpath('/proc/'+pid+'/exe')
 def route(name):subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell',rust,'--surface',name],check=True,timeout=5)
 route('hide');time.sleep(.3);route('settings');time.sleep(2);capture('settings-before');tap(284,210);wait(lambda:'scan' in operations);time.sleep(1);capture('dummy-list')
 tap(284,378);wait(lambda:mapped('keyboard'));time.sleep(.8);capture('masked-empty')
 for _ in range(8):tap(28,998)
 capture('masked-typed');tap(504,350);assert mapped('keyboard');capture('revealed')
 tap(525,1132);assert mapped('keyboard');capture('revealed-corrected')
 tap(28,998);capture('revealed-retyped');tap(504,350);capture('hidden-again')
 tap(120,720);wait(lambda:not mapped('keyboard'));time.sleep(.4);tap(284,378);wait(lambda:mapped('keyboard'));capture('reopened-masked-empty')
 route('hide');time.sleep(.5)
 Path('/root/tmp/k230-deployment/wifi-eye-result.json').write_text(json.dumps({'evidence_class':'board-injected-uinput-and-native-capture','rust':rust,'system':os.path.realpath('/run/current-system'),'fixture':'one invented network, no radio operations or persistence','operations':operations,'keyboard_stays_mapped_during_eye_and_backspace':True,'cancel_lowers_keyboard':True,'reopen_raises_keyboard':True,'limits':['Image review is required for visibility and text. Injected touches are not real-finger input. Existing connection/reboot/Forget acceptance is the user report.']},indent=2))
 print('WIFI_EYE_BOARD_CHECK_COMPLETE')
finally:
 fcntl.ioctl(f,0x5502);os.close(f);srv.close();override.unlink(missing_ok=True);subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell-ui'],check=True)
