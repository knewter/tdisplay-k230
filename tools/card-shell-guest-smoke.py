#!/usr/bin/env python3
"""Run inside the booted RISC-V guest against its non-root card shell service."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time


def wait_for(predicate, label, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.05)
    raise RuntimeError('timeout: '+label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', required=True)
    parser.add_argument('--keyboard-helper', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if os.getuid() == 0:
        raise RuntimeError('guest clients must be unprivileged')
    runtime = Path('/run/card-shell-smoke')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY='wayland-1')
    processes = []
    keyboard = None
    compositor_pid = None
    def ipc(command='', kind=0):
        nonlocal compositor_pid
        with socket.socket(socket.AF_UNIX) as sock:
            sock.settimeout(10)
            sock.connect(str(runtime/'sway-ipc.sock'))
            compositor_pid, uid, _ = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            assert uid == os.getuid(), 'compositor and fixtures must share unprivileged UID'
            payload = command.encode()
            sock.sendall(b'i3-ipc'+struct.pack('=II', len(payload), kind)+payload)
            def read(size):
                out = b''
                while len(out) < size:
                    part = sock.recv(size-len(out))
                    if not part:
                        raise RuntimeError('Sway IPC disconnected')
                    out += part
                return out
            header = read(14)
            result = json.loads(read(struct.unpack('=II', header[6:])[0]))
            if kind == 0 and not all(row['success'] for row in result):
                raise RuntimeError('card-capable Sway rejected '+command)
            return result
    def command(value):
        return ipc('card_shell '+value)
    def nodes(tree):
        yield tree
        for node in tree.get('nodes', [])+tree.get('floating_nodes', []):
            yield from nodes(node)
    def apps():
        return [n for n in nodes(ipc(kind=4)) if n.get('app_id') in ('k230.card.one', 'k230.card.two')]
    def focused():
        return next((n['app_id'] for n in apps() if n.get('focused')), None)
    def records(name):
        return [json.loads(line) for line in (runtime/(name+'.jsonl')).read_text().splitlines() if line.startswith('{')]
    def count(name, field):
        return max((row.get(field, 0) for row in records(name)), default=0)
    def start(name, refuse=False):
        with (runtime/(name+'.jsonl')).open('w') as stream:
            child = subprocess.Popen([args.client, '--app-id', name, '--duration', '300']+
                                     (['--refuse-close'] if refuse else []), env=env, stdout=stream, stderr=stream)
        processes.append(child)
        return child
    try:
        wait_for(lambda: (runtime/'sway-ipc.sock').exists(), 'guest compositor startup')
        command('test-touch init')  # unknown/unsupported compositor must fail
        one = start('k230.card.one', True)
        wait_for(lambda: len(apps()) == 1, 'first mapped guest client')
        two = start('k230.card.two')
        wait_for(lambda: len(apps()) == 2, 'two mapped guest clients')
        spec = importlib.util.spec_from_file_location('virtual_keyboard', args.keyboard_helper)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        keyboard = module.Keyboard(runtime/'wayland-1')
        ipc('[app_id="k230.card.one"] focus')
        command('enter')
        command('test-touch down 1 284 450'); command('test-touch motion 1 114 450')
        before = [[count(name, field) for field in ('frames', 'child_frames')]
                  for name in ('k230.card.one', 'k230.card.two')]
        wait_for(lambda: all(count(name, field) > before[i][j]
                            for i, name in enumerate(('k230.card.one', 'k230.card.two'))
                            for j, field in enumerate(('frames', 'child_frames'))), 'live root and subsurface callbacks')
        command('test-touch up 1')
        command('test-touch down 2 284 450'); command('test-touch up 2')
        wait_for(lambda: focused() == 'k230.card.two', 'expand restores app focus')
        keyboard.press(); wait_for(lambda: count('k230.card.two', 'key_presses') == 1, 'keyboard after expand')
        command('enter'); command('previous'); command('close')
        wait_for(lambda: any(r['event'] == 'close_refused' for r in records('k230.card.one')), 'real xdg close refusal')
        wait_for(lambda: 'message=6' in (runtime/'sway.log').read_text(), 'bounded refusal recovery')
        assert one.poll() is None
        command('next'); command('close')
        wait_for(lambda: two.poll() is not None, 'normal graceful close')
        assert two.returncode == 0
        command('back'); wait_for(lambda: focused() == 'k230.card.one', 'back restores surviving app')
        keyboard.press(); wait_for(lambda: count('k230.card.one', 'key_presses') == 1, 'keyboard after refusal/close')
        command('enter'); command('test-touch down 3 284 450'); command('test-touch cancel')
        command('test-touch down 4 284 450'); command('test-touch up 4')
        command('enter'); command('back')
        keyboard.press(); wait_for(lambda: count('k230.card.one', 'key_presses') == 2, 'cancel/back leaves keyboard usable')
        result = {'run_id': args.run_id, 'evidence_class': 'qemu-system-guest-headless-injected',
                  'machine': os.uname().machine, 'uid': os.getuid(),
                  'kernel': os.uname().release, 'system_toplevel': str(Path('/run/current-system').resolve()),
                  'compositor_pid': compositor_pid, 'compositor': os.readlink(f'/proc/{compositor_pid}/exe'),
                  'passed': ['two-live-root-and-subsurface-clients', 'deck-drag-expand',
                             'keyboard-focus-return', 'close-refusal-timeout', 'graceful-close', 'cancel-back-recovery']}
        assert result['machine'] == 'riscv64'
    finally:
        if keyboard:
            keyboard.close()
        for child in processes:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
        assert all(p.returncode == 0 for p in processes), 'guest fixture teardown failed'
    print('K230_CARD_GUEST_RESULT '+json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
