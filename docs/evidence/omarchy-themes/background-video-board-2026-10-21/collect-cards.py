#!/usr/bin/env python3
"""Paired-background landscape trial; injected uinput, owned temporary Foot apps."""
import os,sys,time,json,struct,fcntl,socket,subprocess,shlex,importlib.util,threading
from pathlib import Path
mode=sys.argv[1];out=Path(sys.argv[2]);count=int(sys.argv[3]) if len(sys.argv)>3 else 6
revision=sys.argv[4];expected_system=sys.argv[5]
wanted_cards=int(sys.argv[6]);assert wanted_cards in (1,3)
owned=('one','two') if wanted_cards==3 else ()
selected_app='k230.motion.one' if owned else 'k230-terminal'
if not __import__('re').fullmatch(r'[0-9a-f]{40}',revision):raise SystemExit('explicit source revision required')
if str(Path('/run/current-system').resolve())!=expected_system:raise SystemExit('installed system differs from expected build')
if mode not in ('full','reduced') or not 1<=count<=12:raise SystemExit('invalid run')
out.mkdir(mode=0o700)
root=Path(__file__).parent
spec=importlib.util.spec_from_file_location('session_export',root/'card-shell-board-session.py');export=importlib.util.module_from_spec(spec);spec.loader.exec_module(export)
def cmd(args):return subprocess.check_output(args,text=True,timeout=25).strip()
def ipc(command='',kind=0):
 payload=command.encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(20);s.connect('/run/shell/sway-ipc.sock');s.sendall(b'i3-ipc'+struct.pack('=II',len(payload),kind)+payload)
  def read(n):
   b=b''
   while len(b)<n:
    chunk=s.recv(n-len(b))
    if not chunk:raise RuntimeError('closed IPC')
    b+=chunk
   return b
  header=read(14);n,_=struct.unpack('=II',header[6:]);r=json.loads(read(n))
 if kind==0 and not all(x.get('success') for x in r):raise RuntimeError('rejected IPC command')
 return r
def nodes(n):
 yield n
 for c in n.get('nodes',[])+n.get('floating_nodes',[]):yield from nodes(c)
def apps():return {n['app_id'] for n in nodes(ipc(kind=4)) if n.get('app_id')}
def capture(name):
 displays=[p.name for p in Path('/run/shell').glob('wayland-*') if p.is_socket()]
 if len(displays)!=1:raise RuntimeError('ambiguous Wayland display')
 data=subprocess.check_output(['sudo','-u','shell','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY='+displays[0],'PATH=/run/current-system/sw/bin','grim','-'],timeout=25)
 if not data.startswith(b'\x89PNG'):raise RuntimeError('invalid capture')
 (out/(name+'.png')).write_bytes(data)
