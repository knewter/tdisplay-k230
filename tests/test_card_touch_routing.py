#!/usr/bin/env python3
"""Actual wl_touch pairing regression for the opt-in headless card adapter.

Compiles the native receiver, runs Sway under QEMU if needed, and emits real
wlr_touch device events via the explicitly guarded test hook. No board access.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, label, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError('timed out: ' + label)


def records(path):
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def build_receiver(directory):
    source = ROOT / 'tests/card_touch_receiver.c'
    protocols = [('/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml', 'xdg-shell'),
                 (ROOT / 'tests/fixtures/wayland/wlr-layer-shell-unstable-v1.xml', 'wlr-layer-shell')]
    generated = []
    for xml, name in protocols:
        subprocess.run(['wayland-scanner', 'client-header', str(xml), str(directory/f'{name}-client-protocol.h')], check=True)
        code = directory/f'{name}-protocol.c'
        subprocess.run(['wayland-scanner', 'private-code', str(xml), str(code)], check=True)
        generated.append(str(code))
    flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'wayland-client'], text=True).split()
    binary = directory/'card-touch-receiver'
    subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-I', str(directory), str(source), *generated, *flags, '-o', str(binary)], check=True)
    return binary


def run(sway, qemu, output):
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o700)
    receiver = build_receiver(output)
    config = output/'sway.conf'
    config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\nfocus_follows_mouse no\n'
                      'for_window [app_id="^k230.touch."] floating enable, border none, resize set 520 1040, move position 24 120\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(output), WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
               WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1', SWAY_K230_CARD_TEST_INPUT='1')
    processes = []
    log = (output/'sway.log').open('w')
    prefix = [qemu] if Path(sway).read_bytes()[18:20] == b'\xf3\x00' else []
    compositor = subprocess.Popen([*prefix, sway, '-c', str(config), '-d'], env=env, stdout=log, stderr=log)
    processes.append(compositor)

    def ipc(command):
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(5)
            connection.connect(str(next(output.glob('sway-ipc.*.sock'))))
            payload = command.encode()
            connection.sendall(b'i3-ipc'+struct.pack('=II', len(payload), 0)+payload)
            def read(n):
                data = b''
                while len(data) < n:
                    chunk = connection.recv(n-len(data))
                    assert chunk, 'IPC closed'
                    data += chunk
                return data
            header = read(14)
            reply = json.loads(read(struct.unpack('=II', header[6:])[0]))
            assert all(row['success'] for row in reply), (command, reply)
            return reply

    def native(command):
        return ipc('card_shell test-touch '+command)

    def start(name, role, app_id='k230.touch.one'):
        path = output/f'{name}.jsonl'
        with path.open('w') as stream:
            process = subprocess.Popen([str(receiver), '--role', role, '--app-id', app_id],
                                       env=env, stdout=stream, stderr=subprocess.PIPE)
        processes.append(process)
        wait_for(lambda: any(r['event'] == 'touch_ready' for r in records(path)), name+' touch binding')
        wait_for(lambda: any(r['event'] == 'ready' for r in records(path)), name+' mapped')
        return process, path

    def delivered(path, touch_id, event):
        return any(row['id'] == touch_id and row['event'] == event for row in records(path))

    def select_card(touch_id):
        before = (output/'sway.log').read_text().count('K230_CARD_SHELL restored focus=')
        native(f'down {touch_id} 284 450')
        native(f'up {touch_id}')
        wait_for(lambda: (output/'sway.log').read_text().count('K230_CARD_SHELL restored focus=') > before,
                 'fresh contact selects card '+str(touch_id))

    def paired(path, touch_id, x, y):
        native(f'down {touch_id} {x} {y}')
        native(f'up {touch_id}')
        wait_for(lambda: delivered(path, touch_id, 'down') and delivered(path, touch_id, 'up'), 'paired touch '+str(touch_id))
        assert records(path)[-1]['active'] == 0

    try:
        wait_for(lambda: list(output.glob('sway-ipc.*.sock')), 'Sway startup', 45)
        env['WAYLAND_DISPLAY'] = next(p.name for p in output.glob('wayland-*') if not p.name.endswith('.lock'))
        native('init')
        one, one_log = start('one', 'app')
        two, two_log = start('two', 'app', 'k230.touch.two')
        bar, bar_log = start('bar', 'bar')
        launcher, launcher_log = start('launcher', 'launcher')
        # Actual layer-shell launcher receives the entire footer and the hidden
        # Cards-button rectangle, including the overlap with the bottom edge.
        paired(launcher_log, 1, 284, 1195)
        paired(launcher_log, 2, 480, 90)
        launcher.terminate(); assert launcher.wait(timeout=5) == 0
        time.sleep(.15)
        # Card owns id10. id11 lands on bar second and lifts first: BOTH are
        # drained, so no unmatched bar touch can survive normal restoration.
        ipc('card_shell enter')
        native('down 10 284 450')
        native('motion 10 250 450')
        native('down 11 20 20')
        native('up 11')
        native('up 10')
        time.sleep(.1)
        assert not delivered(bar_log, 11, 'down'), records(bar_log)
        paired(bar_log, 12, 20, 20)
        # No wl_touch point remains to block entry after that real paired stream.
        ipc('card_shell enter'); ipc('card_shell back')
        paired(two_log, 13, 284, 450)
        # A real exclusive keyboard layer changes the reserved region. Its
        # second contact must also drain; a fresh standalone contact is paired.
        keyboard, keyboard_log = start('keyboard', 'keyboard')
        ipc('card_shell enter')
        native('down 40 284 450')
        native('down 41 284 1100')
        native('up 41'); native('up 40')
        time.sleep(.1)
        assert not delivered(keyboard_log, 41, 'down'), records(keyboard_log)
        paired(keyboard_log, 42, 284, 1100)
        keyboard.terminate(); assert keyboard.wait(timeout=5) == 0
        time.sleep(.15)
        # Real compositor cancel ends the stream without an up; fresh touch works.
        ipc('card_shell enter');native('down 20 284 450');native('cancel')
        select_card(21)
        ipc('card_shell enter');ipc('card_shell back')
        # Physical-device removal while a card owns touch likewise has no up.
        ipc('card_shell enter');native('down 30 284 450');native('remove')
        wait_for(lambda: records(bar_log)[-1]['event'] == 'touch_removed', 'device removal observed')
        native('init')
        wait_for(lambda: records(bar_log)[-1]['event'] == 'touch_ready', 'replacement touch binding')
        select_card(31)
        ipc('card_shell enter');ipc('card_shell back')
        paired(bar_log, 32, 20, 20)
        for path in (one_log, two_log, bar_log):
            rows = records(path)
            assert not any(r['event'].startswith(('invalid_', 'unpaired_')) for r in rows), rows
            assert rows[-1]['active'] == 0, rows
        result = {'evidence_class': 'native-wayland-receiver-headless-injected-device',
                  'passed': ['launcher-footer-pairing', 'hidden-card-button-pairing',
                             'second-contact-bar-drain', 'second-contact-keyboard-drain',
                             'normal-app-touch-pairing',
                             'cancel-without-up', 'device-removal-without-up'],
                  'limits': ['No physical panel or finger evidence.',
                             'Input originates from a test wlr_touch device, not direct card handlers.']}
    finally:
        # Close clients while Sway is still alive; server disconnect must not
        # masquerade as receiver protocol failure or suppress final assertions.
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        log.close()
        assert all(p.returncode == 0 for p in processes), [p.returncode for p in processes]
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sway', required=True)
    parser.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    if arguments.output:
        if arguments.output.exists() and any(arguments.output.iterdir()):
            parser.error('--output must be new or empty')
        run(arguments.sway, arguments.qemu, arguments.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='card-touch-routing-') as directory:
            run(arguments.sway, arguments.qemu, Path(directory))
