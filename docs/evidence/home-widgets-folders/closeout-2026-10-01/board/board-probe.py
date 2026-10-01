"""Real-board injected-touch Home acceptance; uses an isolated layout."""
import os,fcntl,struct,time,socket,json,subprocess
from pathlib import Path
ROOT=Path('/run/k230-home-proof');ROOT.mkdir(mode=0o700,exist_ok=True);os.chown(ROOT,1000,995)
state=ROOT/'state/k230-shell';state.mkdir(parents=True,exist_ok=True)
for p in [ROOT/'state',state]:os.chown(p,1000,995)
layout_file=state/'home.json';checks={};captures=[]
def app(name):return {'kind':'app','id':name}
apps=['foot.desktop','htop.desktop','dev.tchx84.Portfolio.desktop']
def layout():
 p=[[None]*20 for _ in range(2)];p[0][0]=app(apps[0]);p[0][1]=app(apps[1]);p[0][2]=app(apps[2]);p[1][0]=app('k230-clock.desktop')
 return {'schema':2,'columns':4,'pages':p,'dock':[None]*4}
def save(v):layout_file.write_text(json.dumps(v));os.chown(layout_file,1000,995)
def current():return json.loads(layout_file.read_text())
save(layout())
def ipc(command,kind=0):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect('/run/shell/sway-ipc.sock');b=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(b),kind)+b)
  def read(n):
   b=b''
   while len(b)<n:
    c=s.recv(n-len(b));assert c;b+=c
   return b
  h=read(14);r=json.loads(read(struct.unpack('=II',h[6:])[0]));
  if kind==0:assert all(x['success'] for x in r),r
  return r

def scene():return ipc('card_shell debug-scene')[0]['error']
def wait(p,seconds=12):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if p():return
  time.sleep(.05)
 raise AssertionError('state not reached: '+scene())
def capture(label):
 display=next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+display,'grim','-t','jpeg','-q','85','/run/shell/home-proof-'+label+'.jpg'],check=True,timeout=20);captures.append(label)

override=Path('/run/systemd/system/shell-ui.service.d/97-home-proof.conf');override.parent.mkdir(parents=True,exist_ok=True);override.write_text('[Service]\nEnvironment=XDG_STATE_HOME='+str(ROOT/'state')+'\n')
def restart():
 subprocess.run(['systemctl','restart','shell-ui'],check=True);time.sleep(4);ipc('card_shell home');time.sleep(1.4)
