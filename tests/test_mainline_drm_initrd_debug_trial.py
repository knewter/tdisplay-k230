import hashlib
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

SPEC = importlib.util.spec_from_file_location('debug_trial', Path(__file__).parents[1] / 'tools/mainline-drm-initrd-debug-trial.py')
t = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(t)
TOKEN = 'a' * 32
BOOT = '11111111-1111-1111-1111-111111111111'
NORMAL_BOOT = '22222222-2222-2222-2222-222222222222'
SELECTED = '/nix/store/' + 'a' * 32 + '-candidate'
ARGS = 'bootargs=console=ttyS0,115200n8 root=fstab loglevel=4 loglevel=7 init=' + SELECTED + '/init'
PREPARED = {'system': SELECTED, 'pid1': '/nix/store/systemd/lib/systemd/systemd', 'bootargs': t.bootargs(ARGS, SELECTED)}


class Clock:
    def __init__(self, step=.1): self.n = 0; self.step = step
    def __call__(self): self.n += self.step; return self.n


def tokens():
    n = 0
    def make():
        nonlocal n
        n += 1
        return f'{n:032x}'
    return make


def response(token, stage, body=b'', rc=0):
    return f'K230_IDBG_BEGIN {token} {stage}\n'.encode() + body + f'\nK230_IDBG_END {token} {stage} RC={rc}\n'.encode() + b'\x1b[?2004hsh-5.3# '


def unit_body(names, fields):
    values = {'ExecMainPID': '55', 'ControlPID': '0', 'ExecMainStatus': '0', 'ActiveState': 'inactive', 'SubState': 'dead', 'TTYPath': '/dev/ttyS0', 'Job': '', 'Result': 'success'}
    blocks = []
    for name in names:
        v = dict(values, Id=name, ControlGroup='/system.slice/' + name)
        if name == 'debug-shell.service': v.update(ActiveState='active', SubState='running')
        blocks.append('\n'.join(k + '=' + v[k] for k in fields))
    return ('\n\n'.join(blocks) + '\n').encode()


