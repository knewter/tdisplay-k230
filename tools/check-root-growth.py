#!/usr/bin/env python3
"""Capture physical root-growth evidence; never resize or select a boot target.

Before capture creates one public root sentinel. All phases inspect actual
mounted devices and the installed growth helper. The host holds the board lock
for upload/capture, and publishes only the structured, credential-free report.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

SENTINEL = Path('/var/lib/k230-root-growth-evidence/sentinel')
BOOT_FILES = ('Image', 'initrd.uimg', 'k230-tdisplay.dtb', 'bootargs.txt',
              'fw_jump_add_uboot_head.bin', 'force_dtb', 'lcd_dtb', 'hdmi_dtb')
PYTHON = '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3'


def run(args, timeout=30, required=True):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if required and p.returncode:
        raise RuntimeError(Path(args[0]).name+' failed (output withheld)')
    return p


def digest(path, offset=0, length=None):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        stream.seek(offset)
        while length is None or length > 0:
            block = stream.read(min(length, 1024*1024) if length is not None else 1024*1024)
            if not block:
                if length:
                    raise RuntimeError('short protected-region read')
                break
            h.update(block)
            if length is not None:
                length -= len(block)
    return h.hexdigest()


def probe(args):
    if os.geteuid() != 0 or not Path('/sys/firmware/devicetree/base/model').is_file():
        raise RuntimeError('requires root on the physical device-tree board')
    model = Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0').decode()
    if 'K230' not in model:
        raise RuntimeError('unexpected physical board')
    guard = json.loads(run([args.helper+'/bin/k230-root-growth']).stdout)
    if guard['status'] != 'checked' or guard['mutation_requested']:
        raise RuntimeError('read-only layout preflight failed')
    layout = guard['layout']
    if args.phase == 'before':
        SENTINEL.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not SENTINEL.exists():
            with SENTINEL.open('x') as stream:
                stream.write('K230 root-growth preservation sentinel '+args.token+'\n')
                stream.flush(); os.fsync(stream.fileno())
    sentinel = digest(SENTINEL)
    fs = os.statvfs('/')
    bootargs = Path('/boot/bootargs.txt').read_text()
    selected = re.findall(r'init=(/nix/store/[^\s]+?)/init(?:\s|$)', bootargs)
    if selected != [args.target_system]:
        raise RuntimeError('bootargs does not select exactly the target system')
    # WPA output is kept in memory; only the completed-state boolean escapes.
    wifi = run(['wpa_cli', '-s', '/run/k230-wifi/wpa_supplicant/client', '-p', '/run/k230-wifi/wpa_supplicant', '-i', 'wlan0', 'status'], required=False).stdout
    interface = json.loads(run(['ip', '-j', '-4', 'addr', 'show', 'dev', 'wlan0']).stdout)
    online = run(['curl', '--interface', 'wlan0', '-fsS', '--connect-timeout', '10',
                  '--max-time', '20', '-o', '/dev/null', '-w', '%{http_code}',
                  'https://example.com/'], required=False, timeout=25)
    credentials = Path('/var/lib/k230/wifi/wpa_supplicant.conf').stat()
    unit = dict(line.split('=', 1) for line in run(['systemctl', 'show',
        'k230-root-growth.service', '-p', 'ActiveState', '-p', 'SubState',
        '-p', 'Result', '-p', 'ExecMainStatus'], required=False).stdout.splitlines() if '=' in line)
    journal = run(['journalctl', '-b', '-u', 'k230-root-growth.service',
                   '--no-pager', '-o', 'cat'], required=False).stdout
    growth = []
    for line in journal.splitlines():
        if line.startswith('{'):
            item = json.loads(line)
            if set(item) <= {'status', 'layout', 'filesystem_bytes_before', 'mutation_requested',
                             'root_sectors_after', 'filesystem_bytes_after'}:
                growth.append(item)
    return {
        'token': args.token, 'phase': args.phase, 'evidence_class': 'physical-board-serial',
        'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model': model, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'current_system': os.path.realpath('/run/current-system'),
        'selected_system': selected[0], 'helper': args.helper, 'guard': guard,
        'filesystem_total_bytes': fs.f_blocks*fs.f_frsize,
        'filesystem_available_bytes': fs.f_bavail*fs.f_frsize,
        'inodes_total': fs.f_files, 'inodes_available': fs.f_favail,
        'protected': {
            'mbr_boot_code_sha256': digest(layout['disk'], 0, 446),
            'firmware_gap_sha256': digest(layout['disk'], 512, 4*1024*1024-512),
            'boot_files_sha256': {name: digest('/boot/'+name) for name in BOOT_FILES},
            'root_sentinel_sha256': sentinel,
        },
        'shell_active': run(['systemctl', 'is-active', '--quiet', 'shell']).returncode == 0,
        'seatd_active': run(['systemctl', 'is-active', '--quiet', 'seatd']).returncode == 0,
        'wifi_associated': 'wpa_state=COMPLETED' in wifi.splitlines(),
        'wifi_ipv4': any(item.get('addr_info') for item in interface),
        'wifi_https_200': online.returncode == 0 and online.stdout == '200',
        'credentials_root_0600': credentials.st_uid == 0 and credentials.st_gid == 0
                                 and credentials.st_mode & 0o777 == 0o600,
        'growth_unit': unit, 'growth_journal': growth,
        'limits': ['No real-finger interaction or camera observation.',
                   'Selected boot files and firmware regions checked; no full-image readback.'],
    }


def verify(report, phase, before=None):
    def need(ok, why):
        if not ok:
            raise RuntimeError(why)
    for key in ('shell_active', 'seatd_active', 'wifi_associated', 'wifi_ipv4',
                'wifi_https_200', 'credentials_root_0600'):
        need(report[key], key+' failed')
    if phase == 'before':
        need(report['guard']['layout']['root_sectors']*512 < 3*1024**3,
             'starting root is not compact')
        return
    need(before['status'] == 'PASS', 'prior report did not pass')
    need(before['phase'] == ('before' if phase == 'after' else 'after'), 'wrong prior phase')
    need(report['boot_id'] != before['boot_id'], 'no new physical boot')
    need(report['selected_system'] == before['selected_system'], 'selected system changed')
    need(report['current_system'] == report['selected_system'], 'target system did not boot')
    need(report['protected'] == before['protected'], 'protected data changed')
    old, new = before['guard']['layout'], report['guard']['layout']
    need({k:v for k,v in old.items() if k != 'root_sectors'} ==
         {k:v for k,v in new.items() if k != 'root_sectors'}, 'root identity changed')
    need(report['growth_unit'] == {'ActiveState': 'active', 'SubState': 'exited',
                                   'Result': 'success', 'ExecMainStatus': '0'}, 'boot service failed')
    need(len(report['growth_journal']) == 1, 'missing or ambiguous boot growth report')
    growth = report['growth_journal'][0]
    need(growth['mutation_requested'] is True, 'service did not invoke growth')
    need(growth['layout'] == old, 'service starting layout differs from prior capture')
    need(growth['root_sectors_after'] == new['root_sectors'], 'service final layout differs')
    need(growth['filesystem_bytes_before'] == before['guard']['filesystem_bytes_before'],
         'service starting filesystem differs')
    need(growth['filesystem_bytes_after'] == report['guard']['filesystem_bytes_before'],
         'service final filesystem differs')
    need(0 <= new['disk_bytes']-(262144+new['root_sectors'])*512 <= 33*512,
         'root did not reach card tail')
    if phase == 'after':
        need(growth['status'] == 'grown', 'first boot did not grow')
        need(report['filesystem_available_bytes'] > before['filesystem_available_bytes']+1024**3,
             'usable capacity did not increase')
    else:
        need(growth['status'] == 'no-change' and new == old, 'repeat changed layout')
        need(report['guard']['filesystem_bytes_before'] == before['guard']['filesystem_bytes_before'],
             'repeat changed filesystem size')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board', action='store_true')
    p.add_argument('--phase', choices=('before', 'after', 'repeat'), required=True)
    p.add_argument('--before', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--helper', required=True)
    p.add_argument('--target-system', required=True)
    p.add_argument('--recovery-image', type=Path)
    p.add_argument('--recovery-sha256')
    p.add_argument('--probe', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--token', help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.probe:
        print('K230_GROWTH_BOARD '+json.dumps(probe(args), sort_keys=True), flush=True)
        return
    if not args.board or not args.output:
        p.error('requires --board and --output')
    if args.output.exists():
        p.error('output already exists; preserve earlier evidence')
    if args.phase == 'before':
        if not args.recovery_image or not args.recovery_sha256:
            p.error('before requires a preserved recovery image and its known SHA256')
        if digest(args.recovery_image) != args.recovery_sha256:
            raise RuntimeError('recovery image hash mismatch')
        recovery = {'image': str(args.recovery_image.resolve()),
                    'sha256': args.recovery_sha256, 'bytes': args.recovery_image.stat().st_size}
        prior = None
    else:
        if not args.before:
            p.error('after/repeat requires --before')
        prior = json.loads(args.before.read_text())
        recovery = prior['recovery']
    token = uuid.uuid4().hex
    root = Path(__file__).resolve().parent
    remote = '/run/check-root-growth-'+token+'.py'
    command = shlex.join([PYTHON, remote, '--probe', '--phase', args.phase, '--token', token,
                          '--helper', args.helper, '--target-system', args.target_system])
    with open('/tmp/k230-board.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run([sys.executable, str(root/'push-file.py'), '--src', str(Path(__file__).resolve()),
             '--dest', remote], timeout=90)
        capture = run([sys.executable, str(root/'console.py'), '--wait=45', command], timeout=70).stdout
    # Anchor the actual emitted line, never match echoed command text.
    lines = [line for line in capture.splitlines() if line.startswith('K230_GROWTH_BOARD ')]
    if len(lines) != 1:
        raise RuntimeError('missing/ambiguous serial report (raw output withheld)')
    report = json.loads(lines[0].split(' ', 1)[1])
    if report['token'] != token or report['phase'] != args.phase:
        raise RuntimeError('stale serial report')
    report.update(recovery=recovery, status='FAIL',
                  checker_sha256=digest(__file__),
                  capture_sha256=hashlib.sha256(capture.encode()).hexdigest())
    try:
        verify(report, args.phase, prior)
        report['status'] = 'PASS'
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        args.output.with_suffix('.serial.log').write_text(lines[0]+'\n')
    print(args.phase+' physical-board check PASS: '+str(args.output))


if __name__ == '__main__':
    main()
