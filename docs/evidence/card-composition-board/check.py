#!/usr/bin/env python3
import datetime,json,os,pathlib,socket,struct,subprocess,time
from card_virtual_keyboard import Keyboard
R=pathlib.Path('/run/k230-card-composition/session');O=pathlib.Path('/run/card-board-evidence');O.mkdir(exist_ok=True)
os.environ.update(XDG_RUNTIME_DIR=str(R),SWAYSOCK=str(R/'sway-ipc.sock'),WAYLAND_DISPLAY='wayland-1')
result={'evidence_class':'board-injected','source_revision':'310dbf131e81bcb5f455299a61baf4ad19a1ea53','harness_revision':'260197de09edfed54cc451a46ac815cad229b00c','probe':'/nix/store/wjzw7jw21p8qq4dsbc8b3fky9233pgqq-k230-card-composition-probe','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'checks':{},'limits':['IPC-injected touch, no real-finger proof','Virtual keyboard, not physical OSK','Native captures do not prove optical cadence']}
def record(k,v=True):
 result['checks'][k]=v;(O/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS',k,flush=True)
def wait(f,seconds=20):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   if v:=f():return v
  except (OSError,ValueError,StopIteration):pass
  time.sleep(.15)
 raise AssertionError('condition timed out')
def ipc(cmd,kind=0,check=True):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(10);s.connect(str(R/'sway-ipc.sock'));p=cmd.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(p),kind)+p)
  def read(n):
   data=b''
   while len(data)<n:
    chunk=s.recv(n-len(data));assert chunk;data+=chunk
   return data
  head=read(14);data=json.loads(read(struct.unpack('=II',head[6:])[0]))
 if kind==0 and check:assert all(x['success'] for x in data),(cmd,data)
 return data
def cmd(s):return ipc('k230_card_probe '+s)
def nodes(t):
 yield t
 for c in t.get('nodes',[])+t.get('floating_nodes',[]):yield from nodes(c)
def focused():return next((n.get('app_id') for n in nodes(ipc('',4)) if n.get('focused')),None)
def records(which):
 return [json.loads(s) for s in (R/('client-'+which+'.jsonl')).read_text().splitlines() if s.startswith('{')]
def counters(which):
 a=records(which);return [max((r.get(k,0) for r in a),default=0) for k in ('frames','child_frames','key_presses')]
def logs():
 inv=pathlib.Path('/run/k230-card-composition/invocation').read_text().strip()
 return subprocess.check_output(['journalctl','_SYSTEMD_INVOCATION_ID='+inv,'--no-pager','-o','cat'],text=True)
def shot(name):subprocess.run(['grim',str(O/(name+'.png'))],check=True,timeout=15)
kbd=None
try:
 wait(lambda:(R/'sway-ipc.sock').exists(),60)
 wait(lambda:sum(n.get('app_id') in ('k230.card.one','k230.card.two') for n in nodes(ipc('',4)))==2)
 assert subprocess.run(['systemctl','is-active','--quiet','shell']).returncode!=0
 assert len(subprocess.check_output(['pgrep','-x','sway'],text=True).split())==1
 record('sole_opt_in_compositor')
 result['outputs']= [{k:o.get(k) for k in ('name','active','current_mode','scale','transform')} for o in ipc('',3)]
 assert all(o['scale']==1 for o in result['outputs']);kbd=Keyboard(R/'wayland-1')
 cmd('fail-mirror 2');assert not ipc('k230_card_probe enter',check=False)[0]['success'];record('atomic_allocation_fallback')
 cmd('enter');before=[counters(w) for w in ('one','two')];time.sleep(3);after=[counters(w) for w in ('one','two')]
 assert all(a[i]>b[i] for a,b in zip(after,before) for i in (0,1)),(before,after)
 record('both_parent_and_subsurface_live',{'before':before,'after':after});shot('two-live-cards')
 cmd('down 10 284 200');cmd('down 11 284 700');cmd('up 10');cmd('up 11');wait(lambda:'reason=second-contact' in logs());record('second_contact_cancel')
 cmd('enter');cmd('cancel');wait(lambda:'reason=touch-cancel' in logs());record('touch_cancel')
 cmd('enter');cmd('down 1 284 700')
 for y in range(700,770,5):cmd('motion 1 284 '+str(y));time.sleep(.025)
 shot('card-during-drag');cmd('up 1');record('continuous_injected_motion')
 cmd('down 2 284 700');cmd('up 2');wait(lambda:'selected-expanded card=1' in logs());wait(lambda:focused()=='k230.card.two');kbd.press();wait(lambda:counters('two')[2]>=1);record('adjacent_expand_and_keyboard_focus');shot('expanded-second')
 cmd('enter');cmd('down 3 284 700');cmd('motion 3 284 500');cmd('up 3');wait(lambda:'close-refused card=1' in logs());assert focused()=='k230.card.two';kbd.press();wait(lambda:counters('two')[2]>=2);record('refused_close_recovers_focus')
 cmd('enter');cmd('down 4 284 200');cmd('motion 4 284 40');cmd('up 4');wait(lambda:'app-exit card=0' in logs());wait(lambda:focused()=='k230.card.two');kbd.press();wait(lambda:counters('two')[2]>=3);record('accepted_close_exit_focus_fallback');shot('after-close')
 record('presentation_signal_recorded','output-presented=' in logs());assert result['checks']['presentation_signal_recorded']
 result['status']='PASS'
except Exception as e:
 result['status']='FAIL';result['error']=type(e).__name__+': '+str(e);raise
finally:
 if kbd:kbd.close()
 (O/'result.json').write_text(json.dumps(result,indent=2)+'\n')
