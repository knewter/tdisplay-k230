#!/usr/bin/env python3
"""Headless QEMU pixel proof for the private Sway deck appearance endpoint."""
import argparse,json,os,pathlib,socket,struct,subprocess,time
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
for field in ('sway','client','output'):
 parser.add_argument('--'+field,required=True)
parser.add_argument('--qemu',default='/usr/bin/qemu-riscv64-static')
args=parser.parse_args()
out=pathlib.Path(args.output)
out.mkdir(mode=0o700,exist_ok=False)
base=pathlib.Path(__file__).resolve().parents[1]
sway=args.sway
qemu=args.qemu
client=args.client
default_id='20f2d477bb758593d831e427'; next_id='222222222222222222222222'
default=out/'default/generations'/default_id;default.mkdir(parents=True)
state=out/'state';candidate=state/'generations'/next_id;candidate.mkdir(parents=True)
report=json.loads((base/'nix/handheld-theme-default/default-report.json').read_text())
appearance=json.loads((base/'nix/handheld-theme-default/default-appearance.json').read_text())
(default/'report.json').write_text(json.dumps(report))
(default/'appearance.json').write_text(json.dumps(appearance))
report['generation']=next_id
appearance['generation']=next_id
appearance['sections']['card']={
 'canvas':{'kind':'brush','stops':[{'argb':'#ffff0000','offset':0},{'argb':'#ff0000ff','offset':1}], 'angle_degrees':90,'alpha':1},
 'selected-background':{'kind':'brush','stops':[{'argb':'#ff00ff00','offset':0},{'argb':'#ffffff00','offset':1}], 'angle_degrees':90,'alpha':1},
 'background':{'kind':'brush','stops':[{'argb':'#ff003300','offset':0},{'argb':'#ff00ffff','offset':1}], 'angle_degrees':90,'alpha':1},
 'text':{'kind':'brush','stops':[{'argb':'#ffff00ff','offset':0}], 'angle_degrees':0,'alpha':1}}
(candidate/'report.json').write_text(json.dumps(report))
(candidate/'appearance.json').write_text(json.dumps(appearance))
config=out/'sway.conf';config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\nfor_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48\n')
env=dict(os.environ,XDG_RUNTIME_DIR=str(out),WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_SHELL='1',SWAY_K230_CARD_TOUCH_FIRST='1',SWAY_K230_CARD_APPEARANCE_SOCKET=str(out/'card-appearance.sock'),SWAY_K230_CARD_THEME_STATE_ROOT=str(state),SWAY_K230_CARD_THEME_DEFAULT=str(default))
processes=[];logs={}
def spawn(name,command):
 f=(out/(name+'.log')).open('w');logs[name]=f
 p=subprocess.Popen(command,env=env,stdout=f,stderr=f);processes.append(p);return p
def wait(predicate,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  value=predicate()
  if value:return value
  time.sleep(.05)
 raise AssertionError('timeout')
def ipc(command,kind=0):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect(str(next(out.glob('sway-ipc.*.sock'))))
  data=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(data),kind)+data)
  def read(n):
   data=b''
   while len(data)<n:
    chunk=s.recv(n-len(data));assert chunk;data+=chunk
   return data
  header=read(14);n,_=struct.unpack('=II',header[6:]);result=json.loads(read(n))
  if kind==0: assert all(r['success'] for r in result),(command,result)
  return result
def exchange(phase,id,path,**extra):
 request={'protocol':1,'phase':phase,'generation':id,'path':str(path) if path else None,**extra}
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(4);s.connect(str(out/'card-appearance.sock'))
  s.sendall(json.dumps(request).encode()+b'\n')
  reply=b''
  while not reply.endswith(b'\n'):
   chunk=s.recv(256);assert chunk;reply+=chunk
  result=json.loads(reply)
  assert result['status']=='ok',(request,result)
  return result
def capture(name):
 subprocess.run(['grim',str(out/name)],env=env,check=True)
 return Image.open(out/name).convert('RGB')
try:
 spawn('sway',[qemu,sway,'-c',str(config),'-d'])
 wait(lambda:'Running compositor on wayland display' in (out/'sway.log').read_text(),60)
 env['WAYLAND_DISPLAY']=next(p.name for p in out.glob('wayland-*') if not p.name.endswith('.lock'))
 wait(lambda:(out/'card-appearance.sock').exists())
 spawn('client',[client,'--app-id','k230.card.one'])
 wait(lambda:'k230.card.one' in json.dumps(ipc('',4)))
 ipc('card_shell enter');time.sleep(.3)
 before=capture('before.png')
 exchange('prepare',next_id,candidate,previous_generation=None,previous_path=None)
 (state/'active').symlink_to(candidate)
 exchange('commit',next_id,candidate)
 time.sleep(.3)
 themed=capture('themed.png')
 assert themed.getpixel((10,500)) != before.getpixel((10,500))
 assert themed.getpixel((10,500)) != themed.getpixel((558,500))
 assert themed.getpixel((80,500)) != themed.getpixel((480,500))
 (state/'active').unlink()
 exchange('rollback',None,None)
 time.sleep(.3)
 restored=capture('restored.png')
 for x,y in ((10,500),(80,500),(480,500)):
  assert restored.getpixel((x,y)) == before.getpixel((x,y)),(x,y,restored.getpixel((x,y)),before.getpixel((x,y)))
 result={'result':'PASS','class':'headless-qemu-appearance','before_canvas':before.getpixel((10,500)),'themed_canvas_left':themed.getpixel((10,500)),'themed_canvas_right':themed.getpixel((558,500)),'themed_card_left':themed.getpixel((80,500)),'themed_card_right':themed.getpixel((480,500)),'restored_canvas':restored.getpixel((10,500)),'sway':sway}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
finally:
 for p in reversed(processes):
  if p.poll() is None:p.terminate()
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:p.kill()
 for f in logs.values():f.close()
