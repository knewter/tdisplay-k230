#!/usr/bin/env python3
"""Inspect one coherent normal boot bundle. Never opens or changes the board."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

FILES = ('Image', 'k230-tdisplay.dtb', 'initrd.uimg', 'bootargs.txt',
         'identity.json', 'store-paths', 'registration')
LIMITS = {'Image': 64 * 1024**2, 'initrd.uimg': 64 * 1024**2,
          'bootargs.txt': 4096, 'k230-tdisplay.dtb': 1024**2}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_identity(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'crc32': f'{zlib.crc32(data):08x}'}


def check_registration(lines, paths):
    """Read closureInfo's exportReferencesGraph registration records."""
    registered = set()
    while lines:
        require(len(lines) >= 5, 'truncated registration record')
        path, nar_hash, nar_size, deriver, count = lines[:5]
        require(path not in registered and path in paths, 'unexpected registration path')
        require(bool(nar_hash) and nar_size.isdecimal() and int(nar_size) > 0,
                'invalid registration NAR identity')
        require(not deriver or deriver in paths, 'registration deriver outside closure')
        require(count.isdecimal(), 'invalid registration reference count')
        count = int(count)
        require(len(lines) >= 5 + count, 'truncated registration references')
        require(all(p in paths for p in lines[5:5 + count]),
                'registration reference outside closure')
        registered.add(path)
        lines = lines[5 + count:]
    require(registered == paths, 'registration omits a closure path')


def inspect(bundle):
    bundle = Path(bundle).resolve(strict=True)
    identity = json.loads((bundle / 'identity.json').read_text())
    require(identity.get('schema') == 1, 'unsupported bundle schema')
    require(identity.get('configuration') == 'k230-coherent-shell',
            'unexpected configuration')
    sums = {}
    for line in (bundle / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        require(name in FILES and name not in sums, 'unexpected/duplicate checksum entry')
        sums[name] = digest
    require(set(sums) == set(FILES), 'incomplete checksum inventory')
    for name, digest in sums.items():
        require(file_identity(bundle / name)['sha256'] == digest,
                f'checksum mismatch: {name}')
    for name, limit in LIMITS.items():
        require(0 < (bundle / name).stat().st_size < limit, f'unsafe load size: {name}')

    system = (bundle / 'system').resolve(strict=True)
    require(str(system) == identity['system'], 'selected system identity mismatch')
    kernel = (system / 'kernel').resolve(strict=True)
    require(str(kernel) == identity['kernel'], 'selected kernel identity mismatch')
    require((bundle / 'Image').read_bytes() == kernel.read_bytes(),
            'Image differs from selected system kernel')
    require((system / 'init').is_file(), 'selected init missing')
    args = identity['bootargs']
    require('\n' not in args and '\r' not in args and '\0' not in args,
            'invalid kernel command line')
    require([p for p in args.split() if p.startswith('init=')] == [f'init={system}/init'],
            'bootargs do not select exactly the matching system')
    require((bundle / 'bootargs.txt').read_bytes() == f'bootargs={args}\n'.encode(),
            'environment command line differs from selected configuration')
    tools = bundle / 'inspect-tools'
    dtb = bundle / 'k230-tdisplay.dtb'
    dtargs = subprocess.check_output(
        [str(tools / 'fdtget'), str(dtb), '/chosen', 'bootargs'], text=True).rstrip('\n')
    require(dtargs == args, 'DTB command line differs from environment')
    # Recreate the only permitted DTB modification from its pinned source.
    # Comparing just bootargs would overlook a changed panel/input tree.
    source_dtb = Path(identity['device_tree']).resolve(strict=True)
    scratch = Path.home() / 'tmp'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='k230-dtb-', dir=scratch) as temp:
        expected = Path(temp) / 'expected.dtb'
        expected.write_bytes(source_dtb.read_bytes())
        subprocess.run([str(tools / 'fdtput'), '-t', 's', str(expected),
                        '/chosen', 'bootargs', args], check=True)
        require(expected.read_bytes() == dtb.read_bytes(), 'DTB differs from selected board tree')

    image = (bundle / 'initrd.uimg').read_bytes()
    require(len(image) >= 64, 'short ramdisk header')
    header = struct.unpack('>7I4B32s', image[:64])
    require(header[0] == 0x27051956, 'invalid ramdisk magic')
    require(header[7:11] == (5, 26, 3, 0), 'ramdisk wrapper is not Linux/RISC-V/uncompressed')
    require(header[3] == len(image) - 64, 'ramdisk payload length mismatch')
    require(header[6] == zlib.crc32(image[64:]), 'ramdisk payload CRC mismatch')
    crc_header = bytearray(image[:64]); crc_header[4:8] = bytes(4)
    require(header[1] == zlib.crc32(crc_header), 'ramdisk header CRC mismatch')
    require(image[64:] == (system / 'initrd').read_bytes(),
            'ramdisk payload differs from selected system initrd')

    paths = (bundle / 'store-paths').read_text().splitlines()
    require(len(paths) == len(set(paths)), 'duplicate closure paths')
    require(str(system) in paths and str(kernel.parent) in paths and
            str((system / 'initrd').resolve(strict=True).parent) in paths,
            'selected system/kernel/initrd missing from closure inventory')
    require(all(Path(p).exists() for p in paths), 'closure path absent on host')
    registration = (bundle / 'registration').read_text().splitlines()
    check_registration(registration, set(paths))
    return dict(identity, bundle=str(bundle), initrd=str((system / 'initrd').resolve()),
                closure_paths=len(paths), boot_files={n: file_identity(bundle / n) for n in LIMITS},
                Image_matches_selected_kernel=True, initrd_payload_matches_system=True,
                uimage_crc_valid=True, bootargs_select_matching_system=True,
                DTB_matches_selected_board_tree=True, host_inspection='PASS',
                physical_boot_verified=False, persistent_boot_selection_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.bundle), indent=2))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'boot bundle rejected: {error}\n')


if __name__ == '__main__':
    main()
