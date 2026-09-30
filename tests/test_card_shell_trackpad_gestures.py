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
                SWAY_K230_CARD_REVEAL_STREAM='1')
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
                pad = VirtualPointer(display)
                original = apps()
                ipc('[app_id="k230.card.one"] focus')
                pad.axis(20, orientation=0); pad.axis(orientation=0)
                self.assertEqual(number('axis_owned'), 0)
                self.assertIn('mode=0 ', scene())
                sequence = 500
                def begin(edge='bottom', outward=0, valid=True):
                    nonlocal sequence
                    sequence += 1
                    result = ipc(f'card_shell trackpad begin {sequence} {edge} {outward}', check=valid)
                    if not valid: self.assertFalse(result[0]['success'])
                def move(dx, dy):
                    ipc(f'card_shell trackpad move {sequence} {dx} {dy} {int(time.monotonic()*1000)&0xffffffff}')
                def end(cancel=False):
                    ipc(f'card_shell trackpad {"cancel" if cancel else "end"} {sequence} {int(time.monotonic()*1000)&0xffffffff}')
                # App -> overview: no cursor positioning or application input.
                begin(); move(0, -.12); self.assertEqual(number('trackpad_owned'), 1)
                move(0, -.04); move(0, -.30); end()
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
                # Closing is reversible, and cancellation restores the drawer.
                time.sleep(.3); begin('bottom', 1); move(0, .15); move(0, .05); end(True)
                time.sleep(.3); self.assertIn('drawer_mapped=1 ', scene())
                begin('bottom', 1); move(0, .3); end(); wait(lambda: 'drawer_mapped=0 ' in scene())
                # Shade has the same drag-close behavior from the other edge.
                begin('top'); move(0, .25); end(); wait(lambda: 'drawer_mapped=1 ' in scene())
                time.sleep(.3); begin('top', 1); move(0, -.2); end()
                wait(lambda: 'drawer_mapped=0 ' in scene())
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
                print('PASS: actual compositor finger-axis, edge navigation, reversible sheets and lost-stream recovery; headless injection only')
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
