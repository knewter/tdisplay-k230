"""Bounded sampling trial; keep raw perf data and script private for review."""
import pathlib,sys,os,subprocess,json,time,hashlib,importlib.util,urllib.request
os.umask(0o077)
perf,url=sys.argv[1:];root=pathlib.Path('/run/k230-perf-private');root.mkdir(mode=0o700)
s=importlib.util.spec_from_file_location('touch','/run/k230-picker-baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify_device('/dev/input/event1')
active=pathlib.Path('/home/shell/.local/state/omarchy/current/active');before=str(active.resolve(strict=True))
def identity(unit):
 pid=int(subprocess.check_output(['systemctl','show',unit,'-p','MainPID','--value'],text=True));assert pid>0
 fields=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=pid,start_ticks=int(fields[19]),exe=os.readlink(f'/proc/{pid}/exe'))
identities={u:identity(u) for u in ['shell.service','shell-ui.service','theme-helper.service']}
pids=','.join(str(x['pid']) for x in identities.values());phases=[]
command=[perf,'record','-e','cpu-clock','-F','99','-g','--call-graph','fp','-p',pids,'-o',str(root/'perf.data'),'--','sleep','20']
with (root/'record.private').open('wb') as log:
 sampler=subprocess.Popen(command,stdout=log,stderr=log)
 try:
  time.sleep(1)
  if sampler.poll() is not None:raise RuntimeError('sampler exited before workload')
  subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','k230-shell-rust','--surface','settings'],check=True,timeout=5)
  time.sleep(1);m.native_touch('/dev/input/event1',480,130);time.sleep(3)
  for row,y in [('theme',430),('background',990)]:
   for direction,dx in [('left',-40),('right',40)]:
    item=dict(row=row,direction=direction,start_us=time.monotonic_ns()//1000);phases.append(item)
    m.native_touch('/dev/input/event1',284,y,284+dx,y,held=lambda:time.sleep(.2))
    item['release_us']=time.monotonic_ns()//1000;time.sleep(1);item['end_us']=time.monotonic_ns()//1000
  result=sampler.wait(timeout=25)
 finally:
  if sampler.poll() is None:sampler.terminate();sampler.wait(timeout=5)
assert result==0,'sampling failed'
for u,ident in identities.items():assert identity(u)==ident
assert str(active.resolve(strict=True))==before
with (root/'perf-script.private').open('wb') as output,(root/'script-log.private').open('wb') as err:
 subprocess.run([perf,'script','-i',str(root/'perf.data')],stdout=output,stderr=err,check=True,timeout=30)
summary=dict(schema=1,provenance='injected verified virtual touch, CPU sampling only',perf=perf,perf_version=subprocess.check_output([perf,'--version'],text=True).strip(),command=command,current_system=str(pathlib.Path('/run/current-system').resolve()),identities=identities,phases=phases,generation_sha256=hashlib.sha256(before.encode()).hexdigest(),generation_unchanged=True,record_log=(root/'record.private').read_text(),script_log=(root/'script-log.private').read_text(),limits=['One CPU sampling trial, not an observer-overhead comparison.','Production binaries may lack complete symbols/frame pointers; inspect stack quality.'])
(root/'perf-summary.json').write_text(json.dumps(summary))
for name in ['perf.data','perf-script.private','perf-summary.json']:
 urllib.request.urlopen(urllib.request.Request(url+'/'+name,data=(root/name).read_bytes(),method='POST'),timeout=15).read()
print('K230_PERF_CAPTURE_OK',flush=True)
