#!/usr/bin/env python3
"""Boot staged HDMI artifacts once; caller must hold /tmp/k230-board.lock.

Normal /boot files and the system profile are checked before reboot. Trial
arguments are imported only into volatile U-Boot environment; no saveenv or
persistent boot-file replacement is performed. Raw logs may contain private
network state: review and extract evidence before committing them.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import time
import uuid


def clean(data):
    return re.sub(rb'\x1b\[[0-9;?]*[A-Za-z]', b'', data).replace(b'\r', b'')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--stage-dir', required=True)
    ap.add_argument('--private-log', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    if not re.fullmatch(r'/var/lib/k230/hdmi-responsive-trial-[a-f0-9]+', args.stage_dir):
        ap.error('invalid trial directory')
    if args.private_log.exists() or args.report.exists():
        ap.error('use new paths to preserve previous observations')
    m = json.loads(args.manifest.read_text())
    spec = importlib.util.spec_from_file_location('ums', Path(__file__).with_name('ums-session.py'))
    ums = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ums)

    class TrialSession(ums.Session):
        def send_line(self, text, kill=True):
            if kill:
                self.port.write(ums.KILL_LINE)
                self.port.flush()
                time.sleep(.05)
            self.note('sending: ' + text)
            self.buf = b''
            # A second LF repeats U-Boot's last command. Send just one CR.
            self.port.write(text.encode() + b'\r')
            self.port.flush()

    report = {
        'status': 'FAIL', 'source_revision': m['source_revision'],
        'system': m['system'], 'loads': [],
        'persistent_boot_selection_changed': False,
        'physical_touch_acceptance': False,
        'controller_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    session = TrialSession('/dev/ttyACM0', 115200, str(args.private_log))
    in_uboot = False
    try:
        token = 'K230_HDMI_READY_' + uuid.uuid4().hex
        stage = args.stage_dir
        command = (
            'cd ' + stage + ' && sha256sum -c SHA256SUMS > preflight-check.log'
            ' && sha256sum -c panel-boot-before.sha256 >> preflight-check.log'
            ' && test "$(readlink /run/current-system)" = "$(cat normal-system.txt)"'
            ' && test "$(readlink /nix/var/nix/profiles/system)" = "$(cat normal-profile.txt)"'
            ' && test -x ' + m['system'] + '/init && sync && echo ' + token
        )
        session.send_line(command)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            session.pump()
            if re.search(rb'^' + token.encode() + rb'$', clean(session.buf), re.M):
                break
        else:
            raise RuntimeError('Linux staging preflight did not pass; no reboot attempted')
        report['linux_preflight_passed'] = True
        session.send_line('systemctl reboot')
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            session.port.write(b' \x08')
            session.port.flush()
            session.pump()
            if b'K230#' in session.buf:
                break
            time.sleep(.1)
        else:
            raise RuntimeError('U-Boot prompt not captured; no trial load attempted')
        in_uboot = True
        session.port.write(ums.KILL_LINE + b'\r')
        session.port.flush()
        time.sleep(.3)
        session.pump()
        plan = [
            ('bootargs.txt', '0x7000000'), ('Image', '0x200000'),
            ('k230-tdisplay-hdmi.dtb', '0x8400000'), ('initrd.uimg', '0x9000000'),
        ]
        for name, address in plan:
            info = m['files'][name]
            out = session.cmd_output('ext4load mmc 1:2 ' + address + ' ' + stage + '/' + name, 60)
            counts = re.findall(rb'^([0-9]+) bytes read(?: in [^\n]*)?$', clean(out or b''), re.M)
            if counts != [str(info['bytes']).encode()]:
                raise RuntimeError('unexpected load size: ' + name)
            out = session.cmd_output('crc32 ' + address + ' ' + hex(info['bytes']), 30)
            crcs = re.findall(rb'^[Cc][Rr][Cc]32 for [^\n]+ ==> ([0-9a-fA-F]{8})$', clean(out or b''), re.M)
            if [v.decode().lower() for v in crcs] != [info['crc32']]:
                raise RuntimeError('memory CRC mismatch: ' + name)
            report['loads'].append({'file': name, **info})
        out = session.cmd_output('ext4load mmc 1:1 0x8000000 /fw_jump_add_uboot_head.bin', 30)
        if not re.search(rb'^270808 bytes read(?: in [^\n]*)?$', clean(out or b''), re.M):
            raise RuntimeError('normal firmware load failed')
        out = session.cmd_output('env import -t 0x7000000 ' + hex(m['files']['bootargs.txt']['bytes']) + ' && echo K230_HDMI_ARGS_IMPORTED', 10)
        if not re.search(rb'^K230_HDMI_ARGS_IMPORTED$', clean(out or b''), re.M):
            raise RuntimeError('volatile boot argument import failed')
        session.send_line('bootm 0x8000000 0x9000000 0x8400000')
        in_uboot = False
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            session.pump()
            if b'nixos login:' in session.buf or b'root@nixos' in session.buf:
                report['status'] = 'BOOTED'
                break
        else:
            raise RuntimeError('Linux login not observed before deadline')
    except Exception as exc:
        report['error'] = str(exc)
        if in_uboot:
            session.send_line('reset')
            report['normal_boot_reset_requested'] = True
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        session.port.close()
        session.log.close()


if __name__ == '__main__':
    main()