subprocess.run(['systemctl','daemon-reload'],check=True);restart()
f=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
try:
 for bit in [1,3]:fcntl.ioctl(f,0x40045564,bit)
 fcntl.ioctl(f,0x40045565,0x14a);fcntl.ioctl(f,0x4004556e,1)
 for code,m in [(0x2f,9),(0x39,65535),(0x35,567),(0x36,1231)]:
  fcntl.ioctl(f,0x40045567,code);fcntl.ioctl(f,0x401c5504,struct.pack('=H2xiiiiii',code,0,0,m,0,0,20 if code in [0x35,0x36] else 0))
 fcntl.ioctl(f,0x405c5503,struct.pack('=HHHH80sI',3,0x1234,0x5678,1,b'K230 Shell Gesture Test Source',0));fcntl.ioctl(f,0x5501);time.sleep(.7)
 def emit(events):
  t=time.monotonic_ns();os.write(f,b''.join(struct.pack('=qqHHi',t//10**9,t//1000%1000000,*e) for e in events+[(0,0,0)]))
 def down(x,y):emit([(3,0x2f,0),(3,0x39,101),(3,0x35,int(x)),(3,0x36,int(y)),(1,0x14a,1)])
 def move(x,y):emit([(3,0x35,int(x)),(3,0x36,int(y))])
 def up():emit([(3,0x39,-1),(1,0x14a,0)]);time.sleep(.5)
 def tap(x,y):down(x,y);time.sleep(.09);up()
 def slot(i):return (80.75+135.5*(i%4),203+184*(i//4))
 def drag(start,end,hold=.7):
  down(*start);time.sleep(hold)
  for n in range(1,13):move(start[0]+(end[0]-start[0])*n/12,start[1]+(end[1]-start[1])*n/12);time.sleep(.035)
  time.sleep(.2);up()
 def done():tap(482,80)
 capture('initial-isolated-home')
 drag(slot(0),slot(1));wait(lambda:current()['pages'][0][1] and current()['pages'][0][1]['kind']=='folder');checks['home_drag_creates_folder']=True;done();capture('folder-created')
 drag(slot(2),slot(1));wait(lambda:len(current()['pages'][0][1]['apps'])==3);checks['drag_joins_existing_folder']=True;done()
 tap(*slot(1));capture('folder-open');tap(284,148);wait(lambda:'keyboard_mapped=1 ' in scene());time.sleep(.6)
 for _ in range(6):tap(525,1132)
 for _ in range(4):tap(28,998)
 tap(525,1198);wait(lambda:current()['pages'][0][1].get('name')=='qqqq');checks['real_system_keyboard_renames_folder']=True;wait(lambda:'keyboard_mapped=0 ' in scene());capture('folder-renamed')
 # Extract member zero (the original destination app) and retain two members.
 drag((101,271),slot(4));wait(lambda:current()['pages'][0][4]==app(apps[1]));checks['folder_member_dragged_out_to_requested_cell']=True;capture('member-extracted');done()
 # Move the remaining folder into the first dock slot.
 drag(slot(1),(80,1148));wait(lambda:current()['dock'][0] and current()['dock'][0]['kind']=='folder');checks['folder_moves_to_dock']=True;done();tap(80,1148);capture('dock-folder-open');tap(540,1100)
 # Long press blank space -> Widgets -> drag Clock row into requested footprint.
 down(*slot(12));time.sleep(.7);up();capture('widget-picker-menu');tap(284,186);capture('widget-picker');drag((284,292),slot(8));wait(lambda:current()['pages'][0][8]=={'kind':'widget','widget':'clock'});checks['picker_places_clock_at_requested_cell']=True;done();capture('clock-placed')
 before=current();restart();checks['layout_survives_shell_restart']=current()==before;capture('persisted-home')
 # Repeat edge turns while one contact remains held; continue past the last page.
 v=layout();v['pages'].append([None]*20);save(v);restart()
 down(*slot(0));time.sleep(.7)
 for n in range(1,15):move(slot(0)[0]+(558-slot(0)[0])*n/14,slot(0)[1]);time.sleep(.04)
 time.sleep(.15);capture('edge-indicator');time.sleep(1.9);move(*slot(4));time.sleep(.2);up()
 wait(lambda:any(app(apps[0]) in page for page in current()['pages'][3:]));checks['edge_repeat_creates_new_page_and_keeps_drop']=True;done();capture('new-page-drop')
 # Fast interior displacement, never reaching the 40px edge band.
 save(layout());restart();down(*slot(0));time.sleep(.7);move(400,203);time.sleep(.03);move(410,203);time.sleep(.3);move(*slot(4));time.sleep(.12);up()
 wait(lambda:app(apps[0]) in current()['pages'][1]);checks['interior_fling_pages_without_edge_dwell']=True;done();capture('fling-drop')
 # Native production rendering of every clock style and absent-battery/weather.
 for name,widget in [('bubble','clock'),('thin','clock_minimal'),('dot-matrix','clock_dot_matrix'),('battery','clock')]:
  v=layout();v['pages']=[[None]*20];v['pages'][0][0]={'kind':'widget','widget':'clock_analog'};v['pages'][0][2]={'kind':'widget','widget':'weather'};v['pages'][0][8]={'kind':'widget','widget':widget};v['pages'][0][0]={'kind':'widget','widget':'battery' if name=='battery' else 'clock_analog'};save(v);restart();time.sleep(2);capture('widgets-'+name)
 checks['battery_attachment_absent']=not any(Path('/sys/class/power_supply').iterdir())
 cache=Path('/home/shell/.cache/k230-shell/weather.json');checks['weather_disk_cache_present']=cache.is_file()
 pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip()
 Path('/root/tmp/k230-deployment/home-proof-result.json').write_text(json.dumps({'result':'PASS','evidence_class':'physical-board-uinput-injection-and-native-captures','checks':checks,'rust':os.path.realpath('/proc/'+pid+'/exe'),'system':os.path.realpath('/run/current-system'),'captures':captures,'limits':['Not real-finger acceptance or a daylight contrast measurement. No battery attachment exists. Test layout is isolated; original user layout is untouched.']},indent=2))
 print('HOME_BOARD_CHECK_COMPLETE')
finally:
 fcntl.ioctl(f,0x5502);os.close(f);override.unlink(missing_ok=True);subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','restart','shell-ui'],check=True);time.sleep(3);ipc('card_shell home')
