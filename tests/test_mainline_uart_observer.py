"""Native helper semantics and isolated optional-unit wiring; no board or mounts."""
import json
import os
from pathlib import Path
import re
import pty
import termios
import subprocess
import tempfile
import time
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'nix/mainline-uart-observer/observer.c'
NONCE = '0123456789abcdef' * 2
FROM = '11111111-1111-1111-1111-111111111111'
INIT = '/nix/store/' + 'a' * 32 + '-nixos-system-test/init'
CONTROLS = 'fsck.mode=skip systemd.mask=k230-root-growth.service systemd.mask=register-nix-paths.service rd.systemd.unit=basic.target rd.systemd.debug_shell=ttyS0'
CMDLINE = f'console=ttyS0,115200n8 init={INIT} {CONTROLS} k230.uobs.nonce={NONCE} k230.uobs.from={FROM} k230.uobs.init={INIT}'
MOUNTS = 'rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\nsysfs /sys sysfs rw 0 0\ndevtmpfs /dev devtmpfs rw 0 0\ncgroup2 /sys/fs/cgroup cgroup2 rw 0 0\n'
ROOT_UNITS = ('sysroot.mount', 'initrd-find-nixos-closure.service', 'initrd-nixos-activation.service', 'initrd-switch-root.target', 'initrd-switch-root.service')

HARNESS = r'''
#define _GNU_SOURCE
#include <time.h>
#include <stdlib.h>
#include <errno.h>
static int clock_calls;
static int injected_clock(clockid_t id, struct timespec *t) {
    const char *fail=getenv("FAIL_CLOCK_AT");
    if(fail && ++clock_calls>=atoi(fail)) {errno=EIO;return -1;}
    return clock_gettime(id,t);
}
#define clock_gettime injected_clock
#define WINDOW_MS 10
#define main production_main
#include "OBSERVER_SOURCE"
#undef main
static int mock_snapshot(struct sample *s) {
    if (getenv("FAIL_SNAPSHOT")) return -1;
    memset(s, 0, sizeof *s); s->term.c_cflag=CREAD|CLOCAL;
    cfsetispeed(&s->term, B115200); cfsetospeed(&s->term, B115200);
    s->count.rx=17; s->irq=23; s->irq_available=1; s->irq_total=8;
    strcpy(s->runtime,"active"); return 0;
}
static int mock_guard(struct context *c, int renewed) {
    (void)c; return renewed && !getenv("FAIL_GUARD") ? 0 : -1;
}
static int mock_reboot(void) {
    const char *path=getenv("REBOOT_FILE");
    if (!path) return -1;
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);
    if (fd<0) return -1;
    if(write(fd,"one -ff",7)!=7) {close(fd);return -1;}
    close(fd);return 0;
}
static int child_operation(void *arg, void *out) {
    const char *s=arg;
    if (!strcmp(s,"block")) {sleep(5);return -1;}
    if (!strcmp(s,"exit")) _exit(1);
    if (!strcmp(s,"fail")) return -1;
    *(int*)out=42;return 0;
}
int main(int argc,char **argv) {
    if(argc<2)return 2;
    char text[TEXT_MAX]; size_t used=0;
    if(strncmp(argv[1],"capture",7)) {used=fread(text,1,sizeof text-1,stdin);}
    text[used]=0;
    if(!strcmp(argv[1],"context")) {struct context c={0};return parse_context(text,&c)?1:0;}
    if(!strcmp(argv[1],"mounts"))return mount_guard(text)?1:0;
    if(!strcmp(argv[1],"ppid"))return ppid_from(text,1)?1:0;
    if(!strcmp(argv[1],"uid"))return uid_from(text)?1:0;
    if(!strcmp(argv[1],"units"))return unit_guard(text,123,argc>2?62:1)?1:0;
    if(!strcmp(argv[1],"irq")) {uint64_t total=0;if(irq_count(text,23,&total))return 1;printf("%"PRIu64,total);return 0;}
    if(!strcmp(argv[1],"frame"))return emit(STDOUT_FILENO,"0123456789abcdef0123456789abcdef",0,"ready",text)?1:0;
    if(!strcmp(argv[1],"capture") || !strcmp(argv[1],"capturestdin")) {char out[128];char *a[]={"/bin/sh","-c",argv[2],NULL};int r=capture(a,out,sizeof out);if(!r)printf("%s",out);
        if(!r && !strcmp(argv[1],"capturestdin")) {char b[32];ssize_t n=read(STDIN_FILENO,b,sizeof b);if(n>0)fwrite(b,1,(size_t)n,stdout);}
        return r?1:0;}
    if(!strcmp(argv[1],"wait"))return wait_ms(300)?1:0;
    if(!strcmp(argv[1],"bounded")) {int out=0;if(bounded(child_operation,argv[2],&out,sizeof out,100))return 1;printf("%d",out);return 0;}
    if(!strcmp(argv[1],"observer")) {
        struct context c={0};strcpy(c.nonce,"0123456789abcdef0123456789abcdef");
        strcpy(c.boot,"22222222-2222-2222-2222-222222222222");c.main_pid=getppid();
        struct sample s;if(mock_snapshot(&s)) {memset(&s,0,sizeof s);s.irq=23;strcpy(s.runtime,"active");}
        const struct observer_ops ops={mock_snapshot,mock_guard,mock_reboot};
        (void)observer_with(STDOUT_FILENO,c,s,&ops);return 0;
    }
    if(!strcmp(argv[1],"payload")) {
        struct sample s={0};strcpy(s.runtime,"suspended");s.irq=23;
        if(argc>2){memset(&s.count,0xff,sizeof s.count);s.irq_total=UINT64_MAX;}
        char out[PAYLOAD_MAX+1];if(sample_payload(&s,"after",out,sizeof out))return 1;
        printf("%s",out);return 0;
    }
    return 2;
}
'''


