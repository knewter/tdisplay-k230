#!/usr/bin/env python3
"""Grow only the mounted K230 ext4 root in the documented two-partition layout."""
import argparse
import dataclasses
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys

SECTOR = 512
BOOT_START = 8192
BOOT_SECTORS = 229376
ROOT_START = 262144


class Refused(RuntimeError):
    """Preflight has not authorized any mutation."""


class GrowthFailed(RuntimeError):
    """A mutation failed or its postcondition was not established."""


class Runner:
    def run(self, args, *, timeout=10, allowed=(0,)):
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True,
                                   env={**os.environ, 'LC_ALL': 'C'})
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.communicate()
            raise RuntimeError(args[0]+' exceeded its deadline') from None
        if process.returncode not in allowed:
            raise RuntimeError(args[0]+' failed: '+stderr.strip()[:800])
        return process.returncode, stdout, stderr


@dataclasses.dataclass(frozen=True)
class Layout:
    disk: str
    root: str
    boot: str
    disk_bytes: int
    root_sectors: int
    root_uuid: str
    boot_uuid: str
    table_id: str

    def invariant(self):
        return (self.disk, self.root, self.boot, self.disk_bytes,
                self.root_uuid, self.boot_uuid, self.table_id)


def validate_layout(table, disk, root, disk_bytes, root_meta, boot_meta,
                    mounted_type, kernel_root_bytes):
    """Pure policy; callers supply actual device observations, never CLI overrides."""
    def require(ok, why):
        if not ok:
            raise Refused(why)
    require(mounted_type == 'ext4', 'mounted root is not ext4')
    require(table.get('label') == 'dos' and table.get('unit') == 'sectors',
            'partition table is not the supported DOS/sectors layout')
    require(table.get('sectorsize') == SECTOR, 'logical sector size is not 512 bytes')
    require(table.get('device') == disk, 'partition table device differs from mounted-root disk')
    require(isinstance(disk_bytes, int) and ROOT_START*SECTOR < disk_bytes <= (1 << 32)*SECTOR,
            'disk capacity is outside the supported DOS range')
    require(disk_bytes % SECTOR == 0, 'disk capacity is not sector aligned')
    parts = table.get('partitions', [])
    require(len(parts) == 2, 'expected exactly boot and final root partitions')
    boot, root_part = parts
    require(root_part.get('node') == root, 'mounted root is not partition 2')
    suffix = 'p' if disk[-1:].isdigit() else ''
    require(root == disk+suffix+'2' and boot.get('node') == disk+suffix+'1',
            'partition nodes do not match the mounted-root disk')
    require(boot.get('start') == BOOT_START and boot.get('size') == BOOT_SECTORS,
            'boot boundaries differ from the documented image')
    require(root_part.get('start') == ROOT_START, 'root start differs from the documented image')
    require(all(p.get('type') == '83' for p in parts), 'partition types are not Linux')
    size = root_part.get('size')
    require(isinstance(size, int) and size > 0 and ROOT_START+size <= disk_bytes//SECTOR,
            'root extent is invalid or outside the disk')
    require(kernel_root_bytes == size*SECTOR, 'kernel and partition-table root sizes disagree')
    require(root_meta.get('TYPE') == 'ext4' and root_meta.get('LABEL') == 'NIXOS_SD',
            'root filesystem identity is unexpected')
    require(boot_meta.get('TYPE') == 'ext4' and boot_meta.get('LABEL') == 'K230_BOOT',
            'boot filesystem identity is unexpected')
    require(bool(root_meta.get('UUID')) and bool(boot_meta.get('UUID')) and bool(table.get('id')),
            'missing filesystem or partition-table identity')
    return Layout(disk, root, boot['node'], disk_bytes, size,
                  root_meta['UUID'], boot_meta['UUID'], table['id'])


