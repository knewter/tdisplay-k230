"""Actual Sway axis and shell-edge dispatch; injected headless evidence only."""
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time
import unittest

from card_shell_test_support import binaries


class VirtualPointer:
    """Small standard wlr-virtual-pointer-v1 wire client (no test IPC hook)."""
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(10)
        self.sock.connect(str(path))
        self.next_id = 3
        self.globals = {}
        self.request(1, 1, struct.pack('=I', 2))  # display.get_registry
        self.sync()
        name, version = self.globals['zwlr_virtual_pointer_manager_v1']
        interface = self.string('zwlr_virtual_pointer_manager_v1')
        self.request(2, 0, struct.pack('=I', name) + interface + struct.pack('=II', min(version, 2), 4))
        self.request(4, 0, struct.pack('=II', 0, 5))
        self.next_id = 6
        self.sync()

    @staticmethod
    def string(value):
        data = value.encode() + b'\0'
        return struct.pack('=I', len(data)) + data + b'\0' * (-len(data) % 4)

    def request(self, obj, opcode, data=b''):
        self.sock.sendall(struct.pack('=II', obj, (len(data) + 8) << 16 | opcode) + data)

    def read(self, n):
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk: raise AssertionError('Wayland disconnected')
            data += chunk
        return data

    def sync(self):
        callback = self.next_id
        self.next_id += 1
        self.request(1, 0, struct.pack('=I', callback))
        while True:
            obj, size_op = struct.unpack('=II', self.read(8))
            opcode, size = size_op & 0xffff, size_op >> 16
            data = self.read(size - 8)
            if obj == 1 and opcode == 0: raise AssertionError(('Wayland error', data))
            if obj == 2 and opcode == 0:
                name, length = struct.unpack('=II', data[:8])
                interface = data[8:8 + length - 1].decode()
                version = struct.unpack('=I', data[8 + (length + 3) // 4 * 4:])[0]
                self.globals[interface] = (name, version)
            if obj == callback: return

    def axis(self, delta=None, orientation=1):
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        self.request(5, 5, struct.pack('=I', 1))  # finger source
        if delta is None:
            self.request(5, 6, struct.pack('=II', stamp, orientation))
        else:
            self.request(5, 3, struct.pack('=IIi', stamp, orientation, round(delta * 256)))
        self.request(5, 4)
        self.sync()

    def close(self):
        self.request(5, 8)
        self.sock.close()


class TrackpadGestures(unittest.TestCase):
    def test_direct_edges_axis_reversal_release_and_watchdog(self):
        sway, client = binaries()
        shell_client = os.environ.get('CARD_SHELL_RUST')
        if not shell_client:
            shell_client = str(Path(__file__).resolve().parents[1] / 'nix/rust-shell-client/target/debug/k230-shell-rust')
        if not Path(shell_client).is_file():
            raise RuntimeError('Build native Rust shell or set CARD_SHELL_RUST')
        with tempfile.TemporaryDirectory(prefix='k230-trackpad-', dir=os.environ.get('TMPDIR')) as directory:
            work = Path(directory)
            conf = work / 'sway.conf'
            conf.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\n'
                'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, border none, '
                'resize set 100 ppt 100 ppt, move position 0 0\n')
            env = dict(os.environ, XDG_RUNTIME_DIR=str(work), WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
                WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TOUCH_FIRST='1',
                SWAY_K230_CARD_REVEAL_STREAM='1', SWAY_K230_CARD_TEST_INPUT='1',
                SWAY_K230_KEYBOARD_GESTURES='1', SWAY_K230_KEYBOARD_HEIGHT='420')
            data = work / 'data'
            applications = data / 'applications'; applications.mkdir(parents=True)
            launch = work / 'launch-marker'; launch.write_text('#!/bin/sh\ntouch "'+str(work/'unexpected-launch')+'"\n'); launch.chmod(0o700)
            for index in range(48):
                (applications / f'fixture-{index:02}.desktop').write_text(
                    f'[Desktop Entry]\nType=Application\nName=Fixture {index:02}\nExec={launch}\nIcon=utilities-terminal\n')
            env.update(XDG_DATA_HOME=str(data), XDG_DATA_DIRS=str(data), XDG_CONFIG_HOME=str(work/'config'))
            helper = work / 'keyboard-signal'
            helper.write_text("#!/bin/sh\ncase \"$1\" in show) signal=USR2;; hide) signal=USR1;; *) exit 2;; esac\nprintf '%s\\n' \"$1\" >> \"$XDG_RUNTIME_DIR/keyboard-actions\"\nkill -\"$signal\" \"$(cat \"$XDG_RUNTIME_DIR/keyboard.pid\")\"\n")
            helper.chmod(0o700)
            env['SWAY_K230_KEYBOARD_SIGNAL'] = str(helper)
            keyboard = os.environ.get('CARD_SHELL_KEYBOARD')
            if not keyboard or not Path(keyboard).is_file(): raise RuntimeError('Set CARD_SHELL_KEYBOARD to the matching real wvkbd executable')
            log = (work / 'sway.log').open('w')
            procs = [subprocess.Popen(['/usr/bin/qemu-riscv64-static', sway, '-c', str(conf), '-d'],
                env=env, stdout=log, stderr=log)]
            pad = None
            persistent_ipc = None
            try:
                def wait(predicate, seconds=30):
                    until = time.monotonic() + seconds
                    while time.monotonic() < until:
                        value = predicate()
                        if value: return value
                        time.sleep(.03)
                    raise AssertionError('timeout: ' + (work / 'sway.log').read_text()[-3000:])
                ipc_path = wait(lambda: next(iter(work.glob('sway-ipc.*.sock')), None), 60)
                display = wait(lambda: next((p for p in work.glob('wayland-*') if not p.name.endswith('.lock')), None))
                env['WAYLAND_DISPLAY'] = display.name
                env['SWAYSOCK'] = str(ipc_path)

                def ipc(text='', kind=0, check=True):
                    nonlocal persistent_ipc
                    if persistent_ipc is None:
                        persistent_ipc = socket.socket(socket.AF_UNIX)
                        persistent_ipc.settimeout(10); persistent_ipc.connect(str(ipc_path))
                    sock = persistent_ipc
                    data = text.encode(); sock.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)
                    def read(n):
                        data = b''
                        while len(data) < n:
                            chunk = sock.recv(n-len(data))
                            if not chunk: raise AssertionError('IPC disconnected')
                            data += chunk
                        return data
                    header = read(14); result = json.loads(read(struct.unpack('=II', header[6:])[0]))
                    if kind == 0 and check: self.assertTrue(all(r['success'] for r in result), (text, result))
                    return result
                ipc('card_shell test-touch init')
                def scene(): return ipc('card_shell debug-scene')[0]['error']
                def number(field): return float(re.search(r'\b' + field + r'=(-?[\d.]+)', scene())[1])
                def nodes(node):
                    yield node
                    for child in node.get('nodes', []) + node.get('floating_nodes', []): yield from nodes(child)
                def apps(): return {n['app_id'] for n in nodes(ipc(kind=4)) if n.get('app_id')}
                for name in ('k230.card.one', 'k230.card.two', 'k230.card.three'):
                    procs.append(subprocess.Popen([client, '--app-id', name], env=env, stdout=log, stderr=log))
                wait(lambda: len(apps()) == 3)
                procs.append(subprocess.Popen([shell_client, '--serve'], env=env, stdout=log, stderr=log))
                wait(lambda: (work / 'k230-shell-rust.sock').exists())
                keyboard_process = subprocess.Popen(['/usr/bin/qemu-riscv64-static', keyboard, '-H', '420', '--hidden'], env=env, stdout=log, stderr=log)
                procs.append(keyboard_process)
                (work/'keyboard.pid').write_text(str(keyboard_process.pid))
                time.sleep(.3)
                pad = VirtualPointer(display)
                original = apps()
                ipc('[app_id="k230.card.one"] focus')
                pad.axis(20, orientation=0); pad.axis(orientation=0)
                self.assertEqual(number('axis_owned'), 0)
                self.assertIn('mode=0 ', scene())
                sequence = 500
                def begin(edge='bottom', outward=0, valid=True, fingers=2, x=.5, y=None, dx=0, dy=None):
                    nonlocal sequence
                    sequence += 1
                    if y is None: y = .5 if outward and edge=='bottom' else .98 if edge=='bottom' else .04
                    if dy is None: dy = (.02 if edge=='top' else -.02) * (-1 if outward else 1)
                    result = ipc(f'card_shell trackpad begin {sequence} {fingers} {x} {y} {dx} {dy} {int(time.monotonic()*1000)&0xffffffff}', check=valid)
                    if not valid: self.assertFalse(result[0]['success'])
                    # Match the raw board fixture's frame cadence. Native
                    # surface configure/unmap is asynchronous; a whole
                    # gesture at one timestamp does not model real input.
                    time.sleep(.025)
                def move(dx, dy):
                    ipc(f'card_shell trackpad move {sequence} {dx} {dy} {int(time.monotonic()*1000)&0xffffffff}')
                    time.sleep(.025)
                def end(cancel=False):
                    ipc(f'card_shell trackpad {"cancel" if cancel else "end"} {sequence} {int(time.monotonic()*1000)&0xffffffff}')
                    time.sleep(.025)
                # App -> overview: no cursor positioning or application input.
                begin(); move(0, -.12); self.assertEqual(number('trackpad_owned'), 1)
                move(0, -.04); move(0, -.30); end()
                wait(lambda: 'mode=1 ' in scene())
                # Raw centroid translation reuses native card touch drag,
                # including hold/reversal/release without cursor placement.
                begin(y=.5, dx=.02, dy=0); move(.12, 0)
                self.assertEqual(number('trackpad_client'), 0)
                held = number('card_dx'); time.sleep(.15)
                self.assertAlmostEqual(number('card_dx'), held, places=2)
                move(-.04, 0); time.sleep(.1); end()
                wait(lambda: 'mode=1 ' in scene())
                time.sleep(.4)
                # A tiny/reversed pan is never a card-activation tap.
                begin(y=.5, dx=.02, dy=0); move(.01, 0); move(0, 0); end()
                wait(lambda: 'mode=1 ' in scene())
                # Actual standard Wayland finger axis is smooth, reversible,
                # stationary under a hold, and coasts after axis_stop.
                pad.axis(30); self.assertEqual(number('axis_owned'), 1)
                first = number('card_dx'); self.assertLess(first, 0)
                pad.axis(-10); self.assertGreater(number('card_dx'), first)
                held = number('card_dx'); time.sleep(.18)
                self.assertAlmostEqual(number('card_dx'), held, places=2)
                for _ in range(5): pad.axis(38); time.sleep(.015)
                pad.axis(); self.assertEqual(number('axis_owned'), 0)
                wait(lambda: 'mode=1 ' in scene())
                time.sleep(.7)
                self.assertAlmostEqual(number('card_dx'), 0, places=1)
                self.assertEqual(apps(), original)
                # Losing the pointer device cannot strand a card drag.
                pad.axis(12); self.assertEqual(number('axis_owned'), 1)
                pad.close(); pad = None
                wait(lambda: 'axis_owned=0 ' in scene())
                pad = VirtualPointer(display)
                # Overview -> Home -> app drawer.
                begin(); move(0, -.3); end()
                wait(lambda: 'home_selected=1 ' in scene() and 'mode=0 ' in scene())
                begin(); move(0, -.35); end(); wait(lambda: 'drawer_mapped=1 ' in scene())
                # Native shell touch owns content scroll; returning a list
                # to the top within a scroll never promotes it to dismissal.
                time.sleep(.5)
                begin(y=.55, dy=-.02); move(0, -.22); time.sleep(.15); end()
                time.sleep(.25)
                self.assertIn('drawer_mapped=1 ', scene())
                begin(y=.45, dy=.02); move(0, .55); time.sleep(.15); end()
                time.sleep(.3)
                self.assertIn('drawer_mapped=1 ', scene())
                # Lost native-client contact restores the drawer, and the
                # subsequent gesture can acquire a clean Wayland contact.
                begin(y=.5, dy=.02); move(0, .2)
                self.assertEqual(number('trackpad_client'), 1)
                wait(lambda: 'trackpad_owned=0 ' in scene(), 4)
                time.sleep(.3); self.assertIn('drawer_mapped=1 ', scene())
                # No pan returning to its origin can become an app tap.
                begin(y=.5, dy=.02); move(0, .02); move(0, 0); end()
                time.sleep(.3); self.assertFalse((work/'unexpected-launch').exists())
                # Closing is reversible, and cancellation restores the drawer.
                time.sleep(.3); begin('bottom', 1); move(0, .15); move(0, .05); end(True)
                time.sleep(.3); self.assertIn('drawer_mapped=1 ', scene())
                begin('bottom', 1); move(0, .42); end(); wait(lambda: 'drawer_mapped=0 ' in scene())
                # Shade has the same drag-close behavior from the other edge.
                begin('top'); move(0, .25); end(); wait(lambda: 'drawer_mapped=1 ' in scene())
                time.sleep(.3); begin('top', 1); move(0, -.42); end()
                wait(lambda: 'drawer_mapped=0 ' in scene())
                # A center app pan and an unqualified third-contact gesture
                # must fall through, with no fabricated application touch.
                ipc('[app_id="k230.card.one"] focus')
                ipc('card_shell enter')
                wait(lambda: 'mode=1 ' in scene())
                ipc('card_shell activate')
                wait(lambda: 'mode=0 ' in scene())
                begin(y=.5, dy=.1, valid=False)
                begin(fingers=3, y=.5, dy=-.1, valid=False)
                self.assertEqual(number('trackpad_owned'), 0)
                # Two-finger navigation must never show the keyboard.
                self.assertFalse((work/'keyboard-actions').exists())
                # Three fingers map to the real two-contact keyboard policy.
                begin(fingers=3); move(0, -.3)
                wait(lambda: 'keyboard_mapped=1 ' in scene())
                move(0, -.5); end()
                wait(lambda: 'keyboard_progress=1.0000' in scene())
                # Two-finger grip drag uses the very same native one-contact
                # keyboard close behavior, not another shortcut.
                begin(y=(1232-420-56+20)/1232, dy=.02); move(0, .42); end()
                wait(lambda: 'keyboard_mapped=0 ' in scene())
                self.assertIn('show', (work/'keyboard-actions').read_text())
                self.assertIn('hide', (work/'keyboard-actions').read_text())
                # Refuse malformed/stale streams; lost stream never sticks.
                begin(); bad = ipc(f'card_shell trackpad move {sequence} nan 0 1', check=False)
                self.assertFalse(bad[0]['success'])
                wait(lambda: 'trackpad_owned=0 ' in scene() and 'drawer_mapped=0 ' in scene(), 5)
                begin('top'); move(0, .02)
                ipc('output HEADLESS-1 mode 600x1280')
                wait(lambda: 'trackpad_owned=0 ' in scene() and 'drawer_mapped=0 ' in scene(), 5)
                ipc('output HEADLESS-1 mode 568x1232')
                # Geometry cancellation may restore overview; establish Home
                # explicitly before checking that a fresh drawer drag works.
                ipc('card_shell home')
                wait(lambda: 'home_enabled=1 ' in scene() and 'mode=0 ' in scene())
                begin(); move(0, -.3); end(); wait(lambda: 'drawer_mapped=1 ' in scene())
                self.assertEqual(apps(), original)
                print('PASS: actual compositor/native Rust touch scroll and close, card motion, real keyboard chord/grip and recovery; headless injection only')
            finally:
                if persistent_ipc: persistent_ipc.close()
                if pad: pad.close()
                for proc in reversed(procs):
                    if proc.poll() is None: proc.terminate()
                    try: proc.wait(timeout=5)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                log.close()
                if os.environ.get('CARD_GESTURE_LOG'):
                    Path(os.environ['CARD_GESTURE_LOG']).write_bytes((work/'sway.log').read_bytes())
