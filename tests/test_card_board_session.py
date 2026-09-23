#!/usr/bin/env python3
"""Host fault-injection of service ownership and cleanup, never board proof."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tools/card-composition-board-session.sh'
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root=pathlib.Path(os.environ['FAKE_ROOT'])
state=json.loads((root/'state').read_text())
name=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
with (root/'trace').open('a') as f: f.write(name+' '+' '.join(args)+'\n')
def save(): (root/'state').write_text(json.dumps(state))
if name=='pgrep': sys.exit(0 if os.environ.get('COMPETITOR') else 1)
if name=='systemd-run':
    assert not state['shell'], 'normal shell must stop first'
    state['probe']=True; save()
    sys.exit(int(os.environ.get('PROBE_FAIL', '0')))
if name=='journalctl':
    print('private noise https://private.invalid/token', flush=True)
    print('K230_CARD attached cards=2 renderer=pixman source=live-scene-surfaces', flush=True)
    print('K230_CARD secret path=/private/secret', flush=True)
    sys.exit(0)
if name=='systemctl':
    action=args[0]
    unit=next((x for x in args[1:] if not x.startswith('-')), '')
    key='probe' if unit=='k230-card-composition-probe.service' else unit
    if action=='is-failed': sys.exit(1)
    if action=='is-active': sys.exit(0 if state.get(key) else 3)
    if action=='show':
        if '--property=MainPID' in args: print(0)
        elif '--property=InvocationID' in args: print('a'*32)
        elif '--property=LoadState' in args: print('loaded')
        elif '--property=CPUUsageNSec' in args: print(10000)
        elif '--property=MemoryCurrent' in args: print(20000)
    if action=='start':
        assert key!='shell' or not state['probe'], 'probe must stop before normal shell'
        if os.environ.get('RESTORE_FAIL') and key=='shell': sys.exit(1)
        state[key]=True; save()
    if action=='stop': state[key]=False; save()
'''


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='card-harness-')
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.runtime = self.root / 'runtime'
        fake = self.bin / 'fake'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        for cmd in ['systemctl', 'systemd-run', 'pgrep', 'journalctl']:
            (self.bin / cmd).symlink_to(fake)
        for cmd in ['card-composition-probe', 'card-composition-probe-client']:
            (self.bin / cmd).write_text('#!/bin/sh\nexit 0\n')
            (self.bin / cmd).chmod(0o755)
        (self.root / 'state').write_text(json.dumps(dict(shell=True, seatd=True, probe=False)))
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                        FAKE_ROOT=str(self.root), K230_CARD_RUNTIME=str(self.runtime),
                        K230_CARD_USER=os.environ['USER'], K230_CARD_DURATION='2')

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *args, **env):
        return subprocess.run([str(HARNESS), *args], env=dict(self.env, **env),
                              text=True, capture_output=True, timeout=8)

    def probe(self, **env):
        return self.call('--probe', str(self.bin / 'card-composition-probe'), '--restore-shell', **env)

    def state(self):
        return json.loads((self.root / 'state').read_text())

    def test_normal_and_collection(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.state()['shell'])
        self.assertFalse(self.state()['probe'])
        self.assertEqual(self.call('--verify-restored').returncode, 0)
        result = self.call('--collect')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('K230_CARD attached', result.stdout)
        self.assertIn('UNVERIFIED', result.stdout)
        self.assertNotIn('private.invalid', result.stdout)
        self.assertNotIn('/private/secret', result.stdout)
        trace = (self.root / 'trace').read_text()
        self.assertLess(trace.index('systemctl stop shell'), trace.index('systemd-run'))
        self.assertLess(trace.index('systemctl stop k230-card-composition-probe.service'), trace.index('systemctl start shell'))

    def test_probe_failure_restores_and_preserves_error(self):
        self.assertNotEqual(self.probe(PROBE_FAIL='42').returncode, 0)
        self.assertTrue(self.state()['shell'])
        self.assertFalse(self.state()['probe'])

    def test_restore_failure_is_not_success(self):
        self.assertNotEqual(self.probe(RESTORE_FAIL='1').returncode, 0)
        self.assertIn('restore_failed', (self.runtime / 'session.jsonl').read_text())

    def test_competing_sway_prevents_both_starts(self):
        self.assertNotEqual(self.probe(COMPETITOR='1').returncode, 0)
        trace = (self.root / 'trace').read_text()
        self.assertNotIn('systemd-run', trace)
        self.assertNotIn('systemctl start shell', trace)

    def test_lock_rejects_second_operator(self):
        import fcntl
        self.runtime.mkdir()
        with (self.runtime / 'operator.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.call('--restore-shell').returncode, 75)

    def test_missing_seatd_fails_verification(self):
        state = self.state()
        state['seatd'] = False
        (self.root / 'state').write_text(json.dumps(state))
        self.assertNotEqual(self.call('--verify-restored').returncode, 0)

    def test_signal_stops_probe_before_restoring(self):
        process = subprocess.Popen([str(HARNESS), '--probe',
                                    str(self.bin / 'card-composition-probe'), '--restore-shell'],
                                   env=dict(self.env, K230_CARD_DURATION='30'),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not self.state()['probe']:
                time.sleep(.05)
            self.assertTrue(self.state()['probe'])
            process.terminate()
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 143)
            self.assertTrue(self.state()['shell'])
            self.assertFalse(self.state()['probe'])
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_explicit_restore_required_before_stop(self):
        self.assertEqual(self.call('--probe', str(self.bin / 'card-composition-probe')).returncode, 64)
        self.assertTrue(self.state()['shell'])


if __name__ == '__main__':
    unittest.main()
