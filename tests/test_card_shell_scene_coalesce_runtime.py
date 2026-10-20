"""Actual Sway/Wayland scene scheduling; headless QEMU, never panel proof.

Build the candidate compositor first. CARD_SHELL_SWAY/CLIENT select exact
binaries; CARD_SCENE_COALESCE_OUTPUT optionally preserves numeric evidence.
"""
from card_shell_test_support import binaries
from pathlib import Path
import json
import os
import re
import socket
import struct
import subprocess
import tempfile
import time
import unittest


class SceneCoalescingRuntime(unittest.TestCase):
    def test_latest_pose_clients_structure_chrome_and_settled_quality(self):
        sway, client = binaries()
        with tempfile.TemporaryDirectory(prefix='card-scene-coalesce-') as tmp:
            root = Path(os.environ.get('CARD_SCENE_COALESCE_OUTPUT', tmp))
            root.mkdir(parents=True, exist_ok=True)
            for rotated, reduced in ((True, False), (True, True), (False, False)):
                with self.subTest(rotated=rotated, reduced=reduced):
                    self.exercise(root, sway, client, rotated, reduced)

    def exercise(self, root, sway, client, rotated, reduced):
        work = root / ('rotated' if rotated else 'normal') / ('reduced' if reduced else 'full')
        work.mkdir(parents=True)
        work.chmod(0o700)
        runtime = tempfile.TemporaryDirectory(prefix='card-scene-socket-')
        socket_dir = Path(runtime.name)
        config = work / 'sway.conf'
        config.write_text(
            'output HEADLESS-1 mode 568x1232 render_bit_depth 6 max_render_time 8' +
            (' transform 270' if rotated else '') + '\n'
            'seat seat0 fallback true\nfocus_follows_mouse no\n'
            'for_window [app_id="^k230"] card_shell ordinary, floating enable, '
            'border none, resize set 100 ppt 100 ppt, move position 0 0\n')
        env = dict(os.environ, XDG_RUNTIME_DIR=str(socket_dir), WLR_BACKENDS='headless',
                   WLR_HEADLESS_OUTPUTS='1', WLR_RENDERER='pixman',
                   WLR_PIXMAN_OUTPUT_TURN='1', SWAY_K230_CARD_SHELL='1',
                   SWAY_K230_CARD_TOUCH_FIRST='1', SWAY_K230_CARD_SCALED_CACHE='1',
                   SWAY_K230_CARD_REDUCED_MOTION='1' if reduced else '0')
        processes, streams = [], []
        results = {'evidence_class': 'headless-qemu-product-ipc; no hardware/timing claim',
                   'sway': sway, 'client': client, 'rotated': rotated, 'reduced': reduced}
        log = (work / 'sway.log').open('w')
        streams.append(log)
        server = subprocess.Popen(['/usr/bin/qemu-riscv64-static', sway, '-c', str(config), '-d'],
                                  env=env, stdout=log, stderr=log)
        processes.append(server)

        def wait(predicate, timeout=30):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                value = predicate()
                if value:
                    return value
                self.assertIsNone(server.poll(), (work / 'sway.log').read_text()[-3000:])
                time.sleep(.03)
            self.fail('runtime condition timed out: ' + (work / 'sway.log').read_text()[-3000:])

        def ipc(command='', kind=0, check=True):
            with socket.socket(socket.AF_UNIX) as sock:
                sock.settimeout(10)
                sock.connect(str(next(socket_dir.glob('sway-ipc.*.sock'))))
                payload = command.encode()
                sock.sendall(b'i3-ipc' + struct.pack('=II', len(payload), kind) + payload)

                def read(n):
                    data = b''
                    while len(data) < n:
                        part = sock.recv(n-len(data))
                        self.assertTrue(part, 'closed compositor IPC')
                        data += part
                    return data
                header = read(14)
                length, _ = struct.unpack('=II', header[6:])
                rows = json.loads(read(length))
                if kind == 0 and check:
                    self.assertTrue(all(row['success'] for row in rows), rows)
                return rows

        def nodes(node):
            yield node
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                yield from nodes(child)

        def apps():
            return {node.get('app_id') for node in nodes(ipc(kind=4)) if node.get('app_id')}

        def fields(row):
            return dict(re.findall(r'\b([a-z_]+)=([^ ]+)', row['error']))

        def scene():
            return fields(ipc('card_shell debug-scene')[0])

        def start(name):
            stream = (work / (name + '.jsonl')).open('w')
            streams.append(stream)
            prefix = ['/usr/bin/qemu-riscv64-static'] if Path(client).read_bytes()[18:20] == b'\xf3\x00' else []
            process = subprocess.Popen(prefix + [client, '--app-id', name], env=env,
                                       stdout=stream, stderr=stream)
            processes.append(process)
            def mapped():
                self.assertIsNone(process.poll(), (work/(name+'.jsonl')).read_text())
                return name in apps()
            wait(mapped)

        def client_frames():
            rows = [json.loads(line) for line in (work/'k230.card.one.jsonl').read_text().splitlines()
                    if line.startswith('{')]
            return max((r.get('frames', 0) for r in rows), default=0), max(
                (r.get('child_frames', 0) for r in rows), default=0)

        try:
            wait(lambda: 'Running compositor on wayland display' in (work/'sway.log').read_text(), 60)
            env['WAYLAND_DISPLAY'] = next(p.name for p in socket_dir.glob('wayland-*')
                                          if not p.name.endswith('.lock'))
            for name in ('k230.card.three', 'k230.card.one', 'k230.card.two'):
                start(name)
            ipc('[app_id="k230.card.one"] focus')
            wait(lambda: any(n.get('focused') and n.get('app_id') == 'k230.card.one'
                             for n in nodes(ipc(kind=4))))
            ipc('card_shell enter')
            before = wait(lambda: (s if (s := scene()).get('selected_scene_valid') == '1' else None))
            self.assertEqual(before['selected_app_id'], 'k230.card.one')
            output = ipc(kind=3)[0]['rect']
            x, y = output['width']//2, output['height']//2
            commands = ('card_shell debug-scene; '
                        f'card_shell down 7 {x} {y}; '
                        f'card_shell motion 7 {x-60} {y}; '
                        f'card_shell motion 7 {x-100} {y}; card_shell debug-scene')
            rows = ipc(commands)
            first, immediate = fields(rows[0]), fields(rows[-1])
            self.assertAlmostEqual(float(immediate['card_dx']), -100, delta=1)
            self.assertEqual(immediate['scene_render_syncs'], first['scene_render_syncs'],
                             'a render ran inside one IPC command batch')
            if rotated:
                self.assertGreater(int(immediate['scene_redraw_coalesced']),
                                   int(first['scene_redraw_coalesced']))
            else:
                self.assertEqual(immediate['scene_redraw_coalesced'], '0')
            held = wait(lambda: (s if int((s := scene())['scene_render_syncs']) >
                                int(immediate['scene_render_syncs']) and
                                abs(int(s['selected_scene_x'])-int(before['selected_scene_x'])+100) <= 1
                                else None))
            counts = client_frames()
            wait(lambda: all(a >= b+2 for a, b in zip(client_frames(), counts)))
            if rotated:
                wait(lambda: int(scene()['scene_timer_coalesced']) > int(first['scene_timer_coalesced']))
            else:
                self.assertEqual(scene()['scene_timer_coalesced'], '0')
            structural_before = int(scene()['scene_structural_syncs'])
            start('k230-video-software')
            wait(lambda: int(scene()['scene_structural_syncs']) > structural_before)
            ipc('card_shell up 7', check=False)  # map may have cancelled/drained the owned stream
            time.sleep(.7)
            settled = scene()
            self.assertGreater(int(settled['filter_bilinear']), int(held['filter_bilinear']),
                               'settled full-quality sampling was not restored')
            # Inspect visibility in the same dispatch as expansion starts,
            # before any output frame can conceal a stale chrome state.
            expanding_rows = ipc('card_shell activate; card_shell debug-scene')
            expanding = fields(expanding_rows[-1])
            self.assertEqual(expanding['chrome_enabled'], '0')
            wait(lambda: scene()['active'] == '0')
            results.update(before=before, immediate=immediate, held=held, settled=settled,
                           expanding=expanding, client_frames_before=counts,
                           client_frames_after=client_frames(), status='PASS')
            print('PASS actual scene scheduling: rotated=%s reduced=%s' % (rotated, reduced), flush=True)
        finally:
            (work/'result.json').write_text(json.dumps(results, indent=2)+'\n')
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
            for stream in streams:
                stream.close()
            runtime.cleanup()


if __name__ == '__main__':
    unittest.main()
