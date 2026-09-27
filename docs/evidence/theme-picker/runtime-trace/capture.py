import pathlib,sys,os,subprocess,json,time,hashlib,importlib.util,uuid,urllib.request
os.umask(0o077)
target,url=sys.argv[1:]
assert str(pathlib.Path('/run/current-system').resolve())==target
root=pathlib.Path('/run/shell/k230-runtime-trace');root.mkdir(mode=0o700)
import pwd
user=pwd.getpwnam('shell');os.chown(root,user.pw_uid,user.pw_gid)
trace_id=uuid.uuid4().hex
active=pathlib.Path('/home/shell/.local/state/omarchy/current/active');before=str(active.resolve(strict=True))
s=importlib.util.spec_from_file_location('touch','/run/k230-picker-baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify_device('/dev/input/event1')
for unit,name in [('theme-helper','helper'),('shell-ui','rust')]:
 directory=pathlib.Path('/run/systemd/system/'+unit+'.service.d');directory.mkdir(exist_ok=True)
 p=directory/'90-k230-runtime-trace.conf';assert not p.exists()
 p.write_text('[Service]\nEnvironment=K230_TRACE_ID='+trace_id+'\nEnvironment=K230_TRACE_SECONDS=40\nEnvironment=K230_TRACE_PATH='+str(root/name)+'.json\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
started=time.monotonic()
subprocess.run(['systemctl','restart','theme-helper.service','shell-ui.service'],check=True)
time.sleep(3)
def identity(unit):
 pid=int(subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True))
 assert pid>0
 raw=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,start_ticks=int(raw[19]),exe=os.readlink(f'/proc/{pid}/exe'))
identities={u:identity(u) for u in ['shell.service','shell-ui.service','theme-helper.service']}
subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','k230-shell-rust','--surface','settings'],check=True)
time.sleep(2);m.native_touch('/dev/input/event1',480,130);time.sleep(5)
phases=[]
for row,y in [('theme',430),('background',990)]:
 for direction,dx in [('left',-40),('right',40)]:
  item=dict(row=row,direction=direction,start_us=time.monotonic_ns()//1000);phases.append(item)
  m.native_touch('/dev/input/event1',284,y,284+dx,y,held=lambda:time.sleep(.5))
  item['release_us']=time.monotonic_ns()//1000
  time.sleep(1.5);item['end_us']=time.monotonic_ns()//1000
assert str(active.resolve(strict=True))==before
for u,ident in identities.items():assert identity(u)==ident
while time.monotonic()-started<45:time.sleep(.2)
workload=dict(schema=1,provenance='injected verified virtual touchscreen; initial instrumentation smoke test',trace_id=trace_id,source_revision='ad752b1d',current_system=target,booted_system=str(pathlib.Path('/run/booted-system').resolve()),identities=identities,phases=phases,generation_sha256=hashlib.sha256(before.encode()).hexdigest(),generation_unchanged=str(active.resolve(strict=True))==before,limits=['Single run, no observer overhead comparison or physical finger acceptance.','Only instrumented Rust overlay and helper spans; no compositor internal or CPU-stack sampling.'])
(root/'workload.json').write_text(json.dumps(workload))
for name in ['rust.json','helper.json','workload.json']:
 data=(root/name).read_bytes();json.loads(data)
 urllib.request.urlopen(urllib.request.Request(url+'/'+name,data=data,method='POST'),timeout=15).read()
print('K230_TRACE_CAPTURE_OK',flush=True)
