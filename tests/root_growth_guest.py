#!/usr/bin/env python3
"""Actual disposable-disk tests. Runs only as PID 1 in the marked QEMU guest."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DISK = '/dev/vda'
ROOT = '/dev/vda2'
MOUNT = '/mnt/root-test'
BOOT = '/dev/vda1'
MIB = 1024*1024


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=60, **kwargs).stdout


def digest(device, offset, size):
    h = hashlib.sha256()
    with open(device, 'rb', buffering=0) as stream:
        stream.seek(offset)
        while size:
            chunk = stream.read(min(size, MIB))
            assert chunk, 'short protected-region read'
            size -= len(chunk); h.update(chunk)
    return h.hexdigest()


def protected():
    return {'firmware_gap_sha256': digest(DISK, 512, 4*MIB-512),
            'boot_partition_sha256': digest(BOOT, 0, 112*MIB)}


def prepare(label='NIXOS_SD', filesystem='ext4', full=False, later=False):
    run(['umount', MOUNT]) if os.path.ismount(MOUNT) else None
    sectors = (512*MIB-128*MIB)//512 if full else 128*MIB//512
    table = f'label: dos\nunit: sectors\n\nstart=8192,size=229376,type=83\nstart=262144,size={sectors},type=83\n'
    if later:
        table += 'start=786432,size=32768,type=83\n'
    run(['sfdisk', '--wipe', 'always', '--wipe-partitions', 'always', DISK], input=table)
    run(['partx', '--update', DISK])
    deadline = time.monotonic()+5
    while not Path(ROOT).exists() and time.monotonic() < deadline: time.sleep(.05)
    assert Path(ROOT).exists()
    with open(DISK, 'r+b', buffering=0) as stream:
        # Distinct bytes at every firmware slot; hash the entire protected gap.
        for index, offset in enumerate((MIB, MIB+MIB//2, 2*MIB, 3*MIB, 3200*1024)):
            stream.seek(offset); stream.write(bytes([41+index])*4096)
        os.fsync(stream.fileno())
    options = ['-F', '-q', '-E', 'lazy_itable_init=0,lazy_journal_init=0']
    run(['mkfs.ext4', *options, '-L', 'K230_BOOT', BOOT])
    run(['mkfs.'+filesystem, *options, '-L', label, ROOT])
    run(['mount', '-t', 'ext4', '-o', 'noatime', ROOT, MOUNT])
    with (Path(MOUNT)/'sentinel').open('wb') as stream:
        stream.write(b'root data survives partition and filesystem growth\n'*128)
        stream.flush(); os.fsync(stream.fileno())
    run(['sync'])
    return sectors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--helper', required=True)
    args = parser.parse_args()
    if os.getpid() != 1:
        raise RuntimeError('disposable growth fixture must be guest PID 1')
    for name in ('/proc', '/sys', '/dev', '/run', '/tmp', MOUNT): Path(name).mkdir(parents=True, exist_ok=True)
    run(['mount', '-t', 'proc', 'proc', '/proc'])
    assert 'k230.root_growth_guest=1' in Path('/proc/cmdline').read_text().split()
    run(['mount', '-t', 'sysfs', 'sysfs', '/sys'])
    run(['mount', '-t', 'devtmpfs', 'devtmpfs', '/dev'])
    assert int(run(['blockdev', '--getsize64', DISK])) == 512*MIB
    spec = importlib.util.spec_from_file_location('root_growth', args.helper)
    g = importlib.util.module_from_spec(spec); sys.modules[spec.name] = g; spec.loader.exec_module(g)

    class TrackingRunner(g.Runner):
        def __init__(self): self.writes = []; self.fail_once = None
        def run(self, args, **kwargs):
            if args[0] in ('growpart', 'resize2fs'):
                self.writes.append(args[0])
                if self.fail_once == args[0]:
                    self.fail_once = None
                    raise RuntimeError('injected before '+args[0])
            result = super().run(args, **kwargs)
            if args[0] in ('growpart', 'resize2fs'):
                print('K230_ROOT_GROWTH_TOOL '+json.dumps({'argv': args, 'code': result[0], 'stdout': result[1], 'stderr': result[2]}), flush=True)
            return result

    results = []
    for name, options in (
        ('growth-and-repeat', {}), ('already-full', {'full': True}),
        ('wrong-label', {'label': 'OTHER_ROOT'}), ('later-partition', {'later': True}),
        ('unsupported-filesystem', {'filesystem': 'ext2'}),
        ('partition-tool-failure', {}), ('partition-only-retry', {}),
    ):
        prepare(**options)
        runner = TrackingRunner(); system = g.System(runner, MOUNT)
        before = protected()
        table_before = json.loads(run(['sfdisk', '--json', DISK]))
        sentinel = (Path(MOUNT)/'sentinel').read_bytes()
        row = {'case': name, 'protected_before': before}
        if name in ('wrong-label', 'later-partition', 'unsupported-filesystem', 'partition-tool-failure'):
            root_bytes = int(run(['blockdev', '--getsize64', ROOT]))
            root_hash = digest(ROOT, 0, root_bytes)
            if name == 'partition-tool-failure': runner.fail_once = 'growpart'
            try:
                g.execute(system, True)
            except (g.Refused, g.GrowthFailed) as error:
                row['refusal_or_failure'] = str(error)
            else:
                raise AssertionError('negative case unexpectedly succeeded: '+name)
            expected = ['growpart'] if name == 'partition-tool-failure' else []
            assert runner.writes == expected, 'unexpected mutation after refusal'
            assert json.loads(run(['sfdisk', '--json', DISK])) == table_before
            assert digest(ROOT, 0, root_bytes) == root_hash, 'refused filesystem changed'
            row['unchanged_root_sha256'] = root_hash
        else:
            if name == 'partition-only-retry':
                old_fs = system.filesystem(ROOT)
                runner.fail_once = 'resize2fs'
                try:
                    g.execute(system, True)
                except g.GrowthFailed as error:
                    row['injected_failure'] = str(error)
                else:
                    raise AssertionError('injected filesystem failure was hidden')
                assert system.inspect().root_sectors > table_before['partitiontable']['partitions'][1]['size']
                assert system.filesystem(ROOT) == old_fs
            result = g.execute(system, True)
            assert result['status'] == ('no-change' if name == 'already-full' else 'grown')
            assert system.inspect().disk_bytes-(g.ROOT_START+system.inspect().root_sectors)*512 <= 33*512
            row['growth'] = result
            table_after = json.loads(run(['sfdisk', '--json', DISK]))
            repeat = g.execute(system, True)
            assert repeat['status'] == 'no-change'
            assert json.loads(run(['sfdisk', '--json', DISK])) == table_after
            row['repeat'] = repeat
        assert (Path(MOUNT)/'sentinel').read_bytes() == sentinel
        after = protected(); assert after == before, 'protected boot/firmware data changed'
        row.update(protected_after=after, mutation_commands=runner.writes, status='PASS')
        results.append(row)
        print('K230_ROOT_GROWTH_CASE '+name+' PASS', flush=True)
    run(['umount', MOUNT]); run(['sync'])
    print('K230_ROOT_GROWTH_RESULT '+json.dumps({
        'status': 'PASS', 'run_id': Path('/run-id').read_text().strip(),
        'evidence_class': 'qemu-system-disposable-ext4-disk',
        'machine': os.uname().machine, 'kernel': os.uname().release,
        'helper_sha256': hashlib.sha256(Path(args.helper).read_bytes()).hexdigest(),
        'cases': results,
        'limits': ['Mounted disposable /mnt/root-test, not production / or the boot service.',
                   'No physical K230 boot, flash, power-loss-during-write or shell proof.',
                   'Failure injection occurs before the named tool runs; retry proves the completed-partition/incomplete-filesystem boundary.'],
    }, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
