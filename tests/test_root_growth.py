#!/usr/bin/env python3
"""Host policy/failure checks; actual ext4 growth belongs to the QEMU fixture."""
import copy
import dataclasses
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('root_growth', ROOT/'tools/root-growth.py')
growth = importlib.util.module_from_spec(spec); sys.modules[spec.name] = growth; spec.loader.exec_module(growth)


def observations():
    return {
        'table': {'label': 'dos', 'unit': 'sectors', 'sectorsize': 512, 'device': '/dev/vda', 'id': '0x12345678',
                  'partitions': [{'node': '/dev/vda1', 'start': 8192, 'size': 229376, 'type': '83'},
                                 {'node': '/dev/vda2', 'start': 262144, 'size': 262144, 'type': '83'}]},
        'disk': '/dev/vda', 'root': '/dev/vda2', 'disk_bytes': 512*1024*1024,
        'root_meta': {'TYPE': 'ext4', 'LABEL': 'NIXOS_SD', 'UUID': 'root-uuid'},
        'boot_meta': {'TYPE': 'ext4', 'LABEL': 'K230_BOOT', 'UUID': 'boot-uuid'},
        'mounted_type': 'ext4', 'kernel_root_bytes': 128*1024*1024,
    }


class FakeSystem:
    def __init__(self, data=None, full=False, interrupted=False):
        self.data = data or observations()
        if full or interrupted:
            self.data['table']['partitions'][1]['size'] = 786432
            self.data['kernel_root_bytes'] = 384*1024*1024
        self.fs_bytes = 384*1024*1024 if full else 128*1024*1024
        self.writes = []
        self.fail = None
        self.bad_start = False
        self.bad_uuid = False

    def inspect(self):
        return growth.validate_layout(**self.data)

    def filesystem(self, root):
        return self.fs_bytes, 4096

    def grow_partition(self, disk):
        self.writes.append('partition')
        if self.fail == 'partition':
            raise RuntimeError('injected partition tool failure')
        self.data['table']['partitions'][1]['size'] = 786432
        self.data['kernel_root_bytes'] = 384*1024*1024
        if self.bad_start:
            self.data['table']['partitions'][1]['start'] += 1
        if self.bad_uuid:
            self.data['root_meta']['UUID'] = 'changed'

    def grow_filesystem(self, root):
        self.writes.append('filesystem')
        if self.fail == 'filesystem':
            raise RuntimeError('injected filesystem tool failure')
        self.fs_bytes = self.data['kernel_root_bytes']


