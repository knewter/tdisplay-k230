#!/usr/bin/env python3
"""Tamper a small fixture using the built bundle's pinned DT inspection tools.

Run: python3 tests/test_coherent_shell_boot_inspect.py --bundle <bundle>
No serial access or real store/boot mutation is performed.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location('inspect_boot',
    Path(__file__).resolve().parents[1] / 'tools/coherent-shell-boot-inspect.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def wrap(payload, architecture=26):
    header = struct.pack('>7I4B32s', 0x27051956, 0, 0, len(payload), 0, 0,
                         zlib.crc32(payload), 5, architecture, 3, 0, b'initrd')
    return header[:4] + struct.pack('>I', zlib.crc32(header)) + header[8:] + payload


class BundleInspection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home() / 'tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'; self.bundle.mkdir()
        self.system = self.root / 'system'; self.system.mkdir()
        kernel = self.root / 'kernel'; kernel.mkdir()
        initrd = self.root / 'initrd'; initrd.mkdir()
        (kernel / 'Image').write_bytes(b'selected kernel')
        (initrd / 'initrd').write_bytes(b'selected initrd')
        (self.system / 'kernel').symlink_to(kernel / 'Image')
        (self.system / 'initrd').symlink_to(initrd / 'initrd')
        (self.system / 'init').write_text('selected init')
        (self.bundle / 'system').symlink_to(self.system)
        (self.bundle / 'inspect-tools').symlink_to(REAL_BUNDLE / 'inspect-tools')
        source = json.loads((REAL_BUNDLE / 'identity.json').read_text())['device_tree']
        args = f'console=ttyS0 root=fstab init={self.system}/init'
        self.identity = dict(schema=1, configuration='k230-coherent-shell',
                             system=str(self.system), kernel=str(kernel / 'Image'),
                             device_tree=source, bootargs=args)
        (self.bundle / 'Image').write_bytes((kernel / 'Image').read_bytes())
        (self.bundle / 'initrd.uimg').write_bytes(wrap((initrd / 'initrd').read_bytes()))
        (self.bundle / 'k230-tdisplay.dtb').write_bytes(Path(source).read_bytes())
        subprocess.run([str(self.bundle / 'inspect-tools/fdtput'), '-t', 's',
                        str(self.bundle / 'k230-tdisplay.dtb'), '/chosen', 'bootargs', args], check=True)
        (self.bundle / 'bootargs.txt').write_text(f'bootargs={args}\n')
        paths = [str(self.system), str(kernel), str(initrd)]
        (self.bundle / 'store-paths').write_text('\n'.join(paths) + '\n')
        (self.bundle / 'registration').write_text(''.join(f'{p}\nsha256:fixture\n1\n\n0\n' for p in paths))
        self.sums()

    def sums(self):
        (self.bundle / 'identity.json').write_text(json.dumps(self.identity) + '\n')
        (self.bundle / 'SHA256SUMS').write_text(''.join(
            f'{hashlib.sha256((self.bundle / n).read_bytes()).hexdigest()}  {n}\n' for n in boot.FILES))

    def rejected(self, message):
        self.sums()  # Exercise payload/identity validation independently of checksums.
        with self.assertRaisesRegex(ValueError, message):
            boot.inspect(self.bundle)

    def test_matching_bundle(self):
        result = boot.inspect(self.bundle)
        self.assertEqual(result['host_inspection'], 'PASS')
        self.assertFalse(result['physical_boot_verified'])
        self.assertFalse(result['persistent_boot_selection_changed'])

    def test_bad_checksum(self):
        (self.bundle / 'Image').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            boot.inspect(self.bundle)

    def test_rehashed_wrong_kernel(self):
        (self.bundle / 'Image').write_bytes(b'another kernel')
        self.rejected('Image differs')

    def test_wrong_system_identity(self):
        self.identity['system'] += '-another'
        self.rejected('system identity mismatch')

    def test_duplicate_init(self):
        self.identity['bootargs'] += ' init=/another/init'
        self.rejected('exactly the matching system')

    def test_wrong_environment(self):
        (self.bundle / 'bootargs.txt').write_text('bootargs=init=/another/init\n')
        self.rejected('environment command line differs')

    def test_dtb_non_command_line_change(self):
        subprocess.run([str(self.bundle / 'inspect-tools/fdtput'), '-t', 's',
                        str(self.bundle / 'k230-tdisplay.dtb'), '/', 'model', 'another board'], check=True)
        self.rejected('DTB differs from selected board tree')

    def test_ramdisk_bad_header_crc(self):
        data = bytearray((self.bundle / 'initrd.uimg').read_bytes()); data[8] ^= 1
        (self.bundle / 'initrd.uimg').write_bytes(data)
        self.rejected('header CRC mismatch')

    def test_ramdisk_bad_payload_crc(self):
        data = bytearray((self.bundle / 'initrd.uimg').read_bytes()); data[-1] ^= 1
        (self.bundle / 'initrd.uimg').write_bytes(data)
        self.rejected('payload CRC mismatch')

    def test_valid_crc_wrong_payload(self):
        (self.bundle / 'initrd.uimg').write_bytes(wrap(b'another initrd'))
        self.rejected('payload differs from selected system')

    def test_wrong_architecture(self):
        (self.bundle / 'initrd.uimg').write_bytes(wrap(b'selected initrd', architecture=2))
        self.rejected('Linux/RISC-V')

    def test_registration_truncation(self):
        (self.bundle / 'registration').write_text(str(self.system) + '\n')
        self.rejected('truncated registration')

    def test_closure_missing_kernel(self):
        (self.bundle / 'store-paths').write_text(str(self.system) + '\n')
        self.rejected('missing from closure inventory')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    REAL_BUNDLE = args.bundle.resolve(strict=True)
    unittest.main(argv=[__file__, *remaining])
