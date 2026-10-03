import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('blkid_trial', Path(__file__).parents[1] / 'tools/mainline-drm-blkid-trial.py')
t = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(t)
TOKEN = 'a' * 32


def receipt(token, stage, rc=0, match=1):
    return f'K230_BLKID_BEGIN {token} STAGE={stage}\nK230_BLKID_END {token} STAGE={stage} RC={rc} MATCH={match}\n'.encode()


class Clock:
    def __init__(self): self.n = 0
    def __call__(self): self.n += .1; return self.n


class Session:
    pump = t.rd.PrivateSession.pump
    failure = None
    kind = 'unknown'
    def __init__(self, *args):
        self.buffer = b''; self.log = io.BytesIO(); self.writes = []; self.chunks = []; self.closed = False
        self.port = SimpleNamespace(read=lambda n: self.chunks.pop(0) if self.chunks else b'')
    def write(self, data):
        self.writes.append(data); command = data.decode()
        found = re.search(r'[0-9a-f]{32}', command)
        if found is None: return
        token = found.group()
        if 'K230_BLKID_RAW_BEGIN' in command:
            token = re.search(r'K230_BLKID_RAW_BEGIN ([0-9a-f]{32})', command).group(1)
            stage = 'retrieval'; raw = b'ID_FS_TYPE=ext4\nID_FS_LABEL=NIXOS_SD\n'
            b = f'K230_BLKID_RAW_BEGIN {token} SIZE={len(raw)}\n'.encode() + raw + f'K230_BLKID_RAW_END {token} RC=0\nsh-5.3# '.encode()
            if self.failure == 'retrieval':
                if self.kind == 'unknown': return
                if self.kind == 'nonzero': b = b.replace(b'RC=0', b'RC=1')
                if self.kind == 'duplicate': b += b
                if self.kind == 'stale': b = b.replace(token.encode(), b'f'*32)
                if self.kind == 'malformed': b = re.sub(rb'SIZE=[0-9]+', b'SIZE=999', b)
                if self.kind == 'mismatch': b = b.replace(b'sh-5.3# ', b'> ')
        elif 'K230_BLKID_BEGIN' in command:
            stage = re.search(r'STAGE=([a-z-]+)', command).group(1)
            b = receipt(token, stage)
            if stage == self.failure:
                if self.kind == 'unknown': return
                if self.kind == 'nonzero': b = receipt(token, stage, 1, 0)
                if self.kind == 'timeout': b = receipt(token, stage, 124, 0)
                if self.kind == 'mismatch': b = receipt(token, stage, 0, 0)
                if self.kind == 'duplicate': b += b
                if self.kind == 'stale': b = receipt('f' * 32, stage)
                if self.kind == 'malformed': b = b.replace(b'RC=0', b'RC=256')
        elif 'K230_RDINIT_RX' in command: b = f'K230_RDINIT_RX {token}\n'.encode()
        elif 'K230_RDINIT_TRUE' in command: b = f'K230_RDINIT_TRUE {token} RC=0\n'.encode()
        elif 'K230_RDINIT_MOUNT_BEGIN' in command: b = f'K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n'.encode()
        elif 'K230_RDINIT_UP_BEGIN' in command: b = f'K230_RDINIT_UP_BEGIN {token}\n1.23 0.50\nK230_RDINIT_UP_END {token} RC=0\n'.encode()
        elif 'K230_RDINIT_REBOOT' in command: b = f'K230_RDINIT_REBOOT {token}\n'.encode()
        else: return
        self.chunks += [b] if self.kind == 'duplicate' else [b[:len(b)//2], b[len(b)//2:]]
    def close(self): self.closed = True


def tokens():
    i = 0
    def make():
        nonlocal i
        i += 1
        return f'{i:032x}'
    return make


class ProtocolTests(unittest.TestCase):
    def test_complete_real_pump_split_receipts_and_shared_output(self):
        s = Session(); facts = {}
        t.diagnostic(s, facts, clock=Clock(), token_factory=tokens())
        self.assertTrue(facts['passed'])
        commands = [x.decode() for x in s.writes]
        self.assertEqual(len(commands), 13)
        self.assertEqual(sum('/bin/udevadm test-builtin' in x for x in commands), 1)
        created = next(x for x in commands if 'STAGE=output' in x)
        probed = next(x for x in commands if 'STAGE=blkid' in x)
        self.assertIn('/k230-blkid-' + '0' * 31 + '1', created)
        self.assertIn('/k230-blkid-' + '0' * 31 + '1' + '/output', probed)
        self.assertNotIn('reboot', ''.join(commands))

    def test_every_bad_stage_stops_without_later_input(self):
        for stage in t.STAGES:
            for kind in ('unknown', 'nonzero', 'timeout', 'mismatch', 'duplicate', 'stale', 'malformed'):
                with self.subTest(stage=stage, kind=kind):
                    s = Session(); s.failure = stage; s.kind = kind; facts = {}
                    with self.assertRaises(t.Stopped):
                        t.diagnostic(s, facts, timeout=1, clock=Clock(), token_factory=tokens())
                    self.assertIn('STAGE=' + stage, s.writes[-1].decode())
                    self.assertNotIn('reboot', b''.join(s.writes).decode())
                    self.assertNotIn('passed', facts)
                    if stage != 'blkid': self.assertNotIn('test-builtin', b''.join(s.writes).decode())

    def test_invalid_timeout_sends_nothing(self):
        for timeout in (0, -1, 31, float('nan'), float('inf')):
            s = Session()
            with self.assertRaises(ValueError): t.diagnostic(s, {}, timeout=timeout)
            self.assertEqual(s.writes, [])

    def test_retrieval_bad_or_unknown_stops_before_reboot(self):
        for kind in ('unknown', 'nonzero', 'duplicate', 'stale', 'malformed', 'mismatch'):
            with self.subTest(kind=kind):
                s = Session(); s.failure = 'retrieval'; s.kind = kind; facts = {}
                with self.assertRaises(t.Stopped):
                    t.diagnostic(s, facts, timeout=1, clock=Clock(), token_factory=tokens())
                self.assertFalse(facts['retrieval']['complete'])
                self.assertNotIn('passed', facts)
                self.assertIn('K230_BLKID_RAW_BEGIN', s.writes[-1].decode())
                self.assertNotIn('REBOOT', b''.join(s.writes).decode())

    def test_duplicate_stage_token_prevents_stage_write(self):
        s = Session()
        with self.assertRaises(ValueError): t.diagnostic(s, {}, clock=Clock(), token_factory=lambda: TOKEN)
        self.assertEqual(len(s.writes), 4)

    def test_parser_echo_stale_order_rc_range(self):
        good = receipt(TOKEN, 'blkid')
        self.assertEqual(t.stage_result(good, TOKEN, 'blkid'), {'rc': 0, 'match': True})
        for b in (good + good, good.replace(TOKEN.encode(), b'f'*32), b"printf '" + good.replace(b'\n', b'\\n') + b"'\n", good.replace(b'RC=0', b'RC=256'), good.replace(b'RC=0', b'RC=1'), b'\n'.join(good.splitlines()[::-1]) + b'\n'):
            self.assertIsNone(t.stage_result(b, TOKEN, 'blkid'))

    def test_unknown_readiness_no_reception(self):
        s = Session()
        with mock.patch.object(t.rd, 'await_initrd_ready', return_value=False), mock.patch.object(t.rd, 'verified_load', return_value=True), mock.patch.object(t.rd, 'verified_crc', return_value=True), mock.patch.object(t.rd, 'verified_bootargs', return_value=True), mock.patch.object(t.time, 'monotonic', side_effect=Clock()):
            s.line = lambda command, **kw: setattr(s, 'buffer', t.rd.PROMPT if command == 'reboot' else b'')
            s.command = lambda *args: b'ok'
            with self.assertRaises(t.Stopped): t.boot(s, {'manifest': {'files': {k: {'bytes': 1} for k, _, _, _ in t.rd.LOADS}}, 'bootargs': 'fixture'})
        self.assertEqual(s.writes, [])

    def test_guard_rejects_present_and_dangling_registration(self):
        with tempfile.TemporaryDirectory() as d:
            marker = Path(d)/'marker'
            with mock.patch.object(t.rd, 'prepare_trial', return_value={'helper_text': "print('CHECKED')\n", 'bootargs': 'rdinit fixture'}):
                p = t.prepare(None, None, None)
            helper = p['helper_text'].replace('/nix-path-registration', str(marker))
            self.assertEqual(p['bootargs'], 'rdinit fixture')
            self.assertEqual(subprocess.run([sys.executable, '-c', helper], capture_output=True).returncode, 0)
            marker.write_text('pending')
            self.assertNotEqual(subprocess.run([sys.executable, '-c', helper], capture_output=True).returncode, 0)
            marker.unlink(); marker.symlink_to(Path(d)/'absent')
            self.assertNotEqual(subprocess.run([sys.executable, '-c', helper], capture_output=True).returncode, 0)

    def run_flow(self, failure=None, return_ok=True):
        with tempfile.TemporaryDirectory() as d:
            args = SimpleNamespace(bundle=Path(d)/'bundle', manifest=Path(d)/'manifest', normal_report=Path(d)/'normal', log=Path(d)/'uart', result=Path(d)/'result')
            s = Session(); s.failure = failure
            before = {'boot_id': 'old'}; after = {'boot_id': 'new'}
            original_diagnostic = t.diagnostic
            with mock.patch.object(t, 'diagnostic', side_effect=lambda session, facts: original_diagnostic(session, facts, clock=Clock())), mock.patch.object(t, 'prepare', return_value={'normal': {}, 'bundle': args.bundle, 'system': '/candidate'}), mock.patch.object(t.rd, 'LOCK_PATH', str(Path(d)/'lock')), mock.patch.object(t.rd, 'PrivateSession', return_value=s), mock.patch.dict(sys.modules, {'serial': SimpleNamespace()}), mock.patch.object(t.system, 'wait_prompt', return_value=True), mock.patch.object(t.system, 'normal_check', side_effect=[before, after]) as check, mock.patch.object(t, 'boot'), mock.patch.object(t.system, 'wait_normal', return_value=return_ok) as wait, mock.patch.object(t.time, 'monotonic', side_effect=Clock()):
                ok = t.run(args)
                result = json.loads(args.result.read_text())
            self.assertTrue(s.closed)
            return ok, result, s.writes, check.call_count, wait.call_count

    def test_complete_flow_single_reboot_protected_postflight(self):
        ok, result, writes, checks, waits = self.run_flow()
        self.assertTrue(ok)
        self.assertEqual(sum(b'/bin/reboot -ff' in b for b in writes), 1)
        self.assertEqual(result['status'], 'recovery-verified-diagnostic-passed')
        self.assertTrue(result['diagnostic']['retrieval']['complete'])
        self.assertEqual(result['normal_recovery']['boot_id'], 'new')
        self.assertEqual((checks, waits), (2, 1))

    def test_retrieval_failure_result_retains_gates_without_reboot(self):
        ok, result, writes, checks, waits = self.run_flow('retrieval')
        self.assertFalse(ok)
        self.assertTrue(result['diagnostic']['blkid']['match'])
        self.assertFalse(result['diagnostic']['retrieval']['complete'])
        self.assertNotIn(b'/bin/reboot', b''.join(writes))
        self.assertEqual((checks, waits), (1, 0))

    def test_normal_return_timeout_keeps_probe_facts_no_retry(self):
        ok, result, writes, checks, waits = self.run_flow(return_ok=False)
        self.assertFalse(ok)
        self.assertTrue(result['diagnostic']['passed'])
        self.assertIsNone(result['normal_recovery'])
        self.assertEqual(sum(b'/bin/reboot -ff' in b for b in writes), 1)
        self.assertEqual((checks, waits), (1, 1))


class ShellTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        for p in ('proc', 'sys/class/block', 'sys/class/mmc_host', 'dev', 'bin'):
            (root / p).mkdir(parents=True, exist_ok=True)
        (root/'proc/mounts').write_text(f'proc {root}/proc proc rw 0 0\nsysfs {root}/sys sysfs rw 0 0\ndevtmpfs {root}/dev devtmpfs rw 0 0\n')
        physical = root/'sys/devices/platform/soc/91581000.sdhci1/mmc_host/mmc1'
        part = physical/'mmc1:59b4/block/mmcblk1/mmcblk1p2'; part.mkdir(parents=True)
        (part/'partition').write_text('2\n'); (part/'dev').write_text('179:2\n')
        (root/'sys/class/block/mmcblk1p2').symlink_to(part)
        (root/'sys/class/mmc_host/mmc1').symlink_to(physical)
        (root/'dev/mmcblk1p2').write_text('fixture')
        (root/'bin/stat').write_text('#!/bin/sh\nif [ "$2" = "%t:%T" ]; then printf "b3:2\\n"; else exec /usr/bin/stat "$@"; fi\n'); (root/'bin/stat').chmod(0o700)
        (root/'bin/udevadm').write_text('#!/bin/sh\nprintf "ID_FS_TYPE=ext4\\nID_FS_LABEL=NIXOS_SD\\n"\n'); (root/'bin/udevadm').chmod(0o700)
        (root/'bin/mount').write_text('#!/bin/sh\nexit 0\n'); (root/'bin/mount').chmod(0o700)
        return root, part

    def execute(self, root, stage):
        command = t.stage_command(TOKEN, stage)
        # Every kernel path is isolated before executing; no host sysfs,
        # devtmpfs, mounts, trace settings or real block devices are touched.
        for prefix in ('/sys', '/proc', '/dev', '/k230-blkid-'):
            command = re.sub(r'(?<![A-Za-z0-9_/])' + re.escape(prefix) + (r'(?=$|[^A-Za-z0-9_-])' if prefix != '/k230-blkid-' else ''), lambda m: str(root) + m.group(), command)
        for binary in ('stat', 'udevadm', 'mount'):
            command = command.replace('/bin/' + binary, str(root/'bin'/binary))
        # Permit only the fixture's ordinary file to simulate the -b gate.
        preamble = f'test() {{ if [ "$1" = -b ]; then builtin test -f "$2"; else builtin test "$@"; fi; }}; '
        self.assertNotRegex(command, r'(?<![^ ])/(?:sys|proc|dev)/')
        p = subprocess.run(['bash', '-c', preamble + command], capture_output=True, timeout=3)
        self.assertEqual(p.returncode, 0, p.stderr)
        return t.stage_result(p.stdout, TOKEN, stage)

    def test_actual_generated_shell_setup_ancestry_output_probe(self):
        with tempfile.TemporaryDirectory() as d:
            root, part = self.fixture(d)
            for stage in t.STAGES:
                with self.subTest(stage=stage): self.assertEqual(self.execute(root, stage), {'rc': 0, 'match': True})
            self.assertEqual((root/('k230-blkid-' + TOKEN)/'output').stat().st_mode & 0o777, 0o600)

    def test_wrong_partition_or_dev_major_fails(self):
        for field, value in (('partition', '1\n'), ('dev', '179:3\n'), ('dev', '179:garbled\n'), ('dev', '179:2:3\n'), ('dev', ':2\n')):
            with tempfile.TemporaryDirectory() as d:
                root, part = self.fixture(d); (part/field).write_text(value)
                self.assertFalse(self.execute(root, 'ancestry')['match'])

    def test_malformed_stat_and_wrong_sd1_ancestry_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = self.fixture(d)
            (root/'bin/stat').write_text('#!/bin/sh\nprintf "b3:garbled\\n"\n')
            self.assertFalse(self.execute(root, 'ancestry')['match'])
        with tempfile.TemporaryDirectory() as d:
            root, _ = self.fixture(d)
            (root/'sys/class/mmc_host/mmc1').unlink()
            (root/'sys/class/mmc_host/mmc1').symlink_to(root/'sys/devices/platform/soc/91580000.sdhci0/mmc_host/mmc1')
            self.assertFalse(self.execute(root, 'ancestry')['match'])

    def test_generated_retrieval_has_exact_bounded_bytes_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            root, _ = self.fixture(d)
            self.execute(root, 'output'); self.execute(root, 'blkid')
            command = t.retrieval_command('b'*32, TOKEN).replace('/k230-blkid-', str(root)+'/k230-blkid-').replace('/bin/stat', str(root/'bin/stat'))
            p = subprocess.run(['bash', '-c', command + "; printf 'sh-5.3# '"], capture_output=True, timeout=3)
            result = t.retrieval_result(p.stdout, 'b'*32)
            self.assertEqual(result['bytes'], len(b'ID_FS_TYPE=ext4\nID_FS_LABEL=NIXOS_SD\n'))
            for malformed in (p.stdout+p.stdout, re.sub(rb'SIZE=[0-9]+', b'SIZE=999', p.stdout), p.stdout.replace(b'RC=0', b'RC=1'), p.stdout.replace(b'sh-5.3# ', b'> ')):
                self.assertIsNone(t.retrieval_result(malformed, 'b'*32))
            output = root/('k230-blkid-'+TOKEN)/'output'
            output.write_bytes(b'x'*16385)
            oversized = subprocess.run(['bash', '-c', command], capture_output=True, timeout=3)
            self.assertNotIn(b'x'*100, oversized.stdout)
            self.assertIsNone(t.retrieval_result(oversized.stdout, 'b'*32))

    def test_duplicate_wrong_missing_properties_and_nonzero_fail(self):
        variants = ('ID_FS_LABEL=NIXOS_SD\n', 'ID_FS_TYPE=ext4\nID_FS_LABEL=OTHER\n', 'ID_FS_TYPE=ext4\n', 'ID_FS_TYPE=ext4\nID_FS_TYPE=ext4\nID_FS_LABEL=NIXOS_SD\n')
        for output in variants:
            with tempfile.TemporaryDirectory() as d:
                root, _ = self.fixture(d); self.execute(root, 'output')
                (root/'bin/udevadm').write_text('#!/bin/sh\ncat <<\'EOF\'\n' + output + 'EOF\n')
                self.assertFalse(self.execute(root, 'blkid')['match'])
        with tempfile.TemporaryDirectory() as d:
            root, _ = self.fixture(d); self.execute(root, 'output')
            (root/'bin/udevadm').write_text('#!/bin/sh\nexit 1\n')
            self.assertEqual(self.execute(root, 'blkid'), {'rc': 1, 'match': False})


if __name__ == '__main__': unittest.main()
