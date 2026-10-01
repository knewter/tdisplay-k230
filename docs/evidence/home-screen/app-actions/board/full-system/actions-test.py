import socket,struct,time
from pathlib import Path
WIDTH=568
HEIGHT=1232
class RenameKeyboard:
    """A real `zwp_virtual_keyboard_v1` connection, the same technique
    `tests/card_virtual_keyboard.py::Keyboard` already uses for the Wi-Fi
    password field, extended with a second mapped key (Return, so a rename
    can actually be *committed* -- task 2: "Enter commits") -- kept local to
    this script rather than changing that shared, already-used-elsewhere
    utility's fixed single-key keymap."""

    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.serial = 2
        self.globals = {}
        self.send(1, 1, struct.pack('=I', 2))  # wl_display.get_registry
        self.roundtrip()
        self.bind('zwp_virtual_keyboard_manager_v1', 4)
        self.bind('wl_seat', 5)
        self.send(4, 0, struct.pack('=II', 5, 6))
        self.serial = 6
        # xkb keycode = evdev keycode + 8. <AC01>=38 ('a', evdev 30) and
        # <RTRN>=36 (Return, evdev 28) are the only two keys this probe ever
        # sends -- enough to type a distinguishable rename and commit it.
        keymap = b'''xkb_keymap {
xkb_keycodes "probe" { minimum=8; maximum=255; <AC01>=38; <RTRN>=36; <BKSP>=22; };
xkb_types "probe" { type "ONE_LEVEL" { modifiers=None; map[None]=Level1; level_name[Level1]="Any"; }; };
xkb_compatibility "probe" {};
xkb_symbols "probe" { key <AC01> { type="ONE_LEVEL", [ a ] }; key <RTRN> { type="ONE_LEVEL", [ Return ] }; key <BKSP> { type="ONE_LEVEL", [ BackSpace ] }; };
};\0'''
        fd = os.memfd_create('home-test-keymap', os.MFD_CLOEXEC)
        try:
            os.write(fd, keymap)
            self.send(6, 0, struct.pack('=II', 1, len(keymap)), fd)
        finally:
            os.close(fd)
        self.roundtrip()

    def send(self, obj, opcode, payload=b'', fd=None):
        message = struct.pack('=II', obj, ((len(payload) + 8) << 16) | opcode) + payload
        if fd is None:
            self.socket.sendall(message)
        else:
            sent = self.socket.sendmsg([message], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
            assert sent == len(message)

    def read(self, n):
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            assert chunk, 'Wayland test connection closed'
            data += chunk
        return data

    def roundtrip(self):
        self.serial += 1
        callback = self.serial
        self.send(1, 0, struct.pack('=I', callback))
        while True:
            obj, size_op = struct.unpack('=II', self.read(8))
            size, opcode = size_op >> 16, size_op & 0xffff
            payload = self.read(size - 8)
            assert not (obj == 1 and opcode == 0), ('Wayland protocol error', payload)
            if obj == 2 and opcode == 0:
                name, length = struct.unpack('=II', payload[:8])
                interface = payload[8:8 + length - 1].decode()
                self.globals[interface] = name
            if obj == callback and opcode == 0:
                return

    def bind(self, interface, obj):
        encoded = interface.encode() + b'\0'
        padded = encoded + b'\0' * ((-len(encoded)) % 4)
        self.send(2, 0, struct.pack('=II', self.globals[interface], len(encoded)) + padded + struct.pack('=II', 1, obj))

    def press(self, evdev_keycode=30):
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        self.send(6, 1, struct.pack('=III', stamp, evdev_keycode, 1))
        self.send(6, 1, struct.pack('=III', stamp, evdev_keycode, 0))
        self.roundtrip()

    def press_a(self):
        self.press(30)

    def press_enter(self):
        self.press(28)

    def close(self):
        self.socket.close()

class VirtualPointer(RenameKeyboard):
    """Advertise a real pointer seat capability and inject wl_pointer events.

    Sway cursor IPC alone can exercise compositor chrome, but it does not
    create the pointer device capability the Rust layer-shell client needs.
    """
    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.serial = 2
        self.globals = {}
        self.send(1, 1, struct.pack('=I', 2))
        self.roundtrip()
        self.bind('zwlr_virtual_pointer_manager_v1', 4)
        self.bind('wl_seat', 5)
        self.send(4, 0, struct.pack('=II', 5, 6))
        self.serial = 6
        self.roundtrip()

    def click(self, point, button=1):
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        self.send(6, 1, struct.pack('=IIIII', stamp, int(point[0]), int(point[1]), WIDTH, HEIGHT))
        self.send(6, 4)
        self.roundtrip()
        # Roundtrip acknowledges Sway, not the emulated Rust client's loop.
        # Give pointer entry and each human click phase distinct dispatch turns.
        time.sleep(0.1)
        code = 0x111 if button == 3 else 0x110
        self.send(6, 2, struct.pack('=III', stamp, code, 1))
        self.send(6, 4)
        self.roundtrip()
        time.sleep(0.1)
        self.send(6, 2, struct.pack('=III', (stamp + 200) & 0xffffffff, code, 0))
        self.send(6, 4)
        self.roundtrip()

from pathlib import Path
import subprocess,time,json,re,ast
RUST='/nix/store/zjlcmhxqkhchysmjj9sk53hks1h5wc3l-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust'
PYTHON='/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'
env=['runuser','-u','shell','--','env','HOME=/home/shell','XDG_RUNTIME_DIR=/run/shell','WAYLAND_DISPLAY=wayland-1','SWAYSOCK=/run/shell/sway-ipc.sock','PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin']
def call(args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=20).stdout
def tree():return json.loads(call(env+['swaymsg','-t','get_tree']))
def nodes(node):
 yield node
 for k in ['nodes','floating_nodes']:
  for child in node.get(k,[]):yield from nodes(child)
def foot():return {n['id']:n for n in nodes(tree()) if n.get('app_id') and n.get('type') in ('con','floating_con')}
def home():
 call(env+[RUST,'--surface','hide']);call(env+['swaymsg','card_shell home']);time.sleep(1)
def pointer(x,y,button=1):
 persistent.click((x,y),button);time.sleep(1)
persistent=VirtualPointer(Path('/run/shell/wayland-1'))
original_ids=set(foot());before_ids=set(original_ids);checks={};created=set()
try:
 if not before_ids:
  home();pointer(82,1140)
  deadline=time.monotonic()+10
  while not foot() and time.monotonic()<deadline:time.sleep(.25)
  before_ids=set(foot())
  checks['primary_launches_when_no_window_exists']=len(before_ids)==1
 assert before_ids,'Dock icon did not launch an app'
 home();pointer(82,1140)
 selected=next((wid for wid,n in foot().items() if n.get('focused')),None)
 checks['primary_focuses_existing_window']=selected in before_ids
 checks['primary_does_not_launch_duplicate']=set(foot())==before_ids
 home();journal=call(['journalctl','-u','shell-ui','-n','100','--no-pager','-o','cat']);old_count=journal.count('app-menu-ready')
 pointer(82,1140,3)
 journal=call(['journalctl','-u','shell-ui','-n','100','--no-pager','-o','cat'])
 ready=re.findall(r'app-menu-ready rows=(\d+) new-window=(true|false)',journal)
 assert ready and ready[-1][1]=='true','New Window not supported on selected icon'
 rows=int(ready[-1][0]);y=(1232-min(90+rows*56,1168))/2+78+56*1.5
 pointer(284,y)
 deadline=time.monotonic()+10
 while time.monotonic()<deadline:
  created=set(foot())-before_ids
  if created:break
  time.sleep(.25)
 checks['explicit_new_window_creates_distinct_window']=len(created)==1
 checks['existing_windows_retained']=before_ids<=set(foot())
 assert len(created)==1,'Expected one distinct new app window'
 new=next(iter(created));home();pointer(82,1140)
 checks['primary_returns_to_most_recent_window']=foot().get(new,{}).get('focused',False)
 checks['repeat_primary_does_not_create_third_window']=set(foot())==before_ids|created
finally:
 for wid in set(foot())-original_ids:
  call(env+['swaymsg',f'[con_id={wid}] kill'])
 home();persistent.close()
report={'class':'physical-board-injected-virtual-pointer','source':'288535289172c8465c4fa408eaa8ba2c7ab8a5ac','checks':checks,'existing_window_count':len(before_ids),'probe_windows_cleaned_up':set(foot())==original_ids,'result':'PASS' if checks and all(checks.values()) else 'FAIL','scope':'Actual full-system board compositor and Rust app activation; not physical mouse acceptance'}
print('K230_FULL_SYSTEM_ACTIONS '+json.dumps(report),flush=True)
