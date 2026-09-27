#!/usr/bin/env python3
"""Small, non-activating drag/hold workload; injected virtual touch only."""
import argparse,hashlib,importlib.util,json,os,pathlib,re,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--output',required=True);a=p.parse_args();os.umask(0o077)
s=importlib.util.spec_from_file_location('touch','/run/k230-picker-baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.verify_device('/dev/input/event1')
out=pathlib.Path(a.output);assert not out.exists()
active=pathlib.Path('/home/shell/.local/state/omarchy/current/active');before=str(active.resolve(strict=True));epoch=time.time();phases=[]
pid=int(subprocess.check_output(['systemctl','show','shell-ui.service','-p','MainPID','--value'],text=True));exe=os.readlink(f'/proc/{pid}/exe')
for row,y in [('theme',430),('background',990)]:
 for direction,dx in [('left',-20),('right',20)]:
  item={'row':row,'direction':direction,'start_monotonic_s':time.monotonic()};phases.append(item)
  def held():
   item['injection_end_monotonic_s']=time.monotonic();time.sleep(1.5)
  m.native_touch('/dev/input/event1',284,y,284+dx,y,held=held)
  item['release_monotonic_s']=time.monotonic();time.sleep(1.2);item['end_monotonic_s']=time.monotonic()
  assert str(active.resolve(strict=True))==before
raw=subprocess.check_output(['journalctl','--no-pager','-o','json','--since','@'+str(epoch),'-u','shell-ui.service'],text=True)
events=[]
for line in raw.splitlines():
 e=json.loads(line);message=e.get('MESSAGE','');match=re.fullmatch(r'rust-shell (\d+)ms (commit|frame-done|touch-(?:down|move|up)(?: .*?)?)',message)
 if match:events.append({'monotonic_s':int(e['__MONOTONIC_TIMESTAMP'])/1e6,'kind':match[2].split()[0],'rust_ms':int(match[1])})
for phase in phases:
 ev=[e for e in events if phase['start_monotonic_s']<=e['monotonic_s']<=phase['end_monotonic_s']]
 moves=[e['monotonic_s'] for e in ev if e['kind']=='touch-move'];commits=[e['monotonic_s'] for e in ev if e['kind']=='commit']
 phase['touch_moves']=len(moves);phase['commits']=len(commits)
 phase['last_move_processing_after_injection_ms']=round(1000*(max(moves)-phase['injection_end_monotonic_s']),3) if moves else None
 phase['commits_while_finger_held']=sum(t<=phase['release_monotonic_s'] for t in commits)
 phase['commits_after_release']=sum(t>phase['release_monotonic_s'] for t in commits)
assert int(subprocess.check_output(['systemctl','show','shell-ui.service','-p','MainPID','--value'],text=True))==pid
record={'schema':1,'label':a.label,'provenance':'injected verified virtual touchscreen; no real-finger or presentation-FPS claim','rust_exe':exe,'current_system':str(pathlib.Path('/run/current-system').resolve()),'booted_system':str(pathlib.Path('/run/booted-system').resolve()),'generation_sha256':hashlib.sha256(before.encode()).hexdigest(),'generation_unchanged':str(active.resolve(strict=True))==before,'phases':phases,'events':events,'limits':['20-pixel displacements keep both old and new rows below a half-index transition from rest.','Journal receive timestamps approximate userspace event processing, not panel scanout.','Hold period is 1.5 seconds; release follows without a final movement.','No screenshot capture during timing.']}
out.write_text(json.dumps(record,indent=2)+'\n');print('TRACKING_PROBE_OK')
