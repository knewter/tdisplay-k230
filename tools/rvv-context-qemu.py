#!/usr/bin/env python3
"""Validate the vector probe in full Linux guests, including a corrupt control.

The probe is PID 1 in a minimal initramfs. Its report precedes an expected
"Attempted to kill init" panic. No image, compositor or board claim is made.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import stat
import subprocess
import time


def initrd(package, target):
    closure = subprocess.check_output(['nix-store', '-qR', str(package)], text=True).splitlines()
    with gzip.open(target, 'wb', compresslevel=1) as out:
        inode = 0

        def add(name, mode, data=b'', major=0, minor=0):
            nonlocal inode
            inode += 1
            name = name.encode() + b'\0'
            fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(name), 0]
            header = b'070701' + ''.join(f'{v:08x}' for v in fields).encode()
            out.write(header + name + b'\0' * ((-len(header)-len(name)) % 4))
            out.write(data + b'\0' * ((-len(data)) % 4))

        for name in ('dev', 'nix', 'nix/store'):
            add(name, stat.S_IFDIR | 0o755)
        add('dev/console', stat.S_IFCHR | 0o600, major=5, minor=1)
        add('init', stat.S_IFLNK | 0o777, str(package/'bin/k230-rvv-context-probe').encode())
        paths = set()
        for root in closure:
            paths.add(Path(root))
            for directory, dirs, files in os.walk(root):
                paths.update(Path(directory)/name for name in dirs+files)
        for path in sorted(paths):
            info = path.lstat()
            if path.is_symlink():
                data = os.readlink(path).encode()
            elif path.is_file():
                data = path.read_bytes()
            else:
                data = b''
            add(str(path).lstrip('/'), info.st_mode, data)
        add('TRAILER!!!', 0)


def guest(args, name, archive, cpu):
    command = [args.qemu, '-machine', 'virt', '-cpu', cpu, '-m', '1G', '-nographic',
               '-nic', 'none', '-no-reboot', '-kernel', str(args.kernel/'Image'),
               '-initrd', str(archive), '-append',
               'console=ttyS0 earlycon=sbi rdinit=/init panic=-1']
    log = args.output/(name+'.log')
    report = None
    with log.open('w') as out:
        process = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic()+args.timeout
            while time.monotonic() < deadline:
                for line in log.read_text().splitlines():
                    if line.startswith('{"status":'):
                        report = json.loads(line)
                        break
                if report is not None or process.poll() is not None:
                    break
                time.sleep(.2)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return {'case': name, 'command': command, 'report': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--corrupt-package', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True, help='realized generic RISC-V Linux output')
    parser.add_argument('--output', type=Path, required=True, help='new or empty evidence directory')
    parser.add_argument('--qemu', default='qemu-system-riscv64')
    parser.add_argument('--timeout', type=int, default=45)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error('--timeout must be 1..300 seconds')
    for name in ('package', 'corrupt_package', 'kernel', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    for package in (args.package, args.corrupt_package):
        if not (package/'bin/k230-rvv-context-probe').is_file():
            parser.error('missing probe executable: '+str(package))
    if not (args.kernel/'Image').is_file():
        parser.error('missing realized guest kernel Image')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('--output must be new or empty')
    args.output.mkdir(parents=True, exist_ok=True)
    args.output.chmod(0o700)
    normal, corrupt = (args.output/(name+'.cpio.gz') for name in ('normal', 'corrupt'))
    initrd(args.package, normal)
    initrd(args.corrupt_package, corrupt)
    rows = []
    for name, archive, cpu in (
        ('no-vector', normal, 'rv64,v=false'),
        ('vector-128', normal, 'rv64,v=true,vlen=128,elen=64'),
        ('vector-256', normal, 'rv64,v=true,vlen=256,elen=64'),
        ('corrupt-vector', corrupt, 'rv64,v=true,vlen=128,elen=64'),
    ):
        row = guest(args, name, archive, cpu)
        r = row['report'] or {}
        if name == 'no-vector':
            passed = r.get('status') == 'SKIP' and not (r.get('features', 4) & 4)
        elif name == 'corrupt-vector':
            passed = (r.get('status') == 'FAIL' and r.get('parent_result') == 2
                      and r.get('child_wait_status') == 2 << 8)
        else:
            passed = (r.get('status') == 'PASS' and r.get('parent_iterations') == 2000
                      and r.get('parent_signals', 0) >= 2000
                      and r.get('parent_involuntary_switches', 0) > 0
                      and r.get('child_wait_status') == 0)
        row['check'] = 'PASS' if passed else 'FAIL'
        rows.append(row)
        print(name, row['check'], r, flush=True)
    result = {'status': 'PASS' if all(r['check'] == 'PASS' for r in rows) else 'FAIL',
              'evidence_class': 'full-system-qemu-vector-context',
              'package': str(args.package), 'corrupt_package': str(args.corrupt_package),
              'kernel': str(args.kernel),
              'qemu_version': subprocess.check_output([args.qemu, '--version'], text=True).splitlines()[0],
              'cases': rows,
              'limits': ['Generic Linux guest only; no board or vendor-kernel claim.',
                         'Probe PID 1 exits after its report; the ensuing guest panic is expected.',
                         'Representative vector data/control state, not exhaustive ISA coverage.']}
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
