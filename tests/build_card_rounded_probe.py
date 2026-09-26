#!/usr/bin/env python3
"""Build a host-only ARGB/corner-child variant of the existing test client.

The production probe source stays unchanged. The explicit substitutions
below exercise translucent subsurfaces at the parent's rounded corner.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
source = (ROOT / 'nix/card-composition-probe-client/card-composition-probe-client.c').read_text()
replacements = {
    'WL_SHM_FORMAT_XRGB8888': 'WL_SHM_FORMAT_ARGB8888',
    'wl_subsurface_set_position(a.sub,32,48);': 'wl_subsurface_set_position(a.sub,0,0);',
    'b->pixels[(size_t)y*p->width+x]=color;':
        'b->pixels[(size_t)y*p->width+x]=p->child ? '
        '0x80000000u | ((color >> 1) & 0x007f7f7fu) : 0xff000000u | color;',
    r'\"format\":\"XRGB8888\"': r'\"format\":\"ARGB8888\"',
}
for before, after in replacements.items():
    assert source.count(before) == 1, before
    source = source.replace(before, after)
(args.output / 'client.c').write_text(source)
protocol = '/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml'
subprocess.run(['wayland-scanner', 'client-header', protocol,
                str(args.output / 'xdg-shell-client-protocol.h')], check=True)
subprocess.run(['wayland-scanner', 'private-code', protocol,
                str(args.output / 'xdg-shell-protocol.c')], check=True)
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'wayland-client'], text=True))
command = ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
    str(args.output / 'client.c'), str(args.output / 'xdg-shell-protocol.c'),
    *flags, '-o', str(args.output / 'client')]
subprocess.run(command, check=True)
(args.output / 'build.json').write_text(json.dumps({
    'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
    'binary_sha256': hashlib.sha256((args.output / 'client').read_bytes()).hexdigest(),
    'command': command, 'variant': 'ARGB8888 parent, half-alpha child at parent origin'}, indent=2) + '\n')
