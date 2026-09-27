import os,sys,json,time,pwd,socket,subprocess,pathlib,urllib.request,importlib.util,datetime
os.umask(0o077)
target,url,phase=sys.argv[1:]
assert str(pathlib.Path('/run/current-system').resolve())==target
root=pathlib.Path('/run/k230-background-fix-control')
uid=pwd.getpwnam('shell').pw_uid
spec=importlib.util.spec_from_file_location('touch',str(root/'touch.py'));touch=importlib.util.module_from_spec(spec);spec.loader.exec_module(touch)
device='/dev/input/event1';touch.verify_device(device)
def rpc(**request):
 os.seteuid(uid)
 try:
  with socket.socket(socket.AF_UNIX) as sock:
   sock.settimeout(30);sock.connect('/run/shell/theme-helper.sock');sock.sendall(json.dumps(request).encode()+b'\n')
   data=b''
   while b'\n' not in data:data+=sock.recv(65536)
  reply=json.loads(data);assert reply['exit_code']==0,reply
  return reply['result']
 finally:os.seteuid(0)
def shell(*args):
 return subprocess.check_output(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1',*args],timeout=20)
def capture(name):
 path='/run/shell/k230-background-'+name
 shell('grim',path)
 data=pathlib.Path(path).read_bytes()
 urllib.request.urlopen(urllib.request.Request(url+'/'+name,data=data,method='POST'),timeout=20).read()
def picker():
 shell('k230-shell-rust','--surface','settings');time.sleep(2)
 touch.native_touch(device,480,130);time.sleep(6)
def home():
 ipc=pathlib.Path('/run/shell/sway-ipc.sock')
 if not (root/'parked-app.json').exists():
  tree=json.loads(shell('swaymsg','-s',str(ipc),'-t','get_tree'))
  apps=[]
  def visit(node,workspace=None):
   if node['type']=='workspace':workspace=node['name']
   if node.get('app_id'):apps.append({'id':node['id'],'workspace':workspace})
   for child in node.get('nodes',[])+node.get('floating_nodes',[]):visit(child,workspace)
  visit(tree);assert len(apps)==1, 'expected the single open test terminal'
  (root/'parked-app.json').write_text(json.dumps(apps[0]))
  shell('swaymsg','-s',str(ipc),f"[con_id={apps[0]['id']}] move scratchpad")
 workspaces=json.loads(shell('swaymsg','-s',str(ipc),'-t','get_workspaces'))
 if not (root/'previous-workspace.json').exists():
  (root/'previous-workspace.json').write_text(json.dumps(next(w['name'] for w in workspaces if w['focused'])))
 shell('swaymsg','-s',str(ipc),'workspace k230-background-proof')
 shell('k230-shell-rust','--surface','hide');time.sleep(2)
active=pathlib.Path('/home/shell/.local/state/omarchy/current/active')
if phase=='inspect':
 listing=rpc(action='list');current=rpc(action='preview',id=listing['active']['id'])
 (root/'initial.json').write_text(json.dumps(current))
 home();capture('before.png');picker();capture('reopened.png')
 print('K230_TRACE_CATALOG '+json.dumps({'theme':current['theme']['label'],'generation':current['generation'],'backgrounds':[{'label':r['label'],'kind':r['kind'],'selected':r['selected']} for r in current['backgrounds']]}),flush=True)
elif phase=='apply':
 initial=json.loads((root/'initial.json').read_text());rows=initial['backgrounds'];old=next(i for i,r in enumerate(rows) if r['selected'])
 chosen=min((i for i,r in enumerate(rows) if not r['selected'] and r['kind']=='image'),key=lambda i:abs(i-old))
 for _ in range(abs(chosen-old)):
  touch.native_touch(device,508 if chosen>old else 60,990);time.sleep(2)
 started=time.monotonic();touch.native_touch(device,284,990)
 deadline=time.monotonic()+35
 while active.resolve().name==initial['generation'] and time.monotonic()<deadline:time.sleep(.3)
 assert active.resolve().name!=initial['generation'],'selection did not activate'
 time.sleep(4);capture('picker.png');home();capture('after.png')
 settled=rpc(action='preview',id=initial['theme']['id'])
 assert settled['generation']==active.resolve().name
 assert next(r['id'] for r in settled['backgrounds'] if r['selected'])==rows[chosen]['id']
 picker()
 result={'schema':1,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'97785ec7','system':target,'provenance':'physical board; injected verified virtual touchscreen; native grim screenshots','before_generation':initial['generation'],'after_generation':settled['generation'],'background_changed':True,'remembered_selection_matches':True,'elapsed_including_captures_s':round(time.monotonic()-started,2),'limits':['Not real-finger acceptance.','Not a performance benchmark.']}
 (root/'result.json').write_text(json.dumps(result,indent=2))
 urllib.request.urlopen(urllib.request.Request(url+'/result.json',data=json.dumps(result).encode(),method='POST'),timeout=20).read()
 print('K230_TRACE_BACKGROUND_APPLIED',flush=True)
elif phase=='finish':
 result=json.loads((root/'result.json').read_text())
 subprocess.run(['systemctl','restart','theme-helper.service','shell-ui.service'],check=True)
 time.sleep(4)
 assert active.resolve().name==result['after_generation']
 ipc=pathlib.Path('/run/shell/sway-ipc.sock');parked=json.loads((root/'parked-app.json').read_text())
 shell('swaymsg','-s',str(ipc),f"[con_id={parked['id']}] move container to workspace {json.dumps(parked['workspace'])}")
 shell('swaymsg','-s',str(ipc),'workspace '+json.dumps(parked['workspace']))
 picker();capture('reopened.png')
 current=rpc(action='preview',id=json.loads((root/'initial.json').read_text())['theme']['id'])
 assert current['generation']==result['after_generation']
 print('K230_TRACE_RESTART_REMEMBERED_AND_APP_RESTORED',flush=True)
else:raise ValueError(phase)
