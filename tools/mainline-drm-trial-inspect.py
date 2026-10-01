#!/usr/bin/env python3
"""Check matching host boot artifacts; this never opens the board."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

bundle = Path(sys.argv[1]).resolve()
system = (bundle / 'system').resolve()
kernel = (system / 'kernel').resolve().parent
assert (bundle / 'Image-mainline-drm').read_bytes() == (kernel / 'Image').read_bytes()

args = (bundle / 'bootargs.txt').read_text().strip()
assert args.startswith('bootargs=')
assert f'init={system}/init' in args and 'root=fstab' in args
fdtget = 'fdtget'
dtargs = subprocess.check_output([
    fdtget, str(bundle / 'k230-tdisplay-mainline-drm.dtb'),
    '/chosen', 'bootargs',
], text=True).strip()
assert dtargs == args.removeprefix('bootargs=')

uimage = (bundle / 'initrd.uimg').read_bytes()
header = struct.unpack('>7I4B32s', uimage[:64])
assert header[0] == 0x27051956
assert header[7:11] == (5, 26, 3, 0)  # Linux, RISC-V, ramdisk, no wrapper compression
assert header[3] == len(uimage) - 64
assert header[6] == zlib.crc32(uimage[64:])
crc_header = bytearray(uimage[:64])
crc_header[4:8] = bytes(4)
assert header[1] == zlib.crc32(crc_header)
assert uimage[64:] == (system / 'initrd').read_bytes()

paths = set((bundle / 'store-paths').read_text().splitlines())
assert str(system) in paths and str(kernel) in paths
assert all(Path(path).exists() for path in paths)
assert (bundle / 'registration').stat().st_size > 0
subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=bundle, check=True)
print(json.dumps({
    'bundle': str(bundle),
    'system': str(system),
    'kernel': str(kernel),
    'closure_paths': len(paths),
    'bootargs': dtargs,
    'files': {p.name: p.stat().st_size for p in bundle.iterdir() if p.is_file()},
    'uimage_crc_valid': True,
    'initrd_payload_matches_system': True,
    'Image_matches_candidate': True,
    'DTB_bootargs_matches_environment': True,
}, indent=2))
