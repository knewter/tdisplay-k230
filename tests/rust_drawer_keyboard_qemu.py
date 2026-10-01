#!/usr/bin/env python3
"""Real Rust drawer + wvkbd under QEMU; native touch/key injection, never glass proof."""
import argparse,json,os,re,socket,struct,subprocess,time
from pathlib import Path
from PIL import Image,ImageChops
from rust_wifi_settings_qemu import PasswordKeyboard as TextKeyboard

ap=argparse.ArgumentParser(description=__doc__)
for name in ('sway','rust','keyboard','client','output'):ap.add_argument('--'+name,type=Path,required=True)
ap.add_argument('--qemu',default='/usr/bin/qemu-riscv64-static')
ap.add_argument('--probe-only',action='store_true')
a=ap.parse_args();root=a.output;root.mkdir(mode=0o700,parents=True,exist_ok=False)
config=root/'sway.conf';config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\nfor_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 120\n')
data=root/'data/applications';data.mkdir(parents=True)
for i in range(48):
 (data/f'fixture-{i:02}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=Fixture {i:02}\nExec={a.client} --app-id k230.card.one\nIcon=utilities-terminal\n')
helper=root/'keyboard-signal';helper.write_text('#!/bin/sh\ncase "$1" in show) s=USR2;; hide) s=USR1;; *) exit 2;; esac\nkill -"$s" "$(cat "$XDG_RUNTIME_DIR/keyboard.pid")"\n');helper.chmod(0o700)
swaymsg=root/'swaymsg';swaymsg.write_text(f'#!/bin/sh\nexec {a.qemu} {a.sway.parent / "swaymsg"} "$@"\n');swaymsg.chmod(0o700)
env=dict(os.environ,XDG_RUNTIME_DIR=str(root),XDG_DATA_HOME=str(root/'data'),XDG_DATA_DIRS=str(root/'data'),XDG_CONFIG_HOME=str(root/'config'),K230_SWAYMSG=str(swaymsg),K230_KEYBOARD_SIGNAL=str(helper),K230_KEYBOARD_HEIGHT='420',K230_KEYBOARD_TOUCH_GESTURES='1',WLR_BACKENDS='headless',WLR_HEADLESS_OUTPUTS='1',WLR_RENDERER='pixman',SWAY_K230_CARD_SHELL='1',SWAY_K230_CARD_TOUCH_FIRST='1',SWAY_K230_CARD_TEST_INPUT='1',SWAY_K230_CARD_REVEAL_STREAM='1',SWAY_K230_KEYBOARD_GESTURES='1',SWAY_K230_KEYBOARD_HEIGHT='420',SWAY_K230_KEYBOARD_SIGNAL=str(helper))
processes=[];logs=[];keys=None;contact=100

def spawn(name,cmd):
 log=(root/(name+'.log')).open('w');logs.append(log)
 p=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);processes.append(p);return p

def wait(p,seconds=30):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  value=p()
  if value:return value
  time.sleep(.05)
 raise AssertionError('timeout; inspect '+str(root))

def ipc(command='',kind=0):
 with socket.socket(socket.AF_UNIX) as s:
  s.settimeout(5);s.connect(str(next(root.glob('sway-ipc.*.sock'))));b=command.encode();s.sendall(b'i3-ipc'+struct.pack('=II',len(b),kind)+b)
  def read(n):
   b=b''
   while len(b)<n:
    c=s.recv(n-len(b));assert c;b+=c
   return b
  h=read(14);r=json.loads(read(struct.unpack('=II',h[6:])[0]))
  if kind==0:assert all(x['success'] for x in r),r
  return r

def scene():return ipc('card_shell debug-scene')[0]['error']
def rustlog():return (root/'rust.log').read_text()
def route(name):subprocess.run([a.qemu,str(a.rust),'--surface',name],env=env,check=True,stdout=subprocess.DEVNULL)
def tap(x,y):
 global contact
 contact+=1;ipc(f'card_shell test-touch down {contact} {x} {y}');time.sleep(.09);ipc(f'card_shell test-touch up {contact}');time.sleep(.2)
def shot(name):
 path=root/(name+'.png');subprocess.run(['grim',str(path)],env=env,check=True);return path

def query():
 path=shot('query-probe')
 with Image.open(path) as im:im.crop((43,63,210,95)).save(root/'query-crop.png')
 return subprocess.check_output(['tesseract',str(root/'query-crop.png'),'stdout','--psm','7','-c','tessedit_char_whitelist=0123456789x'],stderr=subprocess.DEVNULL,text=True).strip()
def key_count():
 values=[]
 for line in (root/'launched.log').read_text().splitlines() if (root/'launched.log').exists() else []:
  try:values.append(json.loads(line).get('key_presses',0))
  except ValueError:pass
 return max(values,default=0)
