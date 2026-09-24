#!/usr/bin/env python3
"""Headless QEMU proof of marked ordinary app geometry with the actual wvkbd."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time


def wait_for(predicate, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError('timed out waiting for compositor state')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('sway', 'client', 'keyboard', 'dialog', 'output'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--qemu', default='/usr/bin/qemu-riscv64-static')
    args = ap.parse_args()
    directory = Path(args.output)
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    config = directory / 'sway.conf'
    config.write_text('''output HEADLESS-1 mode 568x1232
seat seat0 fallback true
focus_follows_mouse no
floating_maximum_size -1 x -1
default_floating_border none
workspace_layout default
for_window [tiling app_id=".*"] card_shell ordinary, floating enable, resize set 100 ppt 100 ppt, move position 0 0
''')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(directory), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman', SWAY_K230_CARD_SHELL='1',
               SWAY_K230_CARD_TOUCH_FIRST='1')
    children = []
    log = (directory / 'sway.log').open('w')
    sway = subprocess.Popen([args.qemu, args.sway, '-c', str(config), '-d'], env=env,
                            stdout=log, stderr=log)

    def launch(name, command):
        stream = (directory / (name + '.log')).open('w')
        process = subprocess.Popen(command, env=env, stdout=stream, stderr=stream)
        children.append((process, stream))
        return process

    def ipc(command='', kind=4):
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(5)
        sock.connect(str(next(directory.glob('sway-ipc.*.sock'))))
        request = command.encode()
        sock.sendall(b'i3-ipc' + struct.pack('=II', len(request), kind) + request)

        def read(length):
            data = b''
            while len(data) < length:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    raise AssertionError('IPC closed')
                data += chunk
            return data

        header = read(14)
        length, _ = struct.unpack('=II', header[6:])
        result = json.loads(read(length))
        sock.close()
        return result

    def tree():
        windows, workspaces = [], []
        pending = [ipc()]
        while pending:
            node = pending.pop()
            pending.extend(node.get('nodes', []) + node.get('floating_nodes', []))
            if node.get('type') == 'workspace' and node.get('name') != '__i3_scratch':
                workspaces.append(node['rect'])
            if node.get('app_id'):
                windows.append({'app_id': node['app_id'], 'rect': node['rect'],
                                'type': node['type']})
        return {'windows': sorted(windows, key=lambda row: row['app_id']),
                'workspaces': workspaces}

    def ordinary(snapshot):
        return {row['app_id']: row['rect'] for row in snapshot['windows']
                if row['app_id'].startswith('k230.card.')}

    try:
        wait_for(lambda: next((item.name for item in directory.glob('wayland-*')
                               if item.is_socket()), None))
        env['WAYLAND_DISPLAY'] = next(item.name for item in directory.glob('wayland-*')
                                      if item.is_socket())
        for name in ('one', 'two'):
            launch(name, [args.client, '--app-id', 'k230.card.' + name])
            wait_for(lambda: len(ordinary(tree())) == len([row for row in children
                                                           if row[0].args[0] == args.client]))
            wait_for(lambda: ordinary(tree()).get('k230.card.' + name, {}).get('height') == 1232)
        before = tree()
        assert all(box == {'x': 0, 'y': 0, 'width': 568, 'height': 1232}
                   for box in ordinary(before).values()), before
        dialog = launch('dialog', [args.dialog, '--info', '--no-wrap',
                                   '--title=Geometry dialog', '--text=Transient geometry check'])
        wait_for(lambda: len(tree()['windows']) >= 3)
        pre_keyboard = tree()
        dialog_rows = [row for row in pre_keyboard['windows']
                       if not row['app_id'].startswith('k230.card.')]
        assert len(dialog_rows) == 1 and dialog_rows[0]['type'] == 'floating_con', pre_keyboard
        dialog_before = dialog_rows[0]['rect']
        keyboard = launch('wvkbd', [args.qemu, args.keyboard, '-H', '420', '--hidden'])
        wait_for(lambda: 'Found 2 layers' in (directory / 'wvkbd.log').read_text())
        assert keyboard.poll() is None
        keyboard.send_signal(signal.SIGUSR2)
        wait_for(lambda: tree()['workspaces'][0]['height'] == 812)
        shown = wait_for(lambda: tree() if all(
            box == {'x': 0, 'y': 0, 'width': 568, 'height': 812}
            for box in ordinary(tree()).values()) else None)
        dialog_shown = [row['rect'] for row in shown['windows']
                        if row['app_id'] == dialog_rows[0]['app_id']]
        assert dialog_shown == [dialog_before], (dialog_before, dialog_shown)
        keyboard.send_signal(signal.SIGUSR1)
        wait_for(lambda: tree()['workspaces'][0]['height'] == 1232)
        hidden = wait_for(lambda: tree() if all(
            box == {'x': 0, 'y': 0, 'width': 568, 'height': 1232}
            for box in ordinary(tree()).values()) else None)
        assert dialog.poll() is None
        (directory / 'result.json').write_text(json.dumps(
            {'class': 'headless-qemu-native-wvkbd', 'before': before, 'shown': shown,
             'hidden': hidden, 'dialog_app_id': dialog_rows[0]['app_id']}, indent=2) + '\n')
        print('PASS two ordinary apps follow actual wvkbd usable area; dialog unchanged; no panel proof')
    finally:
        for process, stream in reversed(children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            stream.close()
        if sway.poll() is None:
            sway.terminate()
        try:
            sway.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sway.kill()
        log.close()


if __name__ == '__main__':
    main()
