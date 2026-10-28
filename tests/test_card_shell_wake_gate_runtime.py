#!/usr/bin/env python3
"""Headless proof that a touch on a powered-off output wakes it and is swallowed.

Runs the real patched Sway (card-shell adapter, wake gate) with the headless
Pixman backend (under QEMU user emulation when Sway is RISC-V), a real native
wl_touch probe client, and the guarded test-touch device. Sequence:

  1. output '*' power off  -> get_outputs reports power false
  2. touch down/motion/up  -> output power is back on, probe saw NO touch event
  3. touch down/up again   -> probe DOES receive the pair (positive control)

Evidence class: headless (host-run, injected wlr_touch events). Not the board.
Usage: test_card_shell_wake_gate_runtime.py --sway UNWRAPPED_SWAY [--output DIR]
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_card_touch_routing import build_receiver, records, wait_for  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sway', required=True)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix='wg-'))
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o700)
    receiver = build_receiver(output)
    config = output/'sway.conf'
    config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\n'
                      'for_window [app_id="^k230.touch."] floating enable, border none, '
                      'resize set 520 1040, move position 24 120\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(output), WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
               WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TEST_INPUT='1')
    log = (output/'sway.log').open('w')
    prefix = [args.qemu] if Path(args.sway).read_bytes()[18:20] == b'\xf3\x00' else []
    processes = [subprocess.Popen([*prefix, args.sway, '-c', str(config), '-d'], env=env, stdout=log, stderr=log)]

    def stamp():
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(10)
            connection.connect(str(next(output.glob('sway-ipc.*.sock'))))
            payload = command.encode()
            connection.sendall(b'i3-ipc'+struct.pack('=II', len(payload), kind)+payload)

            def read(n):
                data = b''
                while len(data) < n:
                    chunk = connection.recv(n-len(data))
                    assert chunk, 'IPC closed'
                    data += chunk
                return data
            header = read(14)
            reply = json.loads(read(struct.unpack('=II', header[6:])[0]))
            if kind == 0:
                assert all(row['success'] for row in reply), (command, reply)
            return reply

    def native(command):
        return ipc('card_shell test-touch '+command)

    def power():
        return [o['power'] for o in ipc('', 3)]

    notes = []

    def step(text):
        line = f'{stamp()} {text}'
        notes.append(line)
        print(line, flush=True)

    try:
        wait_for(lambda: list(output.glob('sway-ipc.*.sock')), 'Sway startup', 60)
        env['WAYLAND_DISPLAY'] = next(p.name for p in output.glob('wayland-*') if not p.name.endswith('.lock'))
        native('init')
        path = output/'probe.jsonl'
        with path.open('w') as stream:
            probe = subprocess.Popen([str(receiver), '--role', 'app'], env=env, stdout=stream,
                                     stderr=subprocess.PIPE)
        processes.append(probe)
        wait_for(lambda: any(r['event'] == 'touch_ready' for r in records(path)), 'probe touch binding')
        wait_for(lambda: any(r['event'] == 'ready' for r in records(path)), 'probe mapped', 30)
        assert power() == [True], power()
        step('probe mapped, output power true')

        ipc("output '*' power off")
        wait_for(lambda: power() == [False], 'output power off')
        step('output * power off; get_outputs power ' + str(power()))
        before = len(records(path))

        native('down 7 284 450')
        wait_for(lambda: power() == [True], 'touch on dark output wakes it', 20)
        step('touch down id 7 injected; get_outputs power ' + str(power()))
        native('motion 7 250 450')
        native('motion 7 220 460')
        native('up 7')
        time.sleep(1.0)
        swallowed = records(path)[before:]
        touch_rows = [r for r in swallowed if r['event'] in ('down', 'motion', 'up', 'cancel')]
        assert power() == [True]
        assert not touch_rows, touch_rows
        step(f'down/motion/motion/up completed; power {power()}; probe touch events during sequence: {len(touch_rows)}')

        before = len(records(path))
        native('down 8 284 450')
        native('up 8')
        wait_for(lambda: {(r['id'], r['event']) for r in records(path)[before:]} >= {(8, 'down'), (8, 'up')},
                 'positive control reaches probe')
        step('positive control: id 8 down and up reached the probe with output on')
        rows = records(path)
        assert not any(r['event'].startswith(('invalid_', 'unpaired_')) for r in rows), rows
        assert not any(r['id'] == 7 for r in rows if r['event'] in ('down', 'motion', 'up')), rows
        result = {'evidence_class': 'headless', 'sway': args.sway, 'steps': notes,
                  'probe_events': [r for r in rows if r['event'] in ('down', 'motion', 'up', 'cancel')],
                  'limits': ['Injected wlr_touch device on the headless backend; no panel, DRM output or finger.',
                             'Output power is wlr_output enabled state of the headless output.']}
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print('PASS wake gate swallows the waking touch sequence; positive control delivered')
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == '__main__':
    main()