class Session:
    pump = t.rd.PrivateSession.pump
    def __init__(self):
        self.buffer = b''; self.log = io.BytesIO(); self.writes = []; self.chunks = []; self.closed = False
        self.port = SimpleNamespace(read=lambda n: self.chunks.pop(0) if self.chunks else b'')
        self.fail = None; self.kind = 'unknown'; self.identity_changes = {}; self.renew_changes = {}; self.guard_count = 0
    def write(self, data):
        self.writes.append(data); s = data.decode()
        m = re.search(r'K230_IDBG_BEGIN ([0-9a-f]{32}) ([a-z-]+)', s)
        if not m:
            r = re.search(r'K230_RDINIT_REBOOT ([0-9a-f]{32})', s)
            if r: self.chunks += [f'K230_RDINIT_REBOOT {r[1]}\n'.encode()]
            return
        token, stage = m.groups(); body = b''
        if stage == 'receipt': body = b'receipt=1\n'
        elif stage == 'identity':
            self.guard_count += 1
            v = {'shell_pid': '55', 'shell_ppid': '1', 'uid': '0', 'uname': '7.3.0-rc5', 'boot_id': BOOT, 'pid1': PREPARED['pid1'], 'tty': '/dev/ttyS0', 'cmdline': PREPARED['bootargs'].removeprefix('bootargs='), 'initrd': '1'}
            v.update(self.identity_changes)
            if self.guard_count > 1: v.update(self.renew_changes)
            body = ''.join(k + '=' + x + '\n' for k, x in v.items()).encode()
        elif stage == 'mounts': body = b'mounts=1\n'
        elif stage == 'ownership': body = unit_body(('debug-shell.service',), ('Id', 'ExecMainPID', 'ActiveState', 'SubState', 'TTYPath', 'Job'))
        elif stage == 'boundary': body = unit_body(t.ROOT_UNITS, ('Id', 'ActiveState', 'SubState', 'Job'))
        elif stage.startswith('raw-'):
            if stage == 'raw-units': raw = unit_body(t.UDEV_UNITS, ('Id', 'ActiveState', 'SubState', 'Result', 'ExecMainPID', 'ControlPID', 'ExecMainStatus', 'ControlGroup'))
            elif stage == 'raw-ping': raw = b''
            else: raw = b'private bounded diagnostic output\n'
            body = f'SIZE={len(raw)} SHA256={hashlib.sha256(raw).hexdigest()}\n'.encode() + raw
        rc = 0
        if stage == self.fail:
            if self.kind == 'unknown': return
            if self.kind == 'rc': rc = 124
            if self.kind == 'property': body = body.replace(b'active\n', b'failed\n').replace(b'mounts=1', b'mounts=0')
            if self.kind == 'hash': body = body.replace(b'SHA256=', b'SHA256=f')
            if self.kind == 'pending': body = body.replace(b'Job=\n', b'Job=7\n')
            if self.kind == 'tty': body = body.replace(b'TTYPath=/dev/ttyS0', b'TTYPath=/dev/tty9')
            if self.kind == 'pid': body = body.replace(b'ExecMainPID=55', b'ExecMainPID=56')
            if self.kind in ('queued-target','queued-closure'):
                name = 'initrd-switch-root.target' if self.kind == 'queued-target' else 'initrd-find-nixos-closure.service'
                blocks = body.decode().split('\n\n')
                body = '\n\n'.join(block.replace('Job=','Job=7') if 'Id='+name+'\n' in block else block for block in blocks).encode()
                assert b'Job=7' in body
        b = response(token, stage, body, rc)
        if stage == self.fail:
            if self.kind == 'duplicate': b += b
            if self.kind == 'stale': b = b.replace(token.encode(), b'f' * 32)
            if self.kind == 'truncate': b = b[:b.find(b'K230_IDBG_END') + 30]
        self.chunks += [b[:len(b)//2], b[len(b)//2:]]
    def close(self): self.closed = True


class ProtocolTests(unittest.TestCase):
    def test_full_split_frames_private_raw_before_renewed_guards(self):
        s = Session(); facts = {}
        t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, facts, clock=Clock(), token_factory=tokens())
        self.assertTrue(facts['complete'])
        self.assertEqual(set(facts['snapshots']), {'jobs', 'units', 'ping', 'journal', 'workers'})
        self.assertTrue(all(p['retrieved'] for p in facts['snapshots'].values()))
        self.assertEqual(s.guard_count, 2)
        text = b''.join(s.writes).decode()
        self.assertNotIn('reboot', text)
        self.assertLess(text.index('raw-workers'), text.rindex(' identity'))
        self.assertIn(b'private bounded diagnostic output', s.log.getvalue())
        self.assertNotIn('private bounded diagnostic output', json.dumps(facts))

    def test_each_unknown_duplicate_stale_truncated_stage_stops(self):
        stages = ('receipt', 'identity', 'mounts', 'ownership', 'boundary', 'output', 'jobs', 'raw-jobs', 'units', 'raw-units', 'ping', 'raw-ping', 'journal', 'raw-journal', 'workers', 'raw-workers')
        for stage in stages:
            for kind in ('unknown', 'duplicate', 'stale', 'truncate'):
                with self.subTest(stage=stage, kind=kind):
                    s = Session(); s.fail = stage; s.kind = kind
                    with self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
                    self.assertIn(' ' + stage + '\\n', s.writes[-1].decode())
                    self.assertNotIn(b'reboot', b''.join(s.writes))

    def test_identity_mismatch_no_observations(self):
        for k, value in [('uid','1'), ('uname','6.6.36'), ('pid1','/bin/sh'), ('shell_pid','1'), ('shell_ppid','2'), ('tty','/dev/tty9'), ('boot_id',NORMAL_BOOT), ('initrd','0'), ('cmdline',PREPARED['bootargs'] + ' rdinit=/bin/sh')]:
            s = Session(); s.identity_changes[k] = value
            with self.subTest(k=k), self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
            self.assertIn(b' identity\\n', s.writes[-1])

    def test_ownership_root_boundary_and_mount_mismatches(self):
        for stage, kind in [('mounts','property'), ('ownership','pid'), ('ownership','tty'), ('ownership','pending'), ('boundary','pending')]:
            s = Session(); s.fail = stage; s.kind = kind
            with self.subTest(stage=stage, kind=kind), self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
            self.assertNotIn(b' jobs\\n', b''.join(s.writes))

    def test_queued_root_target_and_closure_stop_with_services_inactive(self):
        for kind in ('queued-target','queued-closure'):
            s = Session(); s.fail = 'boundary'; s.kind = kind
            with self.subTest(kind=kind), self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
            self.assertIn(b' boundary\\n',s.writes[-1])
            self.assertNotIn(b' jobs\\n',b''.join(s.writes))

    def test_returned_snapshot_failure_retrieves_once_then_stops(self):
        s = Session(); s.fail = 'ping'; s.kind = 'rc'; facts = {}
        with self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, facts, clock=Clock(), token_factory=tokens())
        self.assertTrue(facts['snapshots']['ping']['retrieved'])
        self.assertEqual(facts['snapshots']['ping']['rc'], 124)
        self.assertIn(b' raw-ping\\n', s.writes[-1])
        self.assertNotIn(b' journal\\n', b''.join(s.writes))

    def test_raw_integrity_and_renewed_identity_fail_no_reboot(self):
        s = Session(); s.fail = 'raw-journal'; s.kind = 'hash'
        with self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
        self.assertIn(b' raw-journal\\n', s.writes[-1])
        for changes in [{'boot_id': NORMAL_BOOT}, {'shell_pid': '56'}, {'tty': '/dev/tty9'}]:
            s = Session(); s.renew_changes = changes
            with self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=tokens())
            self.assertNotIn(b'reboot', b''.join(s.writes))

    def test_token_reuse_and_global_deadline_stop(self):
        s = Session()
        with self.assertRaises(ValueError): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(), token_factory=lambda: TOKEN)
        self.assertEqual(len(s.writes), 1)
        s = Session()
        with self.assertRaises(t.Stopped): t.diagnostic(s, PREPARED, {'trial_from_boot_id': NORMAL_BOOT}, {}, clock=Clock(31), token_factory=tokens())
        self.assertLessEqual(len(s.writes), 1)

    def test_real_pump_cap_does_not_hide_accumulated_overflow(self):
        s = Session(); s.chunks = [b'x'*150000,b'y'*150000]
        with self.assertRaisesRegex(t.Stopped,'exceeded bound'): t.exchange(s,TOKEN,'overflow','true',clock=Clock())
        self.assertEqual(len(s.writes),1)
        self.assertEqual(len(s.log.getvalue()),300000)
        self.assertLessEqual(len(s.buffer),131072)

    def test_send_time_cannot_extend_overall_deadline(self):
        clock = Clock(); s = Session(); write = s.write
        def delayed(data):
            write(data); clock.n = 92
        s.write = delayed
        with self.assertRaises(t.Stopped): t.exchange(s,TOKEN,'receipt',"printf 'receipt=1\\n'",clock=clock,deadline=90)
        self.assertEqual(len(s.writes),1)
        self.assertEqual(len(s.log.getvalue()),0)

    def test_parser_refuses_echo_and_interleaved_marker(self):
        good = response(TOKEN, 'jobs')
        self.assertEqual(t.frame(good, TOKEN, 'jobs'), {'rc': 0, 'body': b''})
        for bad in [good + good, good.replace(b'RC=0',b'RC=256'), good.replace(TOKEN.encode(),b'f'*32), b"printf '"+good.replace(b'\n',b'\\n')+b"'\n", good.replace(TOKEN.encode(),TOKEN[:11].encode()+b'[ 7.2] arbitrary printk\n'+TOKEN[11:].encode())]:
            self.assertIsNone(t.frame(bad, TOKEN, 'jobs'))

    def test_readiness_needs_fresh_banner_systemd_primary_prompt(self):
        for chunks, expected in [([b'Linux version 7.3.0-rc5 test\nsystemd 261.2 test\nsh-5.3# '],True), ([b'sh-5.3# '],False), ([b'Linux version 7.3.0-rc5 test\nsystemd 261.2 test\n> '],False), ([b'Linux version 6.6.36 test\nsystemd 261.2 test\nsh-5.3# '],False)]:
            s = Session(); s.chunks = chunks
            self.assertEqual(t.wait_ready(s, timeout=1, clock=Clock()), expected)
            self.assertEqual(s.writes, [])


