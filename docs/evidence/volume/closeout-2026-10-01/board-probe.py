"""Real PipeWire plus injected UI control proof on the physical board."""
import os,fcntl,struct,time,socket,json,subprocess,re,wave,math
from pathlib import Path
WP='/nix/store/6rp2g29qzvx266gijs50rlvhkpfc0ald-wireplumber-riscv64-unknown-linux-gnu-0.5.17/bin/wpctl'
PW='/nix/store/3xi5pr6wi4j61qv7p6dfmzrlg75ljk6x-pipewire-riscv64-unknown-linux-gnu-1.6.8/bin/'
ENV=['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell/bus']
subprocess.run(['systemctl','restart','shell-ui'],check=True);time.sleep(4)
checks={};captures=[];stream=None;window=None

def run(args):return subprocess.check_output(ENV+args,text=True,stderr=subprocess.DEVNULL,timeout=10)
def getvol(node='@DEFAULT_AUDIO_SINK@'):
 v=run([WP,'get-volume',str(node)]);return (float(re.search(r'Volume: ([0-9.]+)',v).group(1)),'MUTED' in v)
def setvol(p):run([WP,'set-volume','@DEFAULT_AUDIO_SINK@',str(p)]);run([WP,'set-mute','@DEFAULT_AUDIO_SINK@','0'])
def graph():return json.loads(run([PW+'pw-dump']))
def nodes(klass):return [v for v in graph() if (v.get('info') or {}).get('props',{}).get('media.class')==klass]
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

def wait(p,seconds=12):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if p():return
  time.sleep(.07)
 raise AssertionError('real volume/graph state not reached')
pid=subprocess.check_output(['systemctl','show','shell-ui','-p','MainPID','--value'],text=True).strip();rust=os.path.realpath('/proc/'+pid+'/exe')
def route(name):run([rust,'--surface',name]);time.sleep(1.7)
def capture(label):
 display=next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
 subprocess.run(ENV+['WAYLAND_DISPLAY='+display,'grim','-t','jpeg','-q','85','/run/shell/volume-proof-'+label+'.jpg'],check=True,stderr=subprocess.DEVNULL,timeout=20);captures.append(label)
