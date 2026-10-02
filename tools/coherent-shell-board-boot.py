#!/usr/bin/env python3
"""Temporarily boot an inspected, staged candidate or its protected baseline.

Requires tools/coherent-shell-board-stage.py prepare on the reserved board and
its captured state JSON. Persistent installation requires a separate operator qualification file;
--install then observes untouched autoboot. --recover-baseline works at U-Boot.
No physical-glass acceptance is inferred from serial. Raw console output is saved privately, never printed.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import time
import uuid

PYTHON = '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
    return loaded


def validate_state(state, candidate):
    if state['candidate'] != candidate:
        raise ValueError('staged candidate differs from inspected host bundle')
    if not re.fullmatch(r'/var/lib/k230/coherent-boot/[a-z0-9-]+', state['stage']):
        raise ValueError('invalid immutable staging path')
    if not re.fullmatch(r'/nix/store/[a-z0-9]{32}-nixos-system-[A-Za-z0-9._+-]+', candidate['system']):
        raise ValueError('invalid candidate system path')
    candidate_files = dict(candidate['boot_files'])
    candidate_files['fw_jump_add_uboot_head.bin'] = state['normal_files']['fw_jump_add_uboot_head.bin']
    for name in ('Image', 'initrd.uimg', 'bootargs.txt', 'k230-tdisplay.dtb', 'fw_jump_add_uboot_head.bin'):
        for files in (state['normal_files'], candidate_files):
            item = files[name]
            limit = {'Image': 64*1024**2, 'initrd.uimg': 64*1024**2,
                     'bootargs.txt': 4096, 'k230-tdisplay.dtb': 1024**2,
                     'fw_jump_add_uboot_head.bin': 4*1024**2}[name]
            if type(item['bytes']) is not int or not 0 < item['bytes'] < limit:
                raise ValueError('invalid load size: ' + name)
            if not re.fullmatch('[0-9a-f]{8}', item['crc32']) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                raise ValueError('invalid loaded artifact checksum: ' + name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--baseline', action='store_true')
    modes.add_argument('--install', action='store_true')
    modes.add_argument('--recover-baseline', action='store_true')
    p.add_argument('--qualification', type=Path)
    args = p.parse_args()
    os.umask(0o077)
    candidate = module('inspect_boot', 'coherent-shell-boot-inspect.py').inspect(args.candidate)
    state = json.loads(args.state.read_text()); validate_state(state, candidate)
    if args.install:
        if args.qualification is None:
            p.error('--install requires --qualification')
        module('installer', 'coherent-shell-board-install.py').validate_qualification(json.loads(args.qualification.read_text()), candidate)
    args.output.mkdir(parents=True, exist_ok=False)
    private = Path.home() / 'tmp' / ('k230-coherent-boot-' + uuid.uuid4().hex + '.private.log')
    ums = module('ums', 'ums-session.py'); protocol = module('rvv_protocol', 'rvv-board-boot.py')
    class Session(ums.Session):
        def note(self, text):
            self.log.write((self.stamp() + '--- ' + text + ' ---\n').encode())
        def pump(self):
            chunk = self.port.read(65536)
            if chunk:
                self.log.write(chunk); self.buf = (self.buf + chunk)[-262144:]
            return chunk
        def send_line(self, text, kill=True):
            if kill:
                self.port.write(ums.KILL_LINE); self.port.flush(); time.sleep(.05)
            self.note('sending: ' + text); self.buf = b''
            self.port.write(text.encode() + b'\r'); self.port.flush()
    report = dict(status='FAIL', mode='install-and-ordinary-boot' if args.install else ('recovery-baseline' if args.recover_baseline else ('baseline' if args.baseline else 'candidate')),
                  candidate=candidate, loads=[], persistent_boot_selection_changed=False,
                  physical_navigation_verified=False,
                  controller_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    in_uboot = False
    with open('/tmp/k230-board.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        s = Session('/dev/ttyACM0', 115200, str(private))
        try:
            token = uuid.uuid4().hex
            if args.recover_baseline:
                # No Linux preflight is possible after interrupted boot-file
                # replacement. Root backup loads are still checked by CRC.
                s.send_line('echo K230_COHERENT_RECOVERY')
                if not s.wait_for(ums.PROMPT, 30):
                    raise RuntimeError('recovery requires an already stopped U-Boot prompt')
                in_uboot = True
            else:
                s.port.write(b'\x03\r'); s.port.flush(); time.sleep(.4); s.pump()
                s.send_line(shlex.join([PYTHON, '-I', state['stage'] + '/stage.py', 'check', state['stage'], '--token', token]))
                if not s.wait_for(('\r\nK230_COHERENT_READY ' + token + '\r\n').encode(), 60):
                    raise RuntimeError('staged candidate/registered closure/rollback preflight failed')
                if args.install:
                    s.send_line(shlex.join([PYTHON, '-I', state['stage'] + '/install.py', 'install', state['stage'], '--qualification', state['stage'] + '/qualified.json']) + '; printf "\\nK230_COHERENT_INSTALL_END\\n"')
                    if not s.wait_for(b'\r\nK230_COHERENT_INSTALL_END\r\n', 180):
                        raise RuntimeError('installation deadline exceeded; inspect journal before reboot')
                    records = re.findall(rb'^K230_COHERENT_INSTALL (.+)$', protocol.uart_text(s.buf), re.M)
                    if len(records) != 1:
                        raise RuntimeError('installation report absent; inspect journal before reboot')
                    report['installation'] = json.loads(records[0])
                    if report['installation'].get('result') != 'PASS':
                        raise RuntimeError('installation did not pass')
                    report['persistent_boot_selection_changed'] = True
                s.send_line('reboot')
                if not args.install:
                    end = time.monotonic() + 35
                    while time.monotonic() < end:
                        s.pump()
                        if b'Hit any key to stop autoboot' in s.buf:
                            s.port.write(b' '); s.port.flush()
                        if ums.PROMPT in s.buf:
                            break
                    else:
                        raise RuntimeError('could not catch U-Boot; no load attempted')
                    in_uboot = True
            if not args.install:
                env = s.cmd_output('printenv bootcmd blinux preboot', 30)
                if env is None:
                    raise RuntimeError('could not inspect boot environment')
                report['boot_environment_sha256'] = hashlib.sha256(env).hexdigest()
                files = state['normal_files'] if (args.baseline or args.recover_baseline) else candidate['boot_files']
                base = state['stage'] + ('/backup' if (args.baseline or args.recover_baseline) else '')
                for name, address in [('bootargs.txt', '0x7000000'), ('fw_jump_add_uboot_head.bin', '0x8000000'),
                                      ('Image', '0x200000'), ('k230-tdisplay.dtb', '0x8400000'), ('initrd.uimg', '0x9000000')]:
                    expected = state['normal_files'][name] if name == 'fw_jump_add_uboot_head.bin' else files[name]
                    path = state['stage'] + '/backup/' + name if name == 'fw_jump_add_uboot_head.bin' else base + '/' + name
                    protocol.verify_load(s.cmd_output('ext4load mmc 1:2 ' + address + ' ' + path, 90), expected['bytes'])
                    protocol.verify_crc(s.cmd_output('crc32 ' + address + ' ' + hex(expected['bytes']), 40), expected['crc32'])
                    report['loads'].append(dict(file=name, address=address, **expected))
                reply = s.cmd_output('env import -t 0x7000000 ' + hex(files['bootargs.txt']['bytes']) + ' && echo K230_COHERENT_ARGS_IMPORTED')
                if reply is None or not re.search(rb'^K230_COHERENT_ARGS_IMPORTED\r?$', reply, re.M):
                    raise RuntimeError('volatile boot arguments not imported')
                s.send_line('bootm 0x8000000 0x9000000 0x8400000'); in_uboot = False
            # Install mode sends no key, env import, or boot command during
            # autoboot; only reads console until Linux has started.
            if not s.wait_for(b'nixos login:', 180):
                raise RuntimeError('Linux login deadline exceeded; candidate remains unaccepted')
            s.wait_for(b'root@nixos', 30)
            code = 'from pathlib import Path;import json,subprocess;print("K230_COHERENT_IDENTITY "+json.dumps(dict(system=str(Path("/run/current-system").resolve()),profile=str(Path("/nix/var/nix/profiles/system").resolve()),kernel=str(Path("/run/booted-system/kernel").resolve()),cmdline=Path("/proc/cmdline").read_text().strip(),boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),services=subprocess.run(["systemctl","is-active","shell","shell-ui","theme-helper"],capture_output=True,text=True).stdout.splitlines())))'
            s.send_line(shlex.join([PYTHON, '-c', code]) + '; printf "\\nK230_COHERENT_POST_END\\n"')
            if not s.wait_for(b'\r\nK230_COHERENT_POST_END\r\n', 90):
                raise RuntimeError('postboot identity deadline exceeded')
            lines = re.findall(rb'^K230_COHERENT_IDENTITY (.+)$', protocol.uart_text(s.buf), re.M)
            if len(lines) != 1:
                raise RuntimeError('postboot identity absent or ambiguous')
            report['observed'] = json.loads(lines[0])
            expected_profile = candidate['system'] if args.install else state['normal_profile']
            if not args.recover_baseline and report['observed']['profile'] != expected_profile:
                raise RuntimeError('manual boot changed the protected profile')
            if not (args.baseline or args.recover_baseline):
                observed = report['observed']
                init = [v for v in observed['cmdline'].split() if v.startswith('init=')]
                if observed['system'] != candidate['system'] or observed['kernel'] != candidate['kernel'] or init != ['init=' + candidate['system'] + '/init']:
                    raise RuntimeError('candidate boot identities differ from inspected bundle')
                if observed['services'] != ['active'] * 3:
                    raise RuntimeError('candidate shell services are not active')
            report.update(status='PASS', serial_boot_observed=True, ordinary_autoboot_observed=args.install)
        except BaseException as error:
            report['error'] = str(error)
            if in_uboot or ums.PROMPT in s.buf[-1024:]:
                s.send_line('reset'); report['normal_recovery_login_observed'] = s.wait_for(b'nixos login:', 180)
            raise
        finally:
            s.port.close(); s.log.close()
            (args.output / 'serial-result.json').write_text(json.dumps(report, indent=2) + '\n')
            (args.output / 'private-log-path.txt').write_text(str(private) + '\n')
    print('Ordinary selected-system boot observed; visible postboot acceptance remains separate.' if args.install else 'Serial boot observed; visible navigation and ordinary autoboot remain separate.')


if __name__ == '__main__':
    main()