def unit(unit_id, **changes):
    d = {'Id': unit_id, 'LoadState': 'loaded', 'ActiveState': 'active' if unit_id == 'debug-shell.service' else 'inactive', 'SubState': 'running' if unit_id == 'debug-shell.service' else 'dead', 'Job': ''}
    if unit_id == 'debug-shell.service':
        d.update(ExecMainPID='123', TTYPath='/dev/ttyS0')
    d.update(changes)
    return '\n'.join(f'{k}={v}' for k, v in d.items()) + '\n'


def frames(raw):
    result = []
    for line in raw.split(b'<6>\n')[1:]:
        m = re.fullmatch(rb'K230_UOBS_V1 ([0-9a-f]{32}) ([0-9]+) ([a-z]+) ([0-9]+) ([0-9a-f]{8}) ([0-9a-f]*)\n', line)
        if not m:
            raise AssertionError('incomplete/native malformed frame')
        nonce, seq, stage, length, checksum, encoded = m.groups()
        body = bytes.fromhex(encoded.decode())
        assert nonce.decode() == NONCE
        assert len(body) == int(length) <= 384
        assert zlib.crc32(body) == int(checksum, 16)
        assert len(line) + 4 < 900
        fields = dict(x.split('=', 1) for x in body.decode().splitlines())
        result.append((int(seq), stage.decode(), fields))
    return result


class HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.tmp.name)
        harness = cls.directory / 'harness.c'
        harness.write_text(HARNESS.replace('OBSERVER_SOURCE', str(SOURCE)))
        cls.exe = cls.directory / 'harness'
        cls.production = cls.directory / 'production'
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(harness), '-o', str(cls.exe)], check=True)
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', str(SOURCE), '-o', str(cls.production)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_helper(self, mode, text='', *args, env=None):
        return subprocess.run([str(self.exe), mode, *args], input=text.encode(), capture_output=True, timeout=6, env={**os.environ, **(env or {})})

    def test_exact_context_and_duplicate_each_identity(self):
        self.assertEqual(self.run_helper('context', CMDLINE).returncode, 0)
        for token in (f'k230.uobs.nonce={NONCE}', f'k230.uobs.from={FROM}', f'k230.uobs.init={INIT}', f'init={INIT}'):
            with self.subTest(token=token):
                self.assertNotEqual(self.run_helper('context', CMDLINE+' '+token).returncode, 0)

    def test_missing_unsafe_mismatched_context_and_controls(self):
        bad = [CMDLINE.replace(f'k230.uobs.from={FROM}', ''), CMDLINE.replace(NONCE, NONCE.upper()), CMDLINE.replace('k230.uobs.init='+INIT, 'k230.uobs.init=/nix/store/'+ 'b'*32+'-other/init'), CMDLINE+' rdinit=/bin/sh', CMDLINE+' clk_ignore_unused', CMDLINE+' rd.systemd.unit=initrd.target', CMDLINE+' k230.uobs.other=1', CMDLINE+' systemd.mask=other.service', CMDLINE+' rd.systemd.default_debug_tty=ttyS1', CMDLINE+' rd.udev.log_level=debug', CMDLINE+' udev.log_level=debug', CMDLINE+' systemd.break=pre-udev', CMDLINE.replace('fsck.mode=skip','fsck.mode=force'), CMDLINE.replace('rd.systemd.debug_shell=ttyS0','rd.systemd.debug_shell=ttyS1')]
        for value in bad:
            with self.subTest(value=value):
                self.assertNotEqual(self.run_helper('context', value).returncode, 0)

    def test_mount_table_with_nonmatching_last_entry(self):
        self.assertEqual(self.run_helper('mounts', MOUNTS+'proc /other proc rw 0 0\n').returncode, 0)
        for text in (MOUNTS.replace('proc /proc proc rw 0 0\n',''), MOUNTS+'proc /proc proc rw 0 0\n', MOUNTS.replace('cgroup2 /sys/fs/cgroup cgroup2','none /sys/fs/cgroup tmpfs'), MOUNTS+'root /sysroot ext4 ro 0 0\n', MOUNTS+'root /sysroot/nix ext4 ro 0 0\n', MOUNTS+'root /sysroot\\040hidden ext4 ro 0 0\n'):
            self.assertNotEqual(self.run_helper('mounts', text).returncode, 0)

    def test_actual_outer_ppid_field(self):
        self.assertEqual(self.run_helper('ppid', 'Name:\tsh\nPPid:\t1\n').returncode, 0)
        for body in ('PPid:\t9\n', 'PPid:\t1\nPPid:\t1\n', 'PPid:\t1 trailing\n', 'Name:\tsh\n'):
            self.assertNotEqual(self.run_helper('ppid', body).returncode, 0)

    def test_actual_main_shell_uid_status_is_root(self):
        self.assertEqual(self.run_helper('uid', 'Name:\tsh\nUid:\t0 0 0 0\nPPid:\t1\n').returncode, 0)
        for body in ('Uid:\t0 1 0 0\n', 'Uid:\t0 0 0 0\nUid:\t0 0 0 0\n', 'Uid:\t0 0 0 0 extra\n', 'Name:\tsh\n'):
            self.assertNotEqual(self.run_helper('uid', body).returncode, 0)

    def test_unit_property_order_is_irrelevant(self):
        lines=unit('debug-shell.service').splitlines()
        self.assertEqual(self.run_helper('units', '\n'.join(reversed(lines))+'\n').returncode, 0)
        for changes in ({'ExecMainPID':'124'},{'TTYPath':'/dev/console'},{'Job':'7'},{'LoadState':'not-found'},{'SubState':'exited'}):
            self.assertNotEqual(self.run_helper('units', unit('debug-shell.service', **changes)).returncode, 0)

    def test_all_root_chain_units_and_queued_jobs(self):
        report='\n'.join(unit(x) for x in ROOT_UNITS)
        self.assertEqual(self.run_helper('units', report, 'root').returncode, 0)
        for target in ROOT_UNITS:
            failed='\n'.join(unit(x, **({'Job':'7'} if x == target else {})) for x in ROOT_UNITS)
            self.assertIn('Job=7',failed)
            self.assertNotEqual(self.run_helper('units', failed, 'root').returncode, 0)
        self.assertNotEqual(self.run_helper('units', report+'\n'+unit(ROOT_UNITS[0]), 'root').returncode, 0)
        self.assertNotEqual(self.run_helper('units', '\n'.join(unit(x) for x in ROOT_UNITS[:-1]), 'root').returncode, 0)

    def test_targeted_irq_and_duplicate_missing_malformed(self):
        report=' CPU0 CPU1\n 16: 90 91 PLIC uart-other\n 23: 5 7 PLIC ttyS0\n 25: 900 800 other\n'
        self.assertEqual(self.run_helper('irq', report).stdout, b'12')
        for bad in (report.replace(' 23:', ' 24:'), report+' 23: 1 1 duplicate\n', report.replace('5 7','5 bad'), report.replace('5 7','18446744073709551615 1')):
            self.assertNotEqual(self.run_helper('irq',bad).returncode,0)

    def test_complete_frame_crc_newline_and_payload_limit(self):
        for size in (1, 384):
            result=self.run_helper('frame','x'*size)
            self.assertEqual(result.returncode,0)
            self.assertTrue(result.stdout.startswith(b'<6>\nK230_UOBS_V1 '))
            m=re.search(rb' ready ([0-9]+) ([0-9a-f]{8}) ([0-9a-f]+)\n',result.stdout)
            body=bytes.fromhex(m[3].decode())
            self.assertEqual(len(body),int(m[1]));self.assertEqual(zlib.crc32(body),int(m[2],16))
            self.assertLess(len(result.stdout),900)
        over=self.run_helper('frame','x'*385)
        self.assertNotEqual(over.returncode,0);self.assertEqual(over.stdout,b'')

    def test_capture_complete_nonzero_overflow_and_blocked_child(self):
        self.assertEqual(self.run_helper('capture','', 'printf complete').stdout,b'complete')
        for cmd in ('printf partial; exit 4', 'printf "%0128d" 1', 'sleep 5'):
            start=time.monotonic();r=self.run_helper('capture','',cmd)
            self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,b'')
            self.assertLess(time.monotonic()-start,4)

    def test_command_child_gets_eof_without_consuming_parent_pty(self):
        master, slave = pty.openpty()
        try:
            prior = termios.tcgetattr(slave)
            os.write(master, b'parent-receipt\n')
            p = subprocess.Popen([str(self.exe), 'capturestdin', 'read x; printf "child-eof-%s\n" "$?"'], stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate(timeout=2)
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(out, b'child-eof-1\nparent-receipt\n')
            self.assertEqual(termios.tcgetattr(slave), prior)
        finally:
            os.close(master); os.close(slave)

    def test_injected_midloop_clock_failure_returns_unknown(self):
        for mode, args in (('wait',()),('capture',('sleep 5',)),('bounded',('block',))):
            for failure_at in ('1','2','5'):
                start=time.monotonic()
                r=self.run_helper(mode,'',*args,env={'FAIL_CLOCK_AT':failure_at})
                self.assertNotEqual(r.returncode,0)
                self.assertLess(time.monotonic()-start,1)

    def test_bounded_operation_returns_and_unknown_stops(self):
        self.assertEqual(self.run_helper('bounded','', 'ok').stdout,b'42')
        for kind in ('fail','exit','block'):
            start=time.monotonic();r=self.run_helper('bounded','',kind)
            self.assertNotEqual(r.returncode,0);self.assertLess(time.monotonic()-start,1)

    def test_autonomous_observer_without_any_inbound_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            reboot=Path(d)/'reboot'
            r=self.run_helper('observer',env={'REBOOT_FILE':str(reboot)})
            fs=frames(r.stdout)
            self.assertEqual([x[:2] for x in fs],[(0,'ready'),(1,'before'),(2,'after'),(3,'return')])
            self.assertEqual(fs[1][2]['sample'],'before');self.assertEqual(fs[2][2]['sample'],'after')
            self.assertEqual(fs[0][2]['boot_id'],fs[3][2]['boot_id'])
            self.assertEqual(reboot.read_text(),'one -ff')

    def test_snapshot_or_renewed_guard_failure_has_no_reboot(self):
        for failure,seq in (('FAIL_SNAPSHOT',2),('FAIL_GUARD',3)):
            with tempfile.TemporaryDirectory() as d:
                reboot=Path(d)/'reboot'
                r=self.run_helper('observer',env={'REBOOT_FILE':str(reboot),failure:'1'})
                fs=frames(r.stdout)
                self.assertEqual(fs[-1][:2],(seq,'failed'))
                self.assertNotIn('return',[x[1] for x in fs]);self.assertFalse(reboot.exists())

    def test_complete_failed_write_cannot_request_reboot(self):
        # /dev/full is a host-only failed output sink, never a board descriptor.
        with tempfile.TemporaryDirectory() as d, open('/dev/full','wb') as out:
            reboot=Path(d)/'reboot'
            subprocess.run([str(self.exe),'observer'],input=b'',stdout=out,stderr=subprocess.PIPE,env={**os.environ,'REBOOT_FILE':str(reboot)},timeout=2)
            self.assertFalse(reboot.exists())

    def test_production_has_no_test_cli_and_safe_missing_context(self):
        self.assertEqual(subprocess.run([str(self.production),'--test'],capture_output=True).returncode,2)
        # Native host lacks the required cmdline: must fail before /dev/kmsg.
        self.assertEqual(subprocess.run([str(self.production)],capture_output=True).returncode,2)

    def test_opt_in_module_preserves_tty_policy_and_disables_restart(self):
        module=(ROOT/'nix/mainline-uart-observer/module.nix').read_text()
        self.assertIn('overrideStrategy = "asDropin"',module)
        self.assertIn('Restart = lib.mkForce "no"',module)
        self.assertIn('ExecStart = lib.mkForce [ ""',module)
        self.assertNotIn('TTYReset =',module);self.assertNotIn('TTYVHangup =',module)
        self.assertNotIn('wantedBy',module)
        flake=(ROOT/'flake.nix').read_text()
        self.assertIn('k230-mainline-uart-observer = self.nixosConfigurations.k230-mainline-drm-trial.extendModules',flake)
        bundle=(ROOT/'nix/mainline-uart-observer/bundle.nix').read_text()
        self.assertIn('cmp selected.dts base.dts',bundle)
        self.assertIn('cmp $out/Image-mainline-drm',bundle)
        self.assertIn('sha256sum observer.json >> SHA256SUMS',bundle)


if __name__ == '__main__':
    unittest.main()