def journal_count(event):return subprocess.check_output(['journalctl','-u','shell-ui','--no-pager','-o','cat'],text=True,timeout=8).count(event)
old=getvol();sink=nodes('Audio/Sink')[0];checks['real_sink_exists']=True
wav=Path('/run/shell/volume-proof.wav')
with wave.open(str(wav),'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);chunk=b''.join(struct.pack('<h',int(300*math.sin(2*math.pi*220*n/16000))) for n in range(16000));w.writeframes(chunk*150)
os.chown(wav,1000,995);os.chmod(wav,0o600)
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
 def up():emit([(3,0x39,-1),(1,0x14a,0)]);time.sleep(.6)
 def tap(x,y):down(x,y);time.sleep(.09);up()
 def drag(x1,x2,y):
  down(x1,y);time.sleep(.08)
  for n in range(1,13):move(x1+(x2-x1)*n/12,y);time.sleep(.035)
  up()
 route('hide');ipc('card_shell home');time.sleep(3);route('settings');time.sleep(1)
 down(100,500);time.sleep(.1);move(394,500);wait(lambda:abs(getvol()[0]-.75)<.025 and not getvol()[1]);checks['settings_live_held_drag_updates_hardware_route']=True;up();wait(lambda:abs(getvol()[0]-.75)<.025 and not getvol()[1]);checks['settings_drag_commits_75_percent']=True;capture('settings-75')
 drag(394,64,500);wait(lambda:getvol()[1]);checks['settings_zero_mutes']=True
 drag(64,328,500);wait(lambda:abs(getvol()[0]-.60)<.025 and not getvol()[1]);tap(38,500);wait(lambda:getvol()[1]);tap(38,500);wait(lambda:not getvol()[1] and abs(getvol()[0]-.60)<.025);checks['settings_icon_toggles_mute_and_preserves_level']=True
 route('hide');route('shade');drag(100,284,300);wait(lambda:abs(getvol()[0]-.50)<.025 and not getvol()[1]);checks['shade_slider_changes_real_sink']=True;capture('shade-50')
 route('hide');ipc('card_shell home');time.sleep(1);baseline=journal_count('volume-hud-commit');setvol(.41);wait(lambda:journal_count('volume-hud-commit')>baseline);capture('hud-over-home');checks['hud_maps_over_home_without_another_sheet']=True
 setvol(.48);time.sleep(.25);held_unmaps=journal_count('volume-hud-unmap');down(520,600);time.sleep(.1)
 for n in range(1,10):move(520,600+200*n/9);time.sleep(.04)
 time.sleep(3);checks['held_hud_contact_survives_auto_hide']=journal_count('volume-hud-unmap')==held_unmaps;assert checks['held_hud_contact_survives_auto_hide']
 baseline=journal_count('volume-hud-unmap');started=time.monotonic();up();capture('hud-dragged');wait(lambda:journal_count('volume-hud-unmap')>baseline,6);hide_seconds=round(time.monotonic()-started,3);checks['hud_auto_hides_after_release']=True;capture('hud-hidden')
 # A real PipeWire playback node, named/icon-labelled only for this proof.
 stream=subprocess.Popen(ENV+[PW+'pw-play','--properties={"application.name":"Volume proof","application.icon-name":"audio-x-generic","media.name":"Acceptance tone"}',str(wav)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 wait(lambda:any(v['info']['props'].get('application.name')=='Volume proof' for v in nodes('Stream/Output/Audio')));playing=next(v for v in nodes('Stream/Output/Audio') if v['info']['props'].get('application.name')=='Volume proof');checks['real_playback_stream_present']=True
 # Show the popup above an owned ordinary app; its canvas contains no user text.
 display=next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
 window=subprocess.Popen(ENV+['WAYLAND_DISPLAY='+display,'/run/current-system/sw/bin/foot','--app-id=k230-volume-proof','-e','/run/current-system/sw/bin/sleep','100'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd='/run/shell');time.sleep(2)
 def app_mapped(node):return node.get('app_id')=='k230-volume-proof' or any(app_mapped(c) for c in node.get('nodes',[])+node.get('floating_nodes',[]))
 wait(lambda:app_mapped(ipc('',4)));wait(lambda:'home_selected=0 ' in ipc('card_shell debug-scene')[0]['error'])
 baseline=journal_count('volume-hud-commit');setvol(.42);wait(lambda:journal_count('volume-hud-commit')>baseline);capture('hud-over-app');checks['hud_maps_over_an_ordinary_app']=True
 # Reposition persists until the client exits; return the pill near its default centre.
 down(520,800);time.sleep(.1);move(520,616);time.sleep(.2);up();tap(520,700);capture('expanded-real-stream')
 # One stream and one sink give a 340px expanded panel, top=446px.
 down(350,684);time.sleep(.1);move(449,684);wait(lambda:abs(getvol(playing['id'])[0]-.60)<.035);checks['stream_live_held_drag_updates_real_node']=True;up();wait(lambda:abs(getvol(playing['id'])[0]-.60)<.035);checks['expanded_stream_slider_changes_real_playback_node']=True
 tap(290,655);wait(lambda:getvol(playing['id'])[1]);checks['expanded_stream_label_toggles_mute']=True;tap(290,655)
 tap(400,734);checks['device_picker_real_sink_selected']=True
 sanitized={'id':sink['id'],'class':sink['info']['props']['media.class'],'name':sink['info']['props'].get('node.name'),'description':sink['info']['props'].get('node.description')}
 result={'result':'PASS','evidence_class':'physical-board-uinput-and-real-pipewire-graph','rust':rust,'system':os.path.realpath('/run/current-system'),'sink':sanitized,'checks':checks,'hud_hide_wait_after_release_seconds':hide_seconds,'captures':captures,'limits':['No claim that headphones or an external speaker were audible. No add-on is connected per user. Injected touch is not real-finger input. The generated playback tone proves a graph stream, not acoustic output.']}
 Path('/root/tmp/k230-deployment/volume-proof-result.json').write_text(json.dumps(result,indent=2));print('VOLUME_BOARD_CHECK_COMPLETE')
finally:
 if stream:stream.terminate()
 if window:
  window.terminate()
  try:window.wait(timeout=3)
  except subprocess.TimeoutExpired:window.kill()
 run([WP,'set-volume','@DEFAULT_AUDIO_SINK@',str(old[0])]);run([WP,'set-mute','@DEFAULT_AUDIO_SINK@','1' if old[1] else '0']);wav.unlink(missing_ok=True);fcntl.ioctl(f,0x5502);os.close(f);route('hide');ipc('card_shell home')
