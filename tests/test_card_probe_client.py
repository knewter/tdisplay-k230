#!/usr/bin/env python3
"""Actual Wayland protocol smoke; requires a native client and native Sway.

Headless Pixman is host evidence only. No DRM, panel or touch claims.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def wait_for(predicate, label, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out: {label}")


def records(path):
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # A final line may still be in flight.
    return rows


def run(client, sway):
    swaymsg = str(Path(sway).with_name('swaymsg'))
    with tempfile.TemporaryDirectory(prefix='card-client-test-') as directory:
        root = Path(directory)
        root.chmod(0o700)
        config = root / 'sway.conf'
        config.write_text('output HEADLESS-1 mode 568x1232\n'
                          'seat seat0 fallback true\n'
                          'for_window [app_id="^k230.card."] floating enable, resize set 240 600\n'
                          'for_window [app_id="k230.card.one"] move position 0 0\n'
                          'for_window [app_id="k230.card.two"] move position 280 0\n')
        env = dict(os.environ, XDG_RUNTIME_DIR=directory, WLR_BACKENDS='headless',
                   WLR_RENDERER='pixman', WLR_HEADLESS_OUTPUTS='1',
                   SWAYSOCK=str(root / 'ipc.sock'))
        processes = []
        with (root / 'sway.log').open('w') as compositor_log:
            compositor = subprocess.Popen([sway, '-c', str(config)], env=env,
                                          stdout=compositor_log, stderr=subprocess.STDOUT)
            processes.append(compositor)
            try:
                wait_for(lambda: (root / 'ipc.sock').exists(), 'Sway IPC socket')
                sockets = list(root.glob('wayland-*'))
                env['WAYLAND_DISPLAY'] = next(p.name for p in sockets if not p.name.endswith('.lock'))
                logs = {}
                for name in ['one', 'two']:
                    path = root / f'{name}.jsonl'
                    logs[name] = path
                    with path.open('w') as log:
                        args = [client, '--app-id', f'k230.card.{name}', '--duration', '15']
                        if name == 'two':
                            args.append('--refuse-close')
                        processes.append(subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.PIPE))
                for name, path in logs.items():
                    wait_for(lambda p=path: any(r['frames'] > 5 and r['child_frames'] > 5 and
                                               r['releases'] > 0 and r['child_releases'] > 0
                                               for r in records(p)), f'{name} parent and desynchronized child progress')
                def ipc(command):
                    reply = subprocess.check_output([swaymsg, '-r', command], env=env, text=True)
                    assert all(row['success'] for row in json.loads(reply)), reply
                ipc('[app_id="k230.card.two"] kill')
                wait_for(lambda: any(r['event'] == 'close_refused' for r in records(logs['two'])), 'actual close refusal')
                before = records(logs['two'])[-1]['frames']
                wait_for(lambda: records(logs['two'])[-1]['frames'] > before + 5, 'refusing client remains animated')
                assert processes[2].poll() is None, 'refusing client exited'
                ipc('[app_id="k230.card.one"] kill')
                assert processes[1].wait(timeout=5) == 0
                assert any(r['event'] == 'close_accepted' for r in records(logs['one']))
                # Hide the only surviving client. Watchdog keeps reporting age,
                # but callbacks must cease; a timer-based animation would lie.
                ipc('[app_id="k230.card.two"] move container to workspace hidden')
                time.sleep(2.2)
                rows = records(logs['two'])
                assert rows[-1]['callback_age_ms'] > 1000, rows[-1]
                assert rows[-1]['child_callback_age_ms'] > 1000, rows[-1]
                for row in rows:
                    assert row['presentation'] == 'unmeasured'
                    assert row['format'] == 'XRGB8888'
                ipc('workspace hidden')
                frozen = rows[-1]['frames']
                wait_for(lambda: records(logs['two'])[-1]['frames'] > frozen + 5, 'callbacks resume after output return')
                subprocess.run([swaymsg, '-r', 'exit'], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                compositor.wait(timeout=5)
                assert processes[2].wait(timeout=5) != 0, 'disconnect must report error'
                print('PASS actual XDG configure, SHM release, independent child callbacks, close acceptance/refusal, hidden starvation and return, disconnect')
            except Exception:
                print((root / 'sway.log').read_text()[-4000:])
                for path in root.glob('*.jsonl'):
                    print(path.name, path.read_text()[-2500:])
                raise
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', required=True)
    parser.add_argument('--sway', required=True)
    args = parser.parse_args()
    run(args.client, args.sway)