try:
 spawn('sway',[a.qemu,str(a.sway),'-c',str(config),'-d'])
 wait(lambda:next((p for p in root.glob('wayland-*') if not p.name.endswith('.lock')),None),60)
 env['WAYLAND_DISPLAY']=next(p.name for p in root.glob('wayland-*') if not p.name.endswith('.lock'));env['SWAYSOCK']=str(next(root.glob('sway-ipc.*.sock')))
 spawn('rust',[a.qemu,str(a.rust),'--serve']);wait(lambda:'ready-idle' in rustlog())
 keyboard=spawn('wvkbd',[a.qemu,str(a.keyboard),'-H','420','--hidden']);(root/'keyboard.pid').write_text(str(keyboard.pid))
 time.sleep(.3);ipc('card_shell test-touch init');route('drawer');wait(lambda:'drawer_mapped=1 ' in scene());time.sleep(.3)
 unfocused=shot('search-unfocused');tap(284,76)
 wait(lambda:'drawer-keyboard-focus-granted' in rustlog());wait(lambda:'keyboard_mapped=1 ' in scene());time.sleep(.35)
 focused=shot('search-focused')
 if a.probe_only:print('PROBE ONLY: inspect '+str(focused));raise SystemExit(0)
 keys=TextKeyboard(root/env['WAYLAND_DISPLAY']);keys.text('00x');wait(lambda:query()=='00x');shot('search-typed')
 # Compare a real wvkbd correction touch with the independently injected
 # standard Backspace event. Pixel equality avoids OCR confusing 00 with 0/010.
 typed=Image.open(root/'search-typed.png').convert('RGB').crop((24,54,544,102))
 keys.key('BackSpace')
 def changed_query():
  image=Image.open(shot('search-expected-correction')).convert('RGB').crop((24,54,544,102))
  return image if ImageChops.difference(typed,image).getbbox() else None
 expected=wait(changed_query);assert 'drawer_mapped=1 ' in scene()
 keys.key('x');wait(lambda:query()=='00x')
 tap(525,1127)
 def corrected():
  image=Image.open(shot('search-corrected')).convert('RGB').crop((24,54,544,102))
  return not ImageChops.difference(expected,image).getbbox()
 wait(corrected);assert 'drawer_mapped=1 ' in scene()
 keys.key('Return');wait(lambda:'keyboard_mapped=0 ' in scene());assert 'drawer_mapped=1 ' in scene();shot('search-keyboard-dismissed')
 tap(284,76);wait(lambda:'keyboard_mapped=1 ' in scene());time.sleep(.25)
 keys.key('Escape');wait(lambda:'keyboard_mapped=0 ' in scene());assert 'drawer_mapped=1 ' in scene()
 # Filtered launch uses the installed desktop entry and then yields app focus.
 # Capture child stdout through a dedicated launcher, preserving the normal Exec path.
 launch=root/'launch';launch.write_text(f'#!/bin/sh\nexec {a.client} --app-id k230.card.one >"$XDG_RUNTIME_DIR/launched.log" 2>&1\n');launch.chmod(0o700)
 (data/'fixture-00.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=Fixture 00\nExec={launch}\nIcon=utilities-terminal\n')
 # Catalog refresh on reopen, then focus and filter again.
 route('hide');wait(lambda:'drawer_mapped=0 ' in scene());route('drawer');wait(lambda:'drawer_mapped=1 ' in scene());time.sleep(.4)
 focus_count=rustlog().count('drawer-keyboard-focus-granted');tap(284,76);wait(lambda:'keyboard_mapped=1 ' in scene() and rustlog().count('drawer-keyboard-focus-granted')>focus_count);keys.text('00x');wait(lambda:query()=='00x');keys.key('BackSpace');time.sleep(.3)
 tap(80,160);wait(lambda:'k230.card.one' in json.dumps(ipc(kind=4)));wait(lambda:'drawer_mapped=0 ' in scene() and 'keyboard_mapped=0 ' in scene())
 before=key_count();keys.key('a');wait(lambda:key_count()>before);shot('app-focus-restored')
 result={'result':'PASS','evidence_class':'headless-qemu-injected-touch-and-real-wvkbd','sway':str(a.sway),'rust':str(a.rust),'keyboard':str(a.keyboard),'search_backspace_kept_drawer':True,'enter_escape_kept_filter':True,'filtered_launch_and_app_key_focus':True,'full_size_overlay':all(m==('568','1232') for m in re.findall(r'(?<!wallpaper-)(?<!home-)configure (\d+)x(\d+)',rustlog()))}
 (root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:
 if keys:keys.socket.close()
 for p in reversed(processes):
  if p.poll() is None:p.terminate()
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)
 for log in logs:log.close()