metadata={'evidence_class':'board injected native touch; camera separate','mode':mode,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_revision':revision,'system':str(Path('/run/current-system').resolve()),'gestures':[]}
pid=cmd(['systemctl','show','shell.service','-p','MainPID','--value'])
env=dict(p.split(b'=',1) for p in Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in p)
actual='reduced' if env.get(b'SWAY_K230_CARD_REDUCED_MOTION')==b'1' else 'full'
if actual!=mode:raise RuntimeError('running compositor motion mode mismatch')
outputs=ipc(kind=3);active=[o for o in outputs if o.get('active')]
if len(active)!=1 or active[0]['transform']!='270' or active[0]['rect']['width']!=1232 or active[0]['rect']['height']!=568:raise RuntimeError('unexpected landscape output')
metadata['output']={k:active[0][k] for k in ['name','transform','rect','current_mode']}
for n in owned:
 if 'k230.motion.'+n in apps():raise RuntimeError('test app id already occupied')
# Preserve the fixed three-card workload: the startup terminal must already
# exist before either owned terminal can map. Never close foreign apps.
ready_deadline=time.monotonic()+35
while 'k230-terminal' not in apps():
 if time.monotonic()>ready_deadline:raise RuntimeError('startup terminal did not map before benchmark setup')
 time.sleep(.1)
if apps()!={'k230-terminal'}:raise RuntimeError('controlled workload requires exactly the startup terminal before setup')
metadata['startup_terminal_ready_before_owned_apps']=True
real=os.open('/dev/input/event1',os.O_RDONLY)
axes=[0,1,0x2f,0x30,0x35,0x36,0x39];info={}
for a in axes:
 b=bytearray(24);fcntl.ioctl(real,0x80184540+a,b);info[a]=struct.unpack('6i',b)
os.close(real)
fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
for bit in (0,1,3):fcntl.ioctl(fd,0x40045564,bit)
fcntl.ioctl(fd,0x40045565,0x14a)
for a in axes:fcntl.ioctl(fd,0x40045567,a)
fcntl.ioctl(fd,0x4004556e,1)
mx,mn=[0]*64,[0]*64
for a,v in info.items():mn[a],mx[a]=v[1],v[2]
b=struct.pack('80sHHHHi',b'K230 injected touchscreen',0x18,0,0,0,0)+struct.pack('64i',*mx)+struct.pack('64i',*mn)+struct.pack('64i',*[0]*64)*2
os.write(fd,b);fcntl.ioctl(fd,0x5501);time.sleep(1.0)
metadata['input_axes']={str(a):[v[1],v[2]] for a,v in info.items()}
event=struct.Struct('@llHHi')
def frame(events):
 b=b''.join(event.pack(0,0,*e) for e in [*events,(0,0,0)])
 if os.write(fd,b)!=len(b):raise RuntimeError('short input write')
def position(x,y):
 # Logical landscape -> native panel, then the controller's measured ranges.
 nx=y/567;ny=1-x/1231
 def raw(a,f):return round(info[a][1]+f*(info[a][2]-info[a][1]))
 return [(3,0x35,raw(0x35,nx)),(3,0x36,raw(0x36,ny)),(3,0,raw(0,nx)),(3,1,raw(1,ny))]
armed=False
resource_stop=threading.Event();external_resources=[];resource_errors=[]
def resource_loop():
 try:
  previous={}
  while not resource_stop.is_set():
   cpu=memory=0
   for unit in ('shell.service','shell-ui.service'):
    group=Path('/sys/fs/cgroup/system.slice')/unit
    st=group.stat();identity=(st.st_dev,st.st_ino)
    usage=int(dict(line.split(None,1) for line in (group/'cpu.stat').read_text().splitlines())['usage_usec'])
    mem=int((group/'memory.current').read_text())
    if unit in previous:
     assert previous[unit][0]==identity and usage>=previous[unit][1]
    assert usage>=0 and mem>=0
    previous[unit]=(identity,usage);cpu+=usage*1000;memory+=mem
   external_resources.append({'t_ns':time.monotonic_ns(),'cpu_ns':cpu,'memory_bytes':memory})
   resource_stop.wait(.25)
 except Exception as e:resource_errors.append(type(e).__name__)
resource_thread=None
try:
 # The Rust overlay route is already in the installed closure.
 subprocess.run(['sudo','-u','shell','env','XDG_RUNTIME_DIR=/run/shell','/run/current-system/sw/bin/k230-shell-rust','--surface','hide'],check=True,timeout=20)
 metadata['setup']={'terminal_mapping':'serialized one then two; each must map before next launch','initial_app_count':len(apps())}
 for n,color in ([('one','44'),('two','43')] if owned else []):
  shell="printf '\\033["+color+"m\\033[2J\\033[HMotion trace "+n+"\\n'; sleep 300"
  ipc('exec foot --app-id=k230.motion.'+n+' --title=Motion-'+n+' sh -c '+shlex.quote(shell))
  mapped_deadline=time.monotonic()+15
  while 'k230.motion.'+n not in apps():
   if time.monotonic()>mapped_deadline:raise RuntimeError('ordered test app failed to map')
   time.sleep(.1)
 end=time.monotonic()+15
 while not {'k230.motion.'+n for n in owned}<=apps():
  if time.monotonic()>end:raise RuntimeError('test apps failed to map')
  time.sleep(.1)
 ipc('card_shell back')
 ipc('[app_id="'+selected_app+'"] focus')
 focus_deadline=time.monotonic()+10
 while True:
  focused=[n.get('app_id') for n in nodes(ipc(kind=4)) if n.get('focused') and n.get('app_id')]
  if focused==[selected_app]:break
  if time.monotonic()>focus_deadline:raise RuntimeError('requested motion terminal failed to receive focus')
  time.sleep(.1)
 time.sleep(.5)
 focused=[n.get('app_id') for n in nodes(ipc(kind=4)) if n.get('focused') and n.get('app_id')]
 if focused!=[selected_app]:raise RuntimeError('focus changed before benchmark arm')
 if apps()!=({'k230-terminal'}|{'k230.motion.'+n for n in owned}):raise RuntimeError('unexpected app set before benchmark arm')
 metadata['setup']['focused_app_before_benchmark']=selected_app
 metadata['setup']['expected_app_set_verified']=True
 start_epoch=time.time();metadata['start_monotonic_ns']=time.monotonic_ns()
 resource_thread=threading.Thread(target=resource_loop,daemon=True);resource_thread.start()
 ipc('card_shell benchmark injected');armed=True;time.sleep(3.2)
 ipc('card_shell enter');time.sleep(1.0);capture('before')
 before_scene=ipc('card_shell debug-scene')[0]['error']
 selected=__import__('re').search(r'\bselected_app_id=([^ ]+)',before_scene)
 if not selected or selected.group(1)!=selected_app:raise RuntimeError('selected card changed during benchmark setup, before injection')
 metadata['setup']['selected_app_before_gestures']=selected.group(1)
 metadata['setup']['initial_app_count_verified']=1
 counter_names=['scene_redraw_coalesced','scene_timer_coalesced','scene_render_syncs','scene_structural_syncs']
 def scene_counters(text):
  out={}
  for k in counter_names:
   m=__import__('re').search(r'\b'+k+r'=(\d+)',text)
   if not m:raise RuntimeError('coalescing counter unavailable: '+k)
   out[k]=int(m.group(1))
  return out
 metadata['scene_counters_before_gestures']=scene_counters(before_scene)
 for i in range(count):
  x0,x1=616,(366 if i%2==0 else 866);y=280
  g={'index':i,'from':[x0,y],'to':[x1,y],'down_monotonic_ns':time.monotonic_ns()}
  frame([(3,0x2f,0),(3,0x39,100+i),(3,0x30,20),(1,0x14a,1),*position(x0,y)])
  time.sleep(.05);begin=time.monotonic()
  steps=35 if count>1 else 16;duration=.7 if count>1 else .32
  for k in range(1,steps+1):
   time.sleep(max(0,begin+duration*k/steps-time.monotonic()));frame(position(x0+(x1-x0)*k/steps,y))
  if i==0 and count==1:capture('held')
  frame([(3,0x39,-1),(1,0x14a,0)]);g['up_monotonic_ns']=time.monotonic_ns()
  time.sleep(.8);metadata['gestures'].append(g)
 capture('after');metadata['back_requested_ns']=time.monotonic_ns();ipc('card_shell back');metadata['back_acknowledged_ns']=time.monotonic_ns();time.sleep(3.2);ipc('card_shell benchmark-stop');armed=False
 resource_stop.set();resource_thread.join(timeout=3);assert not resource_thread.is_alive();assert not resource_errors
 (out/'external-session-resources.json').write_text(json.dumps({'units':['shell.service','shell-ui.service'],'samples':external_resources,'limits':'Measured sum of the two service cgroups; distinct from compositor-emitted per-process RSS. No RSS/PID sampling or relabeling of raw compositor telemetry.'},indent=2)+'\n')
 raw=cmd(['journalctl','-u','shell.service','--since','@'+str(int(start_epoch)),'--no-pager','-o','cat','--grep=K230_CARD_(BENCH|SHELL (motion-|input-origin))','-n','30000'])
 clean=export.normalized_journal(raw)
 (out/'telemetry.log').write_text(clean)
 metadata['scene_counters_after_benchmark']=scene_counters(ipc('card_shell debug-scene')[0]['error'])
 metadata['scene_counter_deltas']={k:metadata['scene_counters_after_benchmark'][k]-metadata['scene_counters_before_gestures'][k] for k in counter_names}
 metadata['end_monotonic_ns']=time.monotonic_ns();metadata['telemetry_lines']=len(clean.splitlines())
 (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
 print(json.dumps({'status':'captured','mode':mode,'gestures':len(metadata['gestures']),'lines':metadata['telemetry_lines'],'directory':str(out)}),flush=True)
finally:
 resource_stop.set()
 if resource_thread:resource_thread.join(timeout=3)
 if armed:
  try:ipc('card_shell benchmark-stop')
  except Exception:pass
 try:frame([(3,0x39,-1),(1,0x14a,0)])
 except Exception:pass
 fcntl.ioctl(fd,0x5502);os.close(fd)
 for n in owned:
  try:ipc('[app_id="k230.motion.'+n+'"] kill')
  except Exception:pass

 try:ipc('card_shell home')
 except Exception:pass
