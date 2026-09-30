#!/usr/bin/env python3
"""Bounded injected HDMI-board trial. Requires coordinator board reservation.

Creates a separate raw touchscreen fixture, runs the actual relay against it,
and restores the physical relay in finally. An independent systemd restore
watchdog must be armed by the operator. This is never real-glass evidence.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time


def ipc(command='', check=True, kind=0):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(3)
        sock.connect('/run/shell/sway-ipc.sock')
        data = command.encode()
        sock.sendall(b'i3-ipc' + struct.pack('=II', len(data), kind) + data)
        def read(n):
            value = b''
            while len(value) < n:
                chunk = sock.recv(n-len(value))
                if not chunk: raise RuntimeError('IPC disconnected')
                value += chunk
            return value
        header = read(14)
        reply = json.loads(read(struct.unpack('=II', header[6:])[0]))
        if kind == 0 and check and not all(item['success'] for item in reply): raise RuntimeError((command, reply))
        return reply


def scene():
    return ipc('card_shell debug-scene')[0]['error']


def wait(predicate, seconds=4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = predicate()
        if result: return result
        time.sleep(.04)
    raise RuntimeError('Timed out; last scene: ' + scene())


class Source:
    name = 'K230 Shell Gesture Test Source'
    def __init__(self):
        self.fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
        self.ids = set()
        try:
            for bit in (1, 3): fcntl.ioctl(self.fd, 0x40045564, bit)
            fcntl.ioctl(self.fd, 0x40045565, 0x14a)  # BTN_TOUCH
            fcntl.ioctl(self.fd, 0x4004556e, 1)  # INPUT_PROP_DIRECT
            for code, maximum, resolution in [(0x2f, 9, 0), (0x39, 65535, 0), (0x35, 1023, 20), (0x36, 2399, 20)]:
                fcntl.ioctl(self.fd, 0x40045567, code)
                fcntl.ioctl(self.fd, 0x401c5504, struct.pack('=H2xiiiiii', code, 0, 0, maximum, 0, 0, resolution))
            fcntl.ioctl(self.fd, 0x405c5503, struct.pack('=HHHH80sI', 3, 0x1234, 0x5678, 1, self.name.encode(), 0))
            fcntl.ioctl(self.fd, 0x5501)
            self.path = wait(lambda: next((Path('/dev/input') / p.name for p in Path('/sys/class/input').glob('event*')
                if (p/'device/name').read_text().strip() == self.name), None))
        except BaseException:
            os.close(self.fd)
            raise

    def frame(self, y, x=0, lift=None, fingers=2):
        events = []
        for slot, px in ([(0, 400+x), (1, 600+x)] if fingers == 2 else [(0, 300+x), (1, 500+x), (2, 700+x)]):
            events.append((3, 0x2f, slot))
            if lift is not None and slot in lift:
                if slot in self.ids: events.append((3, 0x39, -1)); self.ids.remove(slot)
            elif lift is None:
                if slot not in self.ids: events.append((3, 0x39, 100+slot)); self.ids.add(slot)
                events.extend([(3, 0x35, px), (3, 0x36, y)])
        events.extend([(1, 0x14a, int(bool(self.ids))), (0, 0, 0)])
        stamp = time.monotonic_ns()
        os.write(self.fd, b''.join(struct.pack('=qqHHi', stamp//1_000_000_000,
            stamp//1000 % 1_000_000, *event) for event in events))
        time.sleep(.025)

    def swipe(self, start, finish, fingers=2):
        self.frame(start, fingers=fingers)
        for i in range(1, 9): self.frame(round(start+(finish-start)*i/8), fingers=fingers)
        # Real finger lifts are normally staggered; ownership must finish once.
        self.frame(finish, lift={fingers-1}, fingers=fingers); self.frame(finish, lift=set(range(fingers-1)), fingers=fingers)

    def close(self):
        fcntl.ioctl(self.fd, 0x5502)
        os.close(self.fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--relay', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--keyboard-height', required=True, type=int)
    args = parser.parse_args()
    if os.geteuid() or os.uname().machine != 'riscv64':
        raise SystemExit('This injected trial runs only as root on the reserved RISC-V board')
    if not args.relay.startswith('/nix/store/') or not Path(args.relay).is_file():
        raise SystemExit('Use the exact built relay store path')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (output/'result.json').unlink(missing_ok=True)
    source = relay = None
    checks = []
    captures = []
    def remember(name, predicate):
        state = wait(predicate)
        checks.append({'name': name, 'scene': state if isinstance(state,str) else scene()})
    def matching(*fields):
        state = scene()
        return state if all(field in state for field in fields) else False
    def interrupted(_sig, _frame): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    def capture(label):
        display = next(p.name for p in Path('/run/shell').glob('wayland-*') if not p.name.endswith('.lock'))
        destination = Path('/run/shell/hdmi-gesture-'+label+'.png')
        subprocess.run(['runuser','-u','shell','--','env','XDG_RUNTIME_DIR=/run/shell',
            'WAYLAND_DISPLAY='+display,'grim','-t','png',str(destination)],check=True,timeout=15)
        image = output/(label+'.png'); image.write_bytes(destination.read_bytes()); destination.unlink()
        captures.append({'file':image.name,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
            'provenance':'native board screencopy after injected raw input'})
    try:
        subprocess.run(['systemctl', 'stop', 'k230-touch-trackpad'], check=True, timeout=5)
        source = Source()
        log = (output/'relay.log').open('w')
        relay = subprocess.Popen([args.relay, '--force-mode=trackpad', '--device='+str(source.path),
            '--shell-socket=/run/shell/sway-ipc.sock', '--log-events'], stdout=log, stderr=log)
        wait(lambda: 'entered trackpad mode' in (output/'relay.log').read_text())
        ipc('card_shell cancel', check=False)
        # Start from an actual app even if the previous trial left Home up.
        ipc('card_shell home')
        wait(lambda: matching('mode=0 ', 'drawer_mapped=0 '))
        ipc('card_shell enter')
        wait(lambda: matching('mode=1 '))
        ipc('card_shell activate')
        wait(lambda: matching('mode=0 ', 'home_selected=0 '))
        source.swipe(2360, 1600)
        remember('raw bottom edge opens overview', lambda: matching('mode=1 '))
        # Standard libinput horizontal finger scroll, not a compositor test hook.
        source.frame(1200)
        for x in range(0, 161, 20): source.frame(1200, x)
        remember('center contacts become native card touch drag', lambda: matching('trackpad_owned=1 ', 'mode=2 '))
        held = scene(); time.sleep(.25)
        position = lambda state: float(re.search(r'card_dx=(-?[\d.]+)', state)[1])
        assert abs(position(held)) > .1, 'Card axis did not move'
        assert abs(position(scene()) - position(held)) < .5, 'Held cards drifted'
        checks.append({'name':'held card axis', 'scene':scene(), 'previous':held})
        source.frame(1200, 160, lift={1}); source.frame(1200, 160, lift={0})
        remember('native card lift releases ownership', lambda: matching('trackpad_owned=0 '))
        # Native screenshot of injected board pixels; review before publication.
        capture('overview')
        source.swipe(2360, 1600)
        remember('overview to Home', lambda: matching('home_selected=1 ', 'mode=0 '))
        time.sleep(.3)
        capture('home')
        source.swipe(2360, 1500)
        remember('Home to app drawer', lambda: matching('drawer_mapped=1 '))
        time.sleep(.5)
        capture('drawer')
        source.swipe(1200, 2350)
        remember('native drawer content swipe closes drawer', lambda: matching('drawer_mapped=0 '))
        source.swipe(30, 720)
        remember('top inward swipe opens shade', lambda: matching('drawer_mapped=1 '))
        time.sleep(1.2)
        # Shade can contain private network information; inspect this capture
        # locally and omit it from public evidence if it does.
        capture('shade')
        source.swipe(1200, 20)
        remember('native shade content swipe closes shade', lambda: matching('drawer_mapped=0 '))
        # These are board IPC injections, distinct from the raw relay checks.
        def nodes(tree):
            yield tree
            for node in tree.get('nodes', []) + tree.get('floating_nodes', []): yield from nodes(node)
        ipc('card_shell enter')
        selected = re.search(r'selected_app_id=(\S+)', scene())[1]
        ipc('card_shell activate')
        remember('board IPC activation restores selected app', lambda: matching('mode=0 ', 'home_selected=0 '))
        focused = next((n.get('app_id') for n in nodes(ipc(kind=4)) if n.get('focused')), None)
        assert focused == selected, 'Activation focused a different app'
        checks[-1]['input_class'] = 'board-compositor-IPC'
        source.swipe(2360, 800, fingers=3)
        remember('raw three-finger keyboard chord shows native keyboard',
            lambda: matching('keyboard_mapped=1 ', 'keyboard_progress=1.0000'))
        capture('keyboard')
        active = next(o for o in ipc(kind=3) if o.get('active'))
        height = active['rect']['height']
        # Use the matched image configuration plus the existing 56px grip.
        # Coordinates refer to the physical glass, not cursor position.
        grip = round((height-args.keyboard_height-56+20)/height * 2399)
        source.swipe(grip, min(2390, grip+1000))
        remember('raw two-finger grip drag hides native keyboard', lambda: matching('keyboard_mapped=0 '))
        seq = (int(time.monotonic()*1000) << 16) + os.getpid()
        ipc(f'card_shell trackpad begin {seq} 2 0.5 0.02 0 0.02 {int(time.monotonic()*1000)&0xffffffff}')
        bad = ipc(f'card_shell trackpad move {seq} nan 0 {int(time.monotonic()*1000)&0xffffffff}', check=False)
        assert not bad[0]['success'], 'Malformed movement was accepted'
        remember('board IPC lost stream watchdog releases ownership',
            lambda: matching('trackpad_owned=0 ', 'drawer_mapped=0 '))
        checks[-1]['input_class'] = 'board-compositor-IPC'
        source.swipe(30, 720)
        remember('raw edge still opens shade after watchdog recovery', lambda: matching('drawer_mapped=1 '))
        time.sleep(.3); source.swipe(1200, 20)
        remember('raw edge closes recovered shade', lambda: matching('drawer_mapped=0 '))
        ipc('card_shell home')
        transport = (output/'relay.log').read_text()
        assert 'shell IPC phase=' not in transport, 'An IPC rejection/timeout invalidates this trial'
        assert 'accepted=false' not in transport, 'An intended shell edge was refused'
        assert transport.count('accepted=true') == 11, 'A qualified translated shell gesture was lost'
        record = {'evidence_class':'physical-board-injected-raw-uinput-and-native-screencopy',
            'real_glass':False,'system':os.path.realpath('/run/current-system'), 'relay':args.relay,
            'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'checks':checks,'captures':captures}
        (output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps({'passed':len(checks), 'real_glass':False, 'system':record['system']}))
    finally:
        if relay:
            relay.terminate()
            try: relay.wait(timeout=2)
            except subprocess.TimeoutExpired: relay.kill(); relay.wait()
        if source: source.close()
        subprocess.run(['systemctl','start','k230-touch-trackpad'],check=True,timeout=10)


if __name__ == '__main__':
    main()