class System:
    # A separate mountpoint is used only by the imported disposable-guest test.
    # The installed CLI and service always construct System() for the real /.
    def __init__(self, runner=None, mountpoint='/'):
        self.runner = runner or Runner()
        self.mountpoint = mountpoint

    def output(self, args):
        return self.runner.run(args)[1].strip()

    def inspect(self):
        root = os.path.realpath(self.output(['findmnt', '-nro', 'SOURCE', '--target', self.mountpoint]))
        info = os.stat(root)
        if not stat.S_ISBLK(info.st_mode):
            raise Refused('mounted-root source is not a block device')
        sysdev = Path('/sys/dev/block')/f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
        device = sysdev.resolve(strict=True)
        if not (device/'partition').is_file() or (device/'partition').read_text().strip() != '2':
            raise Refused('mounted root is not a second partition')
        disk = '/dev/'+device.parent.name
        if not stat.S_ISBLK(os.stat(disk).st_mode):
            raise Refused('parent disk is not a block device')
        table = json.loads(self.output(['sfdisk', '--json', disk]))['partitiontable']
        parts = table.get('partitions', [])
        if len(parts) != 2 or not isinstance(parts[0].get('node'), str):
            raise Refused('expected exactly two partitions')
        def metadata(path):
            return dict(line.split('=', 1) for line in self.output(['blkid', '-p', '-o', 'export', path]).splitlines() if '=' in line)
        return validate_layout(table, disk, root,
            int(self.output(['blockdev', '--getsize64', disk])), metadata(root), metadata(parts[0]['node']),
            self.output(['findmnt', '-nro', 'FSTYPE', '--target', self.mountpoint]),
            int(self.output(['blockdev', '--getsize64', root])))

    def filesystem(self, root):
        text = self.output(['dumpe2fs', '-h', root])
        fields = {}
        for key in ('Block count', 'Block size'):
            match = re.search(r'^'+key+r':\s+(\d+)\s*$', text, re.M)
            if not match:
                raise RuntimeError('missing ext4 '+key.lower())
            fields[key] = int(match.group(1))
        if fields['Block count'] < 1 or fields['Block size'] not in (1024, 2048, 4096, 8192, 16384, 32768, 65536):
            raise RuntimeError('invalid ext4 geometry')
        return fields['Block count']*fields['Block size'], fields['Block size']

    def grow_partition(self, disk):
        code, out, err = self.runner.run(['growpart', '--fudge', '0', disk, '2'], timeout=45, allowed=(0, 1))
        if code == 1 and not out.startswith('NOCHANGE:'):
            raise GrowthFailed('growpart failed without a verified no-change result: '+err.strip()[:800])

    def grow_filesystem(self, root):
        self.runner.run(['resize2fs', root], timeout=90)


def execute(system, apply=False):
    try:
        before = system.inspect()
        fs_before, block_size = system.filesystem(before.root)
        if fs_before > before.root_sectors*SECTOR:
            raise Refused('filesystem exceeds its current partition')
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise Refused(str(error)) from error
    result = {'status': 'checked', 'layout': dataclasses.asdict(before),
              'filesystem_bytes_before': fs_before, 'mutation_requested': apply}
    if not apply:
        return result
    try:
        system.grow_partition(before.disk)
        after_partition = system.inspect()
        if after_partition.invariant() != before.invariant() or after_partition.root_sectors < before.root_sectors:
            raise GrowthFailed('partition growth changed a protected identity or shrank root')
        # Pinned growpart reserves 33 final sectors for a possible GPT header.
        tail = after_partition.disk_bytes - (ROOT_START+after_partition.root_sectors)*SECTOR
        if not 0 <= tail <= 33*SECTOR:
            raise GrowthFailed('partition did not reach the available trailing capacity')
        # Reinspection also checks the kernel partition view before resizing ext4.
        system.grow_filesystem(before.root)
        after = system.inspect()
        fs_after, after_block = system.filesystem(after.root)
        if after != after_partition or after_block != block_size or fs_after < fs_before:
            raise GrowthFailed('filesystem growth changed layout or filesystem geometry unexpectedly')
        # e2fsprogs 1.47.4 resize/main.c rounds the default target down to
        # a system page when pages exceed filesystem blocks (e.g. 1 KiB ext4).
        alignment = max(block_size, os.sysconf('SC_PAGE_SIZE'))
        if not 0 <= after.root_sectors*SECTOR-fs_after < alignment:
            raise GrowthFailed(f'filesystem did not reach its partition capacity: filesystem={fs_after}, partition={after.root_sectors*SECTOR}, block={block_size}')
        result.update(status='grown' if fs_after > fs_before else 'no-change',
                      root_sectors_after=after.root_sectors, filesystem_bytes_after=fs_after)
        return result
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise GrowthFailed(str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='grow the verified mounted root; default is read-only preflight')
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise Refused('root privileges are required to inspect the mounted block devices')
        with open('/run/k230-root-growth.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('another root-growth operation owns the lock') from None
            result = execute(System(), args.apply)
        code = 0
    except Refused as error:
        result, code = {'status': 'refused', 'reason': str(error), 'mutation_requested': args.apply}, 2
    except (GrowthFailed, OSError) as error:
        result, code = {'status': 'failed', 'reason': str(error), 'mutation_requested': args.apply}, 1
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
