#!/usr/bin/env python3
"""Fail-closed identities for one built K230 RVV candidate (not board proof)."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SCHEMA = 'k230-rvv-candidate-v1'
PATHS = ('system', 'kernel', 'context_probe', 'pixman_library', 'pixel_probe',
         'card_package', 'sway_executable', 'normal_config', 'client', 'python')
FILES = {'kernel_image': ('kernel', 'Image'), 'context_probe': ('context_probe',),
         'pixman_library': ('pixman_library',),
         'pixel_probe': ('pixel_probe', 'bin/k230-pixman-rvv-pixel-probe'),
         'sway_executable': ('sway_executable',), 'normal_config': ('normal_config',),
         'client': ('client',), 'python': ('python',)}
STORE = re.compile(r'/nix/store/[a-z0-9]{32}-[^/\s]+(?:/[^\s]*)?\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def file_for(manifest, key):
    root, *suffix = FILES[key]
    return Path(manifest[root]).joinpath(*suffix)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, *, expected_sha256=None):
    raw = Path(path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('staged candidate manifest hash differs')
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {'schema', *PATHS, 'sha256'} or value['schema'] != SCHEMA:
        raise RuntimeError('missing or unsupported candidate manifest fields')
    if not isinstance(value['sha256'], dict) or set(value['sha256']) != set(FILES):
        raise RuntimeError('missing or extra candidate file hashes')
    for key in PATHS:
        name = value[key]
        if not isinstance(name, str) or not STORE.fullmatch(name) or '/..' in name or '/./' in name:
            raise RuntimeError('invalid immutable store path: ' + key)
        if key in ('system', 'kernel', 'pixel_probe', 'card_package') and not Path(name).is_dir():
            raise RuntimeError('missing candidate package: ' + key)
    for key, expected in value['sha256'].items():
        if not isinstance(expected, str) or not SHA.fullmatch(expected):
            raise RuntimeError('invalid candidate file hash: ' + key)
        try:
            observed = digest(file_for(value, key))
        except OSError as error:
            raise RuntimeError('missing candidate file: ' + key) from error
        if observed != expected:
            raise RuntimeError('stale candidate file: ' + key)
    try:
        boot = json.loads((Path(value['system']) / 'boot.json').read_text())['org.nixos.bootspec.v1']
    except (OSError, KeyError, ValueError) as error:
        raise RuntimeError('missing system bootspec') from error
    if boot.get('kernel') != str(file_for(value, 'kernel_image')) or boot.get('toplevel') != value['system']:
        raise RuntimeError('candidate kernel is not bound to system bootspec')
    return value


def require_board(manifest):
    if os.path.realpath('/run/current-system') != manifest['system']:
        raise RuntimeError('candidate system is not running')
    if Path('/sys/firmware/devicetree/base/model').read_bytes().rstrip(b'\0') != b'LILYGO T-Display-K230':
        raise RuntimeError('wrong physical board')


def require_pixel_linkage(manifest):
    """Check the probe's immutable ELF loader path before host staging."""
    binary = file_for(manifest, 'pixel_probe')
    report = subprocess.run(['readelf', '-d', str(binary)], capture_output=True,
                            text=True, timeout=15, check=True).stdout
    needed = re.findall(r'\(NEEDED\).*\[([^]]+)\]', report)
    runpaths = re.findall(r'\((?:RUNPATH|RPATH)\).*\[([^]]+)\]', report)
    if needed.count('libpixman-1.so.0') != 1 or len(runpaths) != 1:
        raise RuntimeError('pixel probe has no unique Pixman loader path')
    found = [Path(folder) / 'libpixman-1.so.0' for folder in runpaths[0].split(':')
             if (Path(folder) / 'libpixman-1.so.0').exists()]
    expected = os.path.realpath(manifest['pixman_library'])
    if len(found) != 1 or os.path.realpath(found[0]) != expected:
        raise RuntimeError('pixel probe loader path differs from candidate Pixman')


def require_loaded_pixel_library(debug_output, manifest):
    """Check glibc's observed library initialization on the physical run."""
    loaded = re.findall(r'calling init: ([^\s]*libpixman-1\.so[^\s]*)', debug_output)
    expected = os.path.realpath(manifest['pixman_library'])
    if len(loaded) != 1 or os.path.realpath(loaded[0]) != expected:
        raise RuntimeError('pixel process loaded a different Pixman library')


def require_mapped_library(maps_text, manifest):
    mapped = sorted({line.split()[-1] for line in maps_text.splitlines()
                     if '/libpixman-1.so' in line and len(line.split()) >= 6})
    expected = os.path.realpath(manifest['pixman_library'])
    if not mapped or any(os.path.realpath(path) != expected for path in mapped):
        raise RuntimeError('mapped Pixman library differs from candidate')
    return mapped
