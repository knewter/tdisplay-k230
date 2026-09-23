#!/usr/bin/env python3
"""Injected board checks; native captures require separate coordinator review."""
import datetime,json,os,pathlib,pwd,signal,subprocess,time
OUT=pathlib.Path('/run/overview-edge-check-fixed');OUT.mkdir(exist_ok=True)
BASE='/nix/store/lrir8irpf6q81ffcgqr2r73zxpgvjf32-k230-touch-launcher-riscv64-unknown-linux-gnu-0.1/bin/k230-touch-launcher'
SWAY='/nix/store/0dw6pla4d4qqyndk77mhahijjzv4g81v-sway-1.12/bin/swaymsg'
JQ='/nix/store/fy9xmga7mbqqiqp6gaj79239a98ssy9g-jq-riscv64-unknown-linux-gnu-1.8.2-bin/bin/jq'
FOOT='/nix/store/y5lgjbwdzhp51x1kja5agixhln8qn7j8-foot/bin/foot'
FIX=pathlib.Path('/run/k230-overview-fixtures');U=pwd.getpwnam('shell')
ENV=dict(os.environ,XDG_RUNTIME_DIR='/run/shell',WAYLAND_DISPLAY='wayland-1',SWAYSOCK='/run/shell/sway-ipc.sock',XDG_DATA_DIRS='/run/current-system/sw/share',XDG_CURRENT_DESKTOP='sway',REAL_SWAYMSG=SWAY,K230_JQ=JQ,K230_SWAYMSG=str(FIX/'focus-log-swaymsg'),K230_FOCUS_LOG='/run/shell/fixture-focus.log')
def run(cmd,**kw):return subprocess.run(cmd,check=True,timeout=10,env=ENV,**kw)
def spawn(cmd,extra):
 env=dict(ENV,**extra)
 return subprocess.Popen(['runuser','-u','shell','--','env',*[f'{k}={v}' for k,v in env.items() if k in ENV and k in ('XDG_RUNTIME_DIR','WAYLAND_DISPLAY','SWAYSOCK','XDG_DATA_DIRS','XDG_CURRENT_DESKTOP','REAL_SWAYMSG','K230_JQ','K230_SWAYMSG','K230_FOCUS_LOG')],*[f'{k}={v}' for k,v in extra.items()],*cmd],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
def tap(x,y,x2=None,y2=None):
 cmd=['/run/inject-tap.sh','/dev/input/event1',str(x),str(y)]
 if x2 is not None:cmd += [str(x2),str(y2)]
 run(cmd,stdout=subprocess.DEVNULL);time.sleep(.8)
def capture(name):run(['grim',str(OUT/(name+'.png'))])
def alive(p):assert p.poll() is None,'owned process exited unexpectedly'
def stop(p):
 if p and p.poll() is None:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=5)
def procset():
 out=[]
 for p in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   if p.joinpath('comm').read_text().strip() in ('foot','htop'):
    tail=p.joinpath('stat').read_text().rsplit(') ',1)[1].split();out.append([int(p.name),tail[19]])
  except OSError:pass
 return sorted(out)
def catalog():return run(['runuser','-u','shell','--','env','REAL_SWAYMSG='+SWAY,'K230_JQ='+JQ,'SWAYSOCK='+ENV['SWAYSOCK'],str(FIX/'stale-catalog')],capture_output=True,text=True).stdout
report={'interaction':'injected-uinput','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':BASE,'phases':[],'native_review':'required separately'}
launcher=fixture=None
try:
 assert not subprocess.run(['pgrep','-x','k230-touch-laun'],capture_output=True).stdout,'existing launcher must be closed first'
 run(['runuser','-u','shell','--',str(FIX/'empty-catalog')]);catalog()
 before=procset();run(['pkill','-USR1','-x','wvkbd-mobintl']);time.sleep(.5)
 log=pathlib.Path(ENV['K230_FOCUS_LOG']);log.write_text('');os.chown(log,U.pw_uid,U.pw_gid);log.chmod(0o600)
 launcher=spawn([BASE],{'K230_WINDOW_CATALOG':str(FIX/'empty-catalog')});time.sleep(1);alive(launcher)
 tap(284,460,284,210);alive(launcher);capture('empty-overview')
 tap(280,1165);alive(launcher);capture('empty-back-apps')
 tap(280,1165);assert launcher.wait(timeout=5)==0
 report['phases'].append({'phase':'empty','overview_stayed_open':True,'first_back_stayed_open':True,'second_back_closed':True})
 fixture=spawn([FOOT,'-a','k230-stale-fixture','-T','Fixture'],{});time.sleep(1);alive(fixture)
 rows=catalog();assert len(rows.strip().splitlines())==1 and '\tFixture\t' in rows
 report['fixture_con_id']=int(rows.split('\t',1)[0])
 launcher=spawn([BASE],{'K230_WINDOW_CATALOG':str(FIX/'stale-catalog')});time.sleep(1);alive(launcher)
 tap(284,460,284,210);alive(launcher);capture('stale-before-close')
 stop(fixture);fixture=None;time.sleep(.5);assert not catalog().strip(),'owned fixture remains in tree'
 tap(284,300);alive(launcher);assert not log.read_bytes(),'stale selection sent a focus command';capture('stale-after-close')
 tap(280,1165);alive(launcher);capture('stale-back-apps')
 tap(280,1165);assert launcher.wait(timeout=5)==0
 assert procset()==before,'existing terminal/monitor identities changed'
 report['phases'].append({'phase':'stale','owned_window_removed':True,'selection_kept_overview':True,'focus_command_count':0,'first_back_stayed_open':True,'second_back_closed':True,'existing_processes_unchanged':True})
 report['result']='process-and-input-checks-pass'
except Exception as error:report['result']='fail';report['error']=str(error)
finally:
 stop(launcher);stop(fixture)
 (OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(report['result'])
raise SystemExit(0 if report['result']=='process-and-input-checks-pass' else 1)