class GuardTests(unittest.TestCase):
    def test_supported_identity_and_readonly_default(self):
        system = FakeSystem()
        result = growth.execute(system)
        self.assertEqual(result['status'], 'checked')
        self.assertEqual(result['layout']['root'], '/dev/vda2')
        self.assertEqual(system.writes, [])

    def test_refused_inputs_never_reach_mutations(self):
        variants = []
        for field, value in [('label', 'gpt'), ('unit', 'bytes'), ('sectorsize', 4096), ('device', '/dev/vdb'), ('id', '')]:
            d = observations(); d['table'][field] = value; variants.append(d)
        for part, field, value in [(0, 'start', 0), (0, 'node', '/dev/vdb1'), (0, 'size', 229375), (1, 'start', 262145),
                                   (1, 'size', 999999999), (1, 'size', -1), (1, 'node', '/dev/vdb2'), (1, 'type', '5')]:
            d = observations(); d['table']['partitions'][part][field] = value; variants.append(d)
        for field, value in [('mounted_type', 'xfs'), ('kernel_root_bytes', 1024), ('disk_bytes', 1 << 42)]:
            d = observations(); d[field] = value; variants.append(d)
        for group, field, value in [('root_meta', 'LABEL', 'unrelated'), ('root_meta', 'TYPE', 'btrfs'),
                                    ('boot_meta', 'LABEL', 'other'), ('boot_meta', 'TYPE', 'vfat'), ('root_meta', 'UUID', '')]:
            d = observations(); d[group][field] = value; variants.append(d)
        d = observations(); d['table']['partitions'].append({'node': '/dev/vda3', 'start': 900000, 'size': 10000, 'type': '83'}); variants.append(d)
        for index, data in enumerate(variants):
            with self.subTest(index=index):
                system = FakeSystem(data)
                with self.assertRaises(growth.Refused): growth.execute(system, True)
                self.assertEqual(system.writes, [])

    def test_first_growth_and_repeat(self):
        system = FakeSystem()
        result = growth.execute(system, True)
        self.assertEqual(result['status'], 'grown')
        self.assertEqual(result['filesystem_bytes_after'], 384*1024*1024)
        self.assertEqual(system.writes, ['partition', 'filesystem'])
        self.assertEqual(growth.execute(system, True)['status'], 'no-change')

    def test_one_kib_filesystem_uses_pinned_resize_page_alignment(self):
        class PageAligned(FakeSystem):
            def grow_partition(self, disk):
                super().grow_partition(disk)
                self.data['table']['partitions'][1]['size'] -= 33
                self.data['kernel_root_bytes'] -= 33*512
            def grow_filesystem(self, root):
                self.writes.append('filesystem')
                self.fs_bytes = self.data['kernel_root_bytes']//4096*4096
            def filesystem(self, root): return self.fs_bytes, 1024
        result = growth.execute(PageAligned(), True)
        self.assertEqual(result['status'], 'grown')
        self.assertEqual(result['root_sectors_after']*512-result['filesystem_bytes_after'], 3584)

    def test_full_disk_is_no_change(self):
        self.assertEqual(growth.execute(FakeSystem(full=True), True)['status'], 'no-change')

    def test_retry_after_partition_only_growth(self):
        system = FakeSystem(interrupted=True)
        result = growth.execute(system, True)
        self.assertEqual(result['status'], 'grown')
        self.assertEqual(result['root_sectors_after'], 786432)

    def test_partition_failure_never_reaches_filesystem(self):
        system = FakeSystem(); system.fail = 'partition'
        with self.assertRaisesRegex(growth.GrowthFailed, 'partition tool failure'): growth.execute(system, True)
        self.assertEqual(system.writes, ['partition'])

    def test_filesystem_failure_remains_failed_and_retryable(self):
        system = FakeSystem(); system.fail = 'filesystem'
        with self.assertRaisesRegex(growth.GrowthFailed, 'filesystem tool failure'): growth.execute(system, True)
        self.assertEqual(system.fs_bytes, 128*1024*1024)
        system.fail = None
        self.assertEqual(growth.execute(system, True)['status'], 'grown')

    def test_post_partition_identity_change_stops_before_resize(self):
        for field in ('bad_start', 'bad_uuid'):
            system = FakeSystem(); setattr(system, field, True)
            with self.subTest(field=field), self.assertRaises(growth.GrowthFailed): growth.execute(system, True)
            self.assertEqual(system.writes, ['partition'])

    def test_nochange_tool_result_cannot_hide_unused_disk_capacity(self):
        system = FakeSystem(); system.grow_partition = lambda disk: None
        with self.assertRaisesRegex(growth.GrowthFailed, 'available trailing capacity'): growth.execute(system, True)
        self.assertEqual(system.writes, [])

    def test_success_status_without_filesystem_growth_is_rejected(self):
        system = FakeSystem(); system.grow_filesystem = lambda root: None
        with self.assertRaisesRegex(growth.GrowthFailed, 'did not reach'): growth.execute(system, True)

    def test_filesystem_larger_than_partition_refuses_before_writes(self):
        system = FakeSystem(); system.fs_bytes = 256*1024*1024
        with self.assertRaises(growth.Refused): growth.execute(system, True)
        self.assertEqual(system.writes, [])

    def test_nochange_exit_requires_explicit_tool_result(self):
        class ResultRunner:
            def __init__(self, text): self.text = text
            def run(self, *args, **kwargs): return 1, self.text, 'diagnostic'
        growth.System(ResultRunner('NOCHANGE: partition 2 is full\n')).grow_partition('/dev/vda')
        with self.assertRaises(growth.GrowthFailed):
            growth.System(ResultRunner('FAILED: cannot lock disk\n')).grow_partition('/dev/vda')


if __name__ == '__main__':
    unittest.main()