class ShellTests(unittest.TestCase):
    def test_actual_mount_table_false_final_entry_and_failures(self):
        good = 'rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\nsysfs /sys sysfs rw 0 0\ndev /dev devtmpfs rw 0 0\ncg /sys/fs/cgroup cgroup2 rw 0 0\nlast /run tmpfs rw 0 0\n'
        with tempfile.TemporaryDirectory() as d:
            table = Path(d)/'mounts'
            for shell in ('/bin/sh','/bin/bash'):
                for data, expected in [(good,'1'), (good + '/dev/mmcblk1p2 /sysroot ext4 rw 0 0\n','0'), (good + 'proc /proc proc rw 0 0\n','0'), (good.replace('cgroup2','tmpfs'),'0'), (good.replace('rootfs / rootfs','disk / ext4'),'0')]:
                    table.write_text(data)
                    p = subprocess.run([shell,'-c',t.mounts_command().replace('/proc/mounts',str(table))],capture_output=True,text=True)
                    self.assertEqual(p.stdout,'mounts='+expected+'\n')
                table.unlink()
                p = subprocess.run([shell,'-c',t.mounts_command().replace('/proc/mounts',str(table))],capture_output=True,text=True)
                self.assertEqual(p.stdout,'mounts=0\n')

    def test_actual_worker_fixture_filters_private_status_and_bounds_pids(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); cg = base/'cg/system.slice/systemd-udevd.service'; cg.mkdir(parents=True)
            proc = base/'proc/55'; proc.mkdir(parents=True)
            (proc/'comm').write_text('(udev-worker)\n'); (proc/'status').write_text('Name:\tworker\nState:\tD (disk sleep)\nPRIVATE=do-not-output\n')
            (proc/'wchan').write_text('mmc_claim_host')
            file = cg/'cgroup.procs'; file.write_text('55\n')
            command = t.worker_command(['/system.slice/systemd-udevd.service']).replace('/sys/fs/cgroup',str(base/'cg')).replace('/proc/',str(base/'proc')+'/')
            p = subprocess.run(['/bin/bash','-c',command],capture_output=True,text=True)
            self.assertEqual(p.returncode,0); self.assertIn('STATE=\tD (disk sleep)',p.stdout); self.assertIn('WCHAN=mmc_claim_host',p.stdout)
            self.assertNotIn('PRIVATE',p.stdout)
            file.write_text('55\n' * 17)
            self.assertNotEqual(subprocess.run(['/bin/bash','-c',command],capture_output=True).returncode,0)
            file.unlink()
            self.assertNotEqual(subprocess.run(['/bin/bash','-c',command],capture_output=True).returncode,0)
        with self.assertRaises(ValueError): t.worker_command(['/system.slice/evil; reboot'])

    def test_raw_empty_nonnewline_and_printk_corruption(self):
        for raw in (b'', b'last line without newline', b'a\nb\n'):
            body = f'SIZE={len(raw)} SHA256={hashlib.sha256(raw).hexdigest()}\n'.encode()+raw
            self.assertEqual(t.captured(body),raw)
            with self.assertRaises(t.Stopped): t.captured(body+b'kernel noise')

    def test_actual_outer_shell_pid_not_child_pid(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'bootid').write_text(BOOT+'\n'); (p/'cmdline').write_text(PREPARED['bootargs'].removeprefix('bootargs=')+'\n'); (p/'release').write_text('fixture')
            command = t.identity_command().replace('/proc/sys/kernel/random/boot_id',str(p/'bootid')).replace('/proc/cmdline',str(p/'cmdline')).replace('/etc/initrd-release',str(p/'release'))
            command = command.replace('/bin/readlink -f /proc/1/exe', "printf '/fixture/systemd\\n'").replace('/bin/readlink /proc/$$/fd/0', "printf '/dev/ttyS0\\n'")
            process = subprocess.Popen(['/bin/bash','-c',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            stdout, _ = process.communicate()
            fields = t.properties(stdout, ('shell_pid','shell_ppid','uid','uname','boot_id','pid1','tty','cmdline','initrd'))
            self.assertEqual(fields['shell_pid'],str(process.pid))
            self.assertEqual(fields['shell_ppid'],str(__import__('os').getpid()))


class PreparationTests(unittest.TestCase):
    def test_exact_args_preserve_original_controls_once(self):
        value = t.bootargs(ARGS, SELECTED)
        self.assertEqual(value, ARGS+' '+' '.join(t.CONTROLS))
        for arg in ('rdinit=/bin/sh','clk_ignore_unused','rd.systemd.debug_shell=tty9','rd.systemd.unit=initrd.target','rd.systemd.default_debug_tty=tty9','rd.udev.log_level=debug','systemd.log_target=console','systemd.mask=foo','fsck.mode=force','init=/wrong/init'):
            with self.subTest(arg=arg), self.assertRaises(ValueError): t.bootargs(ARGS+' '+arg, SELECTED)

    def test_prerequisite_requires_matching_complete_physical_return(self):
        normal = dict(system='/normal', profile='/normal', kernel='/kernel', uname='6.6.36', init='/init', boot_files={'Image':{'sha256':'hash'}})
        p = dict(bundle=Path('/bundle'),system=SELECTED,normal=normal)
        recovery = {k: normal[k] for k in ('system','profile','kernel','uname','init')}; recovery.update(services=['active']*3,boot_files={'Image':'hash'},boot_id=BOOT)
        result = dict(schema='mainline-initrd-blkid-v1',status='recovery-verified-diagnostic-passed',candidate_bundle='/bundle',candidate_system=SELECTED,diagnostic={'passed':True,'retrieval':{'complete':True}},reboot_marker_observed=True,normal_recovery=recovery,normal_preflight={'boot_id':NORMAL_BOOT})
        t.validate_prerequisite(result,p)
        for key, bad in [('status','unknown'),('candidate_system','/wrong'),('candidate_bundle','/wrong'),('reboot_marker_observed',False),('diagnostic',{'passed':True}),('normal_recovery',dict(recovery,boot_id=NORMAL_BOOT)),('normal_recovery',dict(recovery,profile='/wrong'))]:
            with self.subTest(key=key), self.assertRaises(ValueError): t.validate_prerequisite(dict(result,**{key:bad}),p)

    def test_invalid_preparation_never_imports_serial(self):
        args = SimpleNamespace(bundle=Path('/bad'),manifest=Path('/bad'),normal_report=Path('/bad'),blkid_result=Path('/bad'))
        with mock.patch.object(t,'prepare',side_effect=ValueError('unsafe')), mock.patch.object(t.rd,'PrivateSession') as serial:
            with self.assertRaises(ValueError): t.run(args)
            serial.assert_not_called()

    def test_private_prerequisite_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'proof'; f.write_text('{}'); f.chmod(0o600)
            self.assertEqual(t.private_input(f),{})
            f.chmod(0o644)
            with self.assertRaises(ValueError): t.private_input(f)
            f.chmod(0o600); link = Path(d)/'link'; link.symlink_to(f)
            with self.assertRaises(ValueError): t.private_input(link)

    def test_prepared_helper_checks_registration_before_reporting(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'bootargs.txt').write_text(ARGS); (p/'init').write_text('fixture')
            with mock.patch.object(t.rd,'prepare_trial',return_value={'bundle':p,'system':str(p),'helper_text':"print('CHECKED')\n"}), mock.patch.object(t,'bootargs',return_value=PREPARED['bootargs']), mock.patch.object(t,'private_input',return_value={}), mock.patch.object(t,'validate_prerequisite'):
                prepared = t.prepare(p,p,p,p)
            marker = p/'marker'; helper = prepared['helper_text'].replace('/nix-path-registration',str(marker))
            self.assertEqual(subprocess.run([sys.executable,'-c',helper],capture_output=True).returncode,0)
            for dangling in (False,True):
                if dangling: marker.symlink_to(p/'absent')
                else: marker.write_text('pending')
                failed = subprocess.run([sys.executable,'-c',helper],capture_output=True)
                self.assertNotEqual(failed.returncode,0); self.assertNotIn(b'CHECKED',failed.stdout)
                marker.unlink()

    def test_run_unknown_never_reboots_and_success_exactly_once(self):
        for fail, recovered in [('journal',True), (None,True), (None,False)]:
            with self.subTest(fail=fail,recovered=recovered), tempfile.TemporaryDirectory() as d:
                args = SimpleNamespace(bundle=Path(d)/'bundle',manifest=Path(d)/'manifest',normal_report=Path(d)/'normal',blkid_result=Path(d)/'prior',log=Path(d)/'uart',result=Path(d)/'result')
                s = Session(); s.fail = fail
                p = dict(PREPARED,bundle=args.bundle,normal={})
                original = t.diagnostic
                with mock.patch.object(t,'prepare',return_value=p), mock.patch.object(t,'boot'), mock.patch.object(t,'diagnostic',side_effect=lambda session,p,n,facts: original(session,p,n,facts,clock=Clock(),token_factory=tokens())), mock.patch.object(t.rd,'LOCK_PATH',str(Path(d)/'lock')), mock.patch.object(t.rd,'PrivateSession',return_value=s), mock.patch.dict(sys.modules,{'serial':SimpleNamespace()}), mock.patch.object(t.system,'wait_prompt',return_value=True), mock.patch.object(t.system,'normal_check',side_effect=[{'boot_id':NORMAL_BOOT},{'boot_id':BOOT}]) as check, mock.patch.object(t.system,'wait_normal',return_value=recovered) as wait:
                    ok = t.run(args)
                self.assertEqual(ok,fail is None and recovered)
                self.assertEqual(sum(b'/bin/reboot -ff' in command for command in s.writes),int(fail is None))
                self.assertEqual(check.call_count,2 if fail is None and recovered else 1)
                self.assertEqual(wait.call_count,int(fail is None))
                saved = json.loads(args.result.read_text()); self.assertEqual(saved['schema'],'mainline-initrd-debug-v1')
                self.assertTrue(s.closed)


if __name__ == '__main__': unittest.main()
