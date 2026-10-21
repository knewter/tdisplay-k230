from pathlib import Path
import subprocess,json,hashlib,os,time,socket,struct
stable=Path('/var/lib/k230/background-video-trial-20261021');new='/nix/store/2igpibpw4nn0clbda7p35dp5bhg28n35-nixos-system-nixos-26.11.20260919.20b1ddd';old='/nix/store/p501mchy0dq9lyjnaxwkx5s2pdm4i2yj-nixos-system-nixos-26.11.20260919.20b1ddd'
assert str(Path('/nix/var/nix/profiles/system').resolve())==old
assert not Path('/run/systemd/system/shell-ui.service.d/93-source3-background-motion.conf').exists()
def ipc(c='',kind=0):
 b=c.encode()
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(15);s.connect('/run/shell/sway-ipc.sock');s.sendall(b'i3-ipc'+struct.pack('=II',len(b),kind)+b)
  def read(n):
   a=b''
   while len(a)<n:
    q=s.recv(n-len(a));assert q;a+=q
   return a
  n,_=struct.unpack('=II',read(14)[6:]);return json.loads(read(n))
def nodes(n):
 yield n
 for v in n.get('nodes',[])+n.get('floating_nodes',[]):yield from nodes(v)
a=[v for v in nodes(ipc(kind=4)) if v.get('app_id')];assert len(a)==1 and a[0]['app_id']=='k230-terminal'
pid=a[0]['pid'];children=Path('/proc',str(pid),'task',str(pid),'children').read_text().split();assert len(children)==1
shell=children[0];p=Path('/proc',shell);assert p.joinpath('comm').read_text().strip() in ['bash','sh']
for child in p.joinpath('task',shell,'children').read_text().split():
 q=Path('/proc',child);argv=q.joinpath('cmdline').read_bytes().split(b'\0');assert len(argv)>1 and argv[1].endswith(b'/libexec/handheld-theme/foot_color_session.py');assert hashlib.sha256(Path(os.fsdecode(argv[1])).read_bytes()).hexdigest()=='4c4be0deb6eaf565675596afd845735a017999c01348e6252be2509687b1fd42';assert not q.joinpath('task',child,'children').read_text().strip()
# Keep fallback to the exact old system after switching /etc to the new test profile.
restore=stable/'restore-compositor.sh';restore.write_text('#!/bin/sh\nset -eu\nrm -f /run/systemd/system/shell.service.d/93-source3-background-cover.conf\nrm -f /run/systemd/system/shell-ui.service.d/93-source3-background-motion.conf\nsystemctl daemon-reload\n'+old+'/bin/switch-to-configuration test\nsystemctl restart shell.service shell-ui.service theme-helper.service\n');restore.chmod(0o700)
subprocess.run(['systemctl','restart','k230-source3-background-cover-restore2.timer'],check=True)
Path('/run/systemd/system/shell.service.d/93-source3-background-cover.conf').unlink();subprocess.run(['systemctl','daemon-reload'],check=True)
p=subprocess.run([new+'/bin/switch-to-configuration','test'],capture_output=True,text=True,timeout=100);(stable/'system-test-activation.private.log').write_text(p.stdout+p.stderr);assert p.returncode==0
until=time.monotonic()+45
while time.monotonic()<until:
 try:
  if all(subprocess.run(['systemctl','is-active','--quiet',n]).returncode==0 for n in ['shell','shell-ui','theme-helper']):
   if any(v.get('app_id')=='k230-terminal' for v in nodes(ipc(kind=4))):break
 except (OSError,ValueError):pass
 time.sleep(.1)
else:raise RuntimeError('normal services/startup app did not recover')
r={'system':str(Path('/run/current-system').resolve()),'booted_system':str(Path('/run/booted-system').resolve()),'profile':str(Path('/nix/var/nix/profiles/system').resolve()),'original_generation':(Path('/home/shell/.local/state/omarchy/current')/'active').resolve().name,'units':{},'output':[{k:v.get(k) for k in ['name','rect','transform','active']} for v in ipc(kind=3) if v.get('active')],'home':ipc('card_shell home')}
for unit in ['shell','shell-ui']:
 pid=subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True).strip();exe=Path('/proc',pid,'exe').resolve();env=dict(v.split(b'=',1) for v in Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in v);r['units'][unit]={'exe':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'reduced_motion':env.get(b'K230_SETTINGS_REDUCED_MOTION',b'').decode()}
assert r['system']==new and r['profile']==old and r['booted_system']==old and r['original_generation']=='2e583fb7dc1947e9d444c171'
assert r['units']['shell']['sha256']=='4fc7bf3a0c0818c9eb3d286de4579999b3fbbaf9abe0e4317c017bca1dc663ba' and r['units']['shell-ui']['sha256']=='32c8c445eb0e9467114880d0084762aa6649e69b1274ba7f87d24e300bee9148'
assert len(r['output'])==1 and r['output'][0]['transform']=='270' and r['output'][0]['rect']['width']==1232 and r['output'][0]['rect']['height']==568
assert r['units']['shell-ui']['reduced_motion']=='0'
(stable/'system-test-activation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
