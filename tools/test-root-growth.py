#!/usr/bin/env python3
"""Exercise actual root growth on a disposable disk in a full RISC-V guest."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
CASES = {'growth-and-repeat', 'already-full', 'wrong-label', 'later-partition',
         'unsupported-filesystem', 'partition-tool-failure', 'partition-only-retry'}


def archive(package, path, token):
    closure = subprocess.check_output(['nix-store', '-qR', str(package)], text=True).splitlines()
    with gzip.open(path, 'wb', compresslevel=1) as out:
        inode = 0
        def add(name, mode, data=b'', major=0, minor=0):
            nonlocal inode
            inode += 1
            name = name.encode()+b'\0'
            fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(name), 0]
            header = b'070701'+''.join(f'{v:08x}' for v in fields).encode()
            out.write(header+name+b'\0'*((-len(header)-len(name)) % 4))
            out.write(data+b'\0'*((-len(data)) % 4))
        for name in ('dev', 'nix', 'nix/store'): add(name, stat.S_IFDIR | 0o755)
        add('dev/console', stat.S_IFCHR | 0o600, major=5, minor=1)
        add('run-id', stat.S_IFREG | 0o444, token.encode())
        add('init', stat.S_IFLNK | 0o777, str(package/'bin/k230-root-growth-guest').encode())
        paths = set()
        for root in closure:
            paths.add(Path(root))
            for directory, dirs, files in os.walk(root):
                paths.update(Path(directory)/name for name in dirs+files)
        for p in sorted(paths):
            mode = p.lstat().st_mode
            data = os.readlink(p).encode() if p.is_symlink() else p.read_bytes() if p.is_file() else b''
            add(str(p).lstrip('/'), mode, data)
        add('TRAILER!!!', 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qemu', action='store_true', required=True, help='explicitly select disposable system emulation')
    parser.add_argument('--qemu-binary', default='qemu-system-riscv64')
    parser.add_argument('--package', type=Path)
    parser.add_argument('--kernel', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 1200: parser.error('--timeout must be 1..1200')
    args.output = args.output.resolve()
    if args.output.exists() and any(args.output.iterdir()): parser.error('--output must be new or empty')
    args.output.mkdir(parents=True, exist_ok=True); args.output.chmod(0o700)
    def build(attr):
        return Path(subprocess.check_output(['nix', 'build', '.#'+attr, '--no-link', '--print-out-paths',
                                             '--max-jobs', '1', '--cores', '8'], cwd=ROOT, text=True).strip())
    package = (args.package or build('root-growth-guest')).resolve()
    kernel = (args.kernel or build('qemu-kernel')).resolve()
    if not (package/'bin/k230-root-growth-guest').is_file() or not (kernel/'Image').is_file():
        raise RuntimeError('unrealized test package or kernel')
    token = uuid.uuid4().hex
    initrd = args.output/'guest.cpio.gz'; disk = args.output/'disk.img'
    archive(package, initrd, token)
    # This regular file is the only writable drive passed to QEMU. Never pass
    # a host block device, existing image or user-selected disk to the fixture.
    with disk.open('xb') as stream: stream.truncate(512*1024*1024)
    command = [args.qemu_binary, '-machine', 'virt', '-m', '2G', '-nographic', '-nic', 'none',
               '-no-reboot', '-kernel', str(kernel/'Image'), '-initrd', str(initrd),
               '-drive', f'file={disk},format=raw,if=none,id=testdisk',
               '-device', 'virtio-blk-device,drive=testdisk', '-append',
               'console=ttyS0 earlycon=sbi rdinit=/init panic=-1 k230.root_growth_guest=1']
    manifest = {'command': command, 'package': str(package), 'kernel': str(kernel), 'run_id': token,
                'helper_sha256': hashlib.sha256((ROOT/'tools/root-growth.py').read_bytes()).hexdigest(),
                'qemu_version': subprocess.check_output([args.qemu_binary, '--version'], text=True).splitlines()[0]}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    log = args.output/'serial.log'; report = None
    with log.open('w') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic()+args.timeout
            while time.monotonic() < deadline:
                raw = log.read_text(errors='replace').replace('\r', '')
                # UART output may end midway through a JSON write.
                for line in raw.split('\n')[:-1]:
                    if line.startswith('K230_ROOT_GROWTH_RESULT '): report = json.loads(line.split(' ', 1)[1])
                if report is not None: break
                if process.poll() is not None or 'Kernel panic' in raw:
                    raise RuntimeError('guest ended before a complete growth report; inspect serial.log')
                time.sleep(.25)
        finally:
            if process.poll() is None: process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
    if not report: raise RuntimeError('growth guest timed out without complete evidence')
    assert report['status'] == 'PASS' and report['run_id'] == token and report['machine'] == 'riscv64'
    assert report['helper_sha256'] == manifest['helper_sha256']
    assert len(report['cases']) == len(CASES) and {r['case'] for r in report['cases']} == CASES
    assert all(r['status'] == 'PASS' and r['protected_before'] == r['protected_after'] for r in report['cases'])
    result = {'status': 'PASS', 'manifest': manifest, 'guest': report,
              'limits': ['Guest tests production helper logic against a mounted disposable filesystem.',
                         'No production boot-service integration, physical board or interrupted-write proof.']}
    (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: seven disposable-disk cases, protected boot data and root contents retained', flush=True)


if __name__ == '__main__': main()
