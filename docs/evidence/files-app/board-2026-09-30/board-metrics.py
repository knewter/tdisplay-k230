import json,socket,struct,time,subprocess,shlex,datetime,os,signal

def ipc(command='',kind=0):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect('/run/shell/sway-ipc.sock');b=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(b),kind)+b)
  def read(n):
   b=b''
   while len(b)<n:
    x=s.recv(n-len(b));assert x;b+=x
   return b
  h=read(14);return json.loads(read(struct.unpack('=II',h[6:])[0]))
def windows(n):
 r={n['id']:n['app_id']} if n.get('app_id') else {}
 for c in n.get('nodes',[])+n.get('floating_nodes',[]):r.update(windows(c))
 return r
from pathlib import Path
rows=[]
subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','/nix/store/qbi2i7cq00i6z8mshh17bq8vcr7dk3ds-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust','--surface','hide'],check=True,timeout=5)
time.sleep(.3)
for name,desktop in [('dev.tchx84.Portfolio','dev.tchx84.Portfolio.desktop'),('org.gnome.Nautilus','org.gnome.Nautilus.desktop')]:
 ipc('[app_id="'+name+'"] kill')
 deadline=time.monotonic()+8
 while name in windows(ipc(kind=4)).values() and time.monotonic()<deadline:time.sleep(.08)
 assert name not in windows(ipc(kind=4)).values(),'client did not close'
 if name=='org.gnome.Nautilus':
  for d in Path('/proc').iterdir():
   if d.name.isdigit():
    try:
     exe=str((d/'exe').resolve())
     if exe.endswith('/.nautilus-wrapped') or exe.endswith('/nautilus'):os.kill(int(d.name),signal.SIGTERM)
    except (FileNotFoundError,ProcessLookupError):pass
 time.sleep(1)
 entry=Path('/nix/store/81rx1mhm62llrl5zh7qxi8z2bv0q7fxw-k230-handheld-desktop-entries/share/applications/'+desktop).read_text()
 executable=next(shlex.split(line[5:])[0] for line in entry.splitlines() if line.startswith('Exec='))
 assert executable.startswith('/nix/store/') and Path(executable).is_file()
 started=time.monotonic()
 process=subprocess.Popen(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus',executable],stdout=subprocess.DEVNULL,stderr=open('/root/tmp/k230-deployment/files-launch-error.txt','a'))
 deadline=started+25
 while name not in windows(ipc(kind=4)).values() and time.monotonic()<deadline:time.sleep(.04)
 assert name in windows(ipc(kind=4)).values(),('file app failed to map',name,process.poll())
 map_ms=round((time.monotonic()-started)*1000,1);time.sleep(1)
 candidates=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   exe=str((d/'exe').resolve());command=(d/'cmdline').read_bytes().split(bytes([0]));env=(d/'environ').read_bytes().split(bytes([0]))
   if (name=='dev.tchx84.Portfolio' and any(b'/portfolio-filemanager-' in arg or b'/dev.tchx84.Portfolio' in arg or b'/.dev.tchx84.Portfolio-wrapped' in arg for arg in command)) or (name=='org.gnome.Nautilus' and (exe.endswith('/.nautilus-wrapped') or exe.endswith('/nautilus'))):
    status=(d/'status').read_text();rss=next(l for l in status.splitlines() if l.startswith('VmRSS:'))
    checks={key:any(e==key.encode()+b'='+value for e in env) for key,value in [('GDK_BACKEND',b'wayland'),('GSK_RENDERER',b'cairo')]}
    dirs=next((e.split(b'=',1)[1] for e in env if e.startswith(b'XDG_DATA_DIRS=')),b'')
    checks.update({key:fragment in dirs for key,fragment in [('app_share',b'portfolio-' if name=='dev.tchx84.Portfolio' else b'nautilus-'),('adwaita_icons',b'adwaita-icon-theme'),('hicolor_icons',b'hicolor-icon-theme')]})
    candidates.append({'pid':int(d.name),'exe':exe,'rss_kib':int(rss.split()[1]),'wrapper_environment':checks})
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 assert candidates,'No app process RSS for '+name
 assert all(all(p['wrapper_environment'].values()) for p in candidates),'wrapper environment mismatch'
 ipc('[app_id="'+name+'"] focus')
 time.sleep(.5)
 subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','grim','-t','jpeg','-q','85','/run/shell/files-'+('portfolio' if name=='dev.tchx84.Portfolio' else 'nautilus')+'.jpg'],check=True,timeout=8)
 rows.append({'app_id':name,'launch_to_wayland_map_ms':map_ms,'processes':candidates,'limits':['Already warm OS/library caches; first mapped surface is not a first-frame latency measurement.']})
result={'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current_system':str(Path('/run/current-system').resolve()),'evidence_class':'physical-board-desktop-entry-exec-launch-and-proc-read','apps':rows}
Path('/root/tmp/k230-deployment/files-metrics-result.json').write_text(json.dumps(result))
print('FILES_METRICS_RESULT '+json.dumps(result))
