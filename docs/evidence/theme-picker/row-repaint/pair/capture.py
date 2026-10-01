from pathlib import Path
import os,sys,subprocess,time,json,importlib.util,uuid,urllib.request,pwd,hashlib,re
os.umask(0o077)
root=Path(__file__).parent;label,url,exe=sys.argv[1:];assert label in ['base','candidate']
u=pwd.getpwnam('shell');troot=Path('/run/shell/theme-row-trial')/(label+'-'+uuid.uuid4().hex);troot.parent.mkdir(mode=0o700,exist_ok=True);os.chown(troot.parent,u.pw_uid,u.pw_gid);troot.mkdir(mode=0o700,exist_ok=False);os.chown(troot,u.pw_uid,u.pw_gid)
trace_id=uuid.uuid4().hex;owned=[];cleanup=root/('restore-'+label+'.sh');timer='k230-theme-row-restore-'+label
cleanup.write_text('#!/bin/sh\nrm -f /run/systemd/system/shell-ui.service.d/92-theme-row-trial.conf /run/systemd/system/theme-helper.service.d/92-theme-row-trial.conf\nsystemctl daemon-reload\nsystemctl restart theme-helper shell-ui\n');cleanup.chmod(0o700)
def call(a):return subprocess.run(a,check=True,capture_output=True,text=True,timeout=30).stdout
def identity(unit):
 pid=int(call(['systemctl','show',unit,'-p','MainPID','--value']));stat=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'start_ticks':int(stat[19]),'exe':os.readlink('/proc/'+str(pid)+'/exe')}
