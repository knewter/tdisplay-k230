#!/usr/bin/env python3
"""Run the real Omawrite under headless Sway at the panel's size.

Uses a private HOME, synthetic Wayland keyboard/touch and native screenshots.
This is host runtime evidence, never physical-board or finger acceptance.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time
from card_virtual_keyboard import Keyboard


class WriterKeyboard(Keyboard):
    def __init__(self, path):
        super().__init__(path)
        self.codes = {chr(n): n for n in range(32, 127)}
        self.codes.update(Escape=127, Return=128, Tab=129, BackSpace=130)
        symbols = {key: code for key, code in self.codes.items()}
        symbols.update(Escape=0xff1b, Return=0xff0d, Tab=0xff09, BackSpace=0xff08)
        codes = ' '.join(f'<K{code}>={code+8};' for code in self.codes.values())
        keys = ' '.join(f'key <K{code}> {{ type="ONE_LEVEL", [ 0x{symbols[key]:x} ] }};'
                        for key, code in self.codes.items())
        keymap = ('xkb_keymap { xkb_keycodes "writer" { minimum=8; maximum=255; '
                  + codes + ' }; xkb_types "writer" { type "ONE_LEVEL" { '
                  'modifiers=None; map[None]=Level1; }; }; '
                  'xkb_compatibility "writer" {}; xkb_symbols "writer" { '
                  + keys + ' }; };\0').encode()
        fd = os.memfd_create('omawrite-test-keymap', os.MFD_CLOEXEC)
        try:
            os.write(fd, keymap)
            self.send(6, 0, struct.pack('=II', 1, len(keymap)), fd)
        finally:
            os.close(fd)
        self.roundtrip()

    def key(self, key, modifiers=0):
        self.send(6, 2, struct.pack('=IIII', modifiers, 0, 0, 0))
        stamp = int(time.monotonic()*1000) & 0xffffffff
        self.send(6, 1, struct.pack('=III', stamp, self.codes[key], 1))
        self.send(6, 1, struct.pack('=III', stamp, self.codes[key], 0))
        self.send(6, 2, struct.pack('=IIII', 0, 0, 0, 0))
        self.roundtrip()

    def text(self, text):
        for char in text:
            self.key('Return' if char == '\n' else char)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('sway', 'omawrite', 'output'):
        ap.add_argument('--'+name, required=True)
    args = ap.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    home = out/'home'
    home.mkdir()
    current = home/'.local/state/omarchy/current'
    current.mkdir(parents=True)
    for name, color, foreground in [('one', '#112233', '#eeeeee'), ('two', '#eff1f5', '#4c4f69')]:
        generation = current/name
        (generation/'theme').mkdir(parents=True)
        (generation/'theme/colors.toml').write_text(f'background = "{color}"\nforeground = "{foreground}"\naccent = "#1e66f5"\n')
    (current/'active').symlink_to('one')
    scratch = home/'writing.md'
    scratch.write_text('Seed document\n')
    config = out/'sway.conf'
    config.write_text('output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n'
                      'focus_follows_mouse no\n'
                      'for_window [app_id="omawrite"] border none\n')
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(out),
               XDG_CONFIG_HOME=str(home/'.config'), XDG_DATA_HOME=str(home/'.local/share'),
               XDG_STATE_HOME=str(home/'.local/state'), WLR_BACKENDS='headless',
               WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
               SWAY_K230_CARD_SHELL='0', QSG_INFO='1', QT_FORCE_STDERR_LOGGING='1')
    env.pop('WAYLAND_DISPLAY', None)
    env.pop('DISPLAY', None)
    processes = []
    logs = []
    keyboard = None

    def spawn(name, argv):
        log = (out/(name+'.log')).open('w')
        logs.append(log)
        process = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
        processes.append(process)
        return process

    def wait(pred, seconds=60):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            if pred():
                return
            time.sleep(.1)
        raise AssertionError('runtime condition timed out; inspect '+str(out))

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(5)
            peer.connect(str(next(out.glob('sway-ipc.*.sock'))))
            data = command.encode()
            peer.sendall(b'i3-ipc'+struct.pack('=II', len(data), kind)+data)
            def read(n):
                chunks = b''
                while len(chunks) < n:
                    chunk = peer.recv(n-len(chunks))
                    assert chunk, 'IPC closed'
                    chunks += chunk
                return chunks
            header = read(14)
            length, _ = struct.unpack('=II', header[6:])
            result = json.loads(read(length))
            if kind == 0:
                assert all(item['success'] for item in result), result
            return result

    def nodes(tree):
        yield tree
        for child in tree.get('nodes', [])+tree.get('floating_nodes', []):
            yield from nodes(child)

    def app():
        return next((n for n in nodes(ipc('', 4)) if n.get('app_id') == 'omawrite'), None)

    def capture(name):
        subprocess.run(['grim', str(out/(name+'.png'))], env=env, check=True, timeout=20)

    try:
        spawn('sway', [args.sway, '-c', str(config), '-d'])
        wait(lambda: 'Running compositor on wayland display' in (out/'sway.log').read_text())
        env['WAYLAND_DISPLAY'] = next(p.name for p in out.glob('wayland-*') if not p.name.endswith('.lock'))
        program = spawn('omawrite', [args.omawrite, str(scratch)])
        wait(lambda: app() or program.poll() is not None)
        assert program.poll() is None, (out/'omawrite.log').read_text()
        assert app()['rect']['width'] == 568, app()['rect']
        assert app()['rect']['height'] == 1232, app()['rect']
        keyboard = WriterKeyboard(out/env['WAYLAND_DISPLAY'])
        time.sleep(2)
        keyboard.key('a', 4)
        keyboard.text('# Omawrite on the handheld\n\nWriting and saving a scratch document.\n')
        keyboard.key('s', 4)
        wait(lambda: scratch.read_text().startswith('# Omawrite on the handheld'))
        saved = scratch.read_text()
        capture('writing')
        keyboard.key('o', 4)
        time.sleep(2)
        capture('open-dialog')
        keyboard.key('Escape')
        time.sleep(.3)
        keyboard.key('s', 5)
        time.sleep(2)
        capture('save-dialog')
        keyboard.key('Escape')
        time.sleep(.3)
        keyboard.text('Dialog cancellation kept the document.\n')
        keyboard.key('s', 4)
        wait(lambda: 'Dialog cancellation kept the document.' in scratch.read_text())
        saved = scratch.read_text()
        keyboard.key('s', 5)
        time.sleep(.5)
        keyboard.key('a', 4)
        keyboard.text('saved-from-dialog.md')
        keyboard.key('Return')
        second = home/'saved-from-dialog.md'
        wait(lambda: second.exists() and second.read_text() == saved)
        keyboard.key('o', 4)
        time.sleep(.5)
        other = home/'open-target.md'
        other.write_text('A different document.\n')
        keyboard.text('open-target.md')
        keyboard.key('Return')
        wait(lambda: 'open-target.md' in app().get('name', ''))
        keyboard.key('a', 4)
        keyboard.text('Edited the separately opened document.')
        keyboard.key('s', 4)
        wait(lambda: other.read_text() == 'Edited the separately opened document.')
        assert scratch.read_text() == saved and second.read_text() == saved
        keyboard.key('s', 5)
        time.sleep(.5)
        keyboard.key('a', 4)
        keyboard.text('saved-from-dialog.md')
        keyboard.key('Return')
        time.sleep(.5)
        capture('overwrite-confirmation')
        assert second.read_text() == saved, 'overwrite must await confirmation'
        keyboard.key('Escape')
        time.sleep(.3)
        assert second.read_text() == saved, 'cancel must leave existing file alone'
        (current/'next').symlink_to('two')
        (current/'next').replace(current/'active')
        time.sleep(2)
        capture('theme-changed')
        keyboard.key('o', 4)
        time.sleep(.5)
        keyboard.text('writing.md')
        time.sleep(.5)
        capture('theme-dialog')
        keyboard.key('Escape')
        time.sleep(.3)
        from PIL import Image
        before = Image.open(out/'writing.png').convert('RGB').getpixel((8, 120))
        after = Image.open(out/'theme-changed.png').convert('RGB').getpixel((8, 120))
        assert before == (17, 34, 51) and after == (239, 241, 245), (before, after)
        ipc('[app_id="omawrite"] floating enable, resize set 568 812, move position 0 0')
        time.sleep(1)
        capture('keyboard-size')
        assert app()['rect']['height'] == 812
        ipc('[app_id="omawrite"] kill')
        wait(lambda: program.poll() is not None)
        spawn('omawrite-reopened', [args.omawrite, str(scratch)])
        wait(app)
        time.sleep(1)
        keyboard.key('a', 4)
        keyboard.key('s', 4)
        time.sleep(.3)
        assert scratch.read_text() == saved
        capture('reopened')
        assert 'omawrite renderer=software platform=wayland' in (out/'omawrite.log').read_text()
        result = dict(result='PASS', evidence_class='headless-real-app-synthetic-input',
                      sway=args.sway, omawrite=args.omawrite,
                      checks=['568x1232 launch', 'edit/save', 'file chooser save-as/open', 'cancel overwrite preserves existing file', 'dialog cancellation preserves text',
                              'live palette generation switch', '568x812 keyboard-sized window',
                              'saved document reopened', 'software backend'],
                      file_text=saved, physical_board=False, real_finger=False)
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
    finally:
        if keyboard:
            keyboard.close()
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