spec=importlib.util.spec_from_file_location('touch',root/'baseline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Descriptor name plus virtual sysfs parent are checked before every injected contact.
subprocess.run(['systemctl','stop','k230-theme-profile-input.service','k230-theme-row-input-'+label+'.service'],check=False,capture_output=True);time.sleep(.5)
call(['systemd-run','--unit=k230-theme-row-input-'+label,'--collect','--property=Type=exec','--property=RuntimeMaxSec=900s','evemu-device','/root/tmp/k230-theme-jank/touch.desc'])
for _ in range(100):
 devices=[p.parent.parent.name for p in Path('/sys/class/input').glob('event*/device/name') if p.read_text().strip()=='K230 injected touchscreen' and str(p.resolve()).startswith('/sys/devices/virtual/input/')]
 if len(devices)==1:break
 time.sleep(.1)
else:raise RuntimeError('virtual touch unavailable')
device='/dev/input/'+devices[0];m.verify_device(device)
active=Path('/home/shell/.local/state/omarchy/current/active');before=str(active.resolve(strict=True));deadline=time.monotonic()+100
report={'label':label,'clock':'CLOCK_MONOTONIC','generation_sha256':hashlib.sha256(before.encode()).hexdigest(),'active_background_count':len(json.loads((Path(before)/'report.json').read_text())['backgrounds']),'phases':[],'input_samples_per_swipe':20,'requested_swipe_ms':200,'requested_swipe_pixels':240,'current_system':str(Path('/run/current-system').resolve()),'started_at_epoch_s':time.time()}
# Preserve the exact installed wrapper environment, replacing only its final ELF.
normal=call(['systemctl','show','shell-ui','-p','ExecStart','--value'])
match=re.search(r'path=(/nix/store/[^ ;]+/bin/k230-shell-rust)',normal);assert match
original=Path(match[1]).read_text();assert re.fullmatch(r'/nix/store/[a-z0-9]{32}-[^/ \n]+/bin/k230-shell-rust',exe)
wrapper_text,n=re.subn(r'(?m)^    ?exec /nix/store/[^ ]+/bin/k230-shell-rust', 'exec '+exe,original)
if n==0:wrapper_text,n=re.subn(r'(?m)^exec /nix/store/[^ ]+/bin/k230-shell-rust', 'exec '+exe,original)
assert n==1
wrapper=troot/'shell-wrapper';wrapper.write_text(wrapper_text);wrapper.chmod(0o555)
report['normal_wrapper_sha256']=hashlib.sha256(original.encode()).hexdigest()
report['trial_wrapper_sha256']=hashlib.sha256(wrapper_text.encode()).hexdigest()
try:
 for unit,name in [('shell-ui','rust'),('theme-helper','helper')]:
  p=Path('/run/systemd/system/'+unit+'.service.d/92-theme-row-trial.conf');p.parent.mkdir(exist_ok=True);assert not p.exists();owned.append(p)
  text='[Service]\nEnvironment=K230_TRACE_ID='+trace_id+'\nEnvironment=K230_TRACE_SECONDS=60\nEnvironment=K230_TRACE_PATH='+str(troot/name)+'.json\n'
  if unit=='shell-ui':text+='ExecStart=\nExecStart='+str(wrapper)+' --serve\n'
  p.write_text(text)
 call(['systemd-run','--unit='+timer,'--on-active=180s',str(cleanup)])
 call(['systemctl','daemon-reload']);call(['systemctl','restart','theme-helper','shell-ui']);time.sleep(4)
 print('GENERATION_RESTART_UNCHANGED',str(active.resolve(strict=True))==before,flush=True)
 report['identities']={x:identity(x) for x in ['shell','shell-ui','theme-helper']};assert report['identities']['shell-ui']['exe']==exe
 call(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1',exe,'--surface','settings']);time.sleep(2)
 print('GENERATION_SETTINGS_UNCHANGED',str(active.resolve(strict=True))==before,flush=True)
 m.native_touch(device,480,130);time.sleep(12)
 print('GENERATION_PICKER_UNCHANGED',str(active.resolve(strict=True))==before,flush=True)
 for row,y in [('theme',430),('background',990)]:
  for i,(x,x2) in enumerate([(430,190)]*3+[(190,430)]*3):
   assert str(active.resolve(strict=True))==before
   phase={'row':row,'index':i,'start_us':int(time.monotonic()*1e6)}
   m.native_touch(device,x,y,x2,y);phase['release_us']=int(time.monotonic()*1e6);time.sleep(1.2);phase['end_us']=int(time.monotonic()*1e6);report['phases'].append(phase)
 report['generation_unchanged']=str(active.resolve(strict=True))==before
 report['identities_unchanged']=report['identities']=={x:identity(x) for x in report['identities']}
 assert report['generation_unchanged'] and report['identities_unchanged']
 # Finish both independently started bounded traces, not an assumed startup timestamp.
 while not all((troot/(name+'.json')).exists() and (troot/(name+'.json')).stat().st_size for name in ['rust','helper']):
  if time.monotonic()>deadline:raise RuntimeError('bounded trace completion deadline exceeded')
  time.sleep(.2)
 for name in ['rust','helper']:
  data=json.loads((troot/(name+'.json')).read_text());assert data['trace_id']==trace_id and data['dropped']==0
  (root/(label+'-'+name+'.json')).write_text(json.dumps(data)+'\n')
 (root/(label+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 # Native image is outside timed phases and after trace completion.
 target='/run/shell/theme-row-'+label+'.png'
 call(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','grim','-s','0.6',target]);(root/(label+'.png')).write_bytes(Path(target).read_bytes())
finally:
 for p in owned:p.unlink(missing_ok=True)
 call(['systemctl','daemon-reload']);call(['systemctl','restart','theme-helper','shell-ui']);subprocess.run(['systemctl','stop',timer+'.timer','k230-theme-row-input-'+label+'.service'],check=False,capture_output=True)
for suffix in ['.json','-rust.json','-helper.json','.png']:
 name=label+suffix;urllib.request.urlopen(urllib.request.Request(url+'/'+name,data=(root/name).read_bytes(),method='POST'),timeout=25).read()
print('K230_THEME_ROW_TRIAL_OK',label,flush=True)
