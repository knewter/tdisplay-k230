#!/usr/bin/env python3
"""On-board preparation/check for a host-inspected coherent boot trial.

Run as root against an exclusively reserved board. Never writes normal boot
files, the persistent profile, selectors, or stage 1. Transport stays external.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zlib

NORMAL_FILES = ('Image', 'initrd.uimg', 'k230-tdisplay.dtb', 'bootargs.txt',
                'fw_jump_add_uboot_head.bin', 'force_dtb', 'lcd_dtb', 'hdmi_dtb')


def identity(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                crc32=f'{zlib.crc32(data):08x}')


def check(stage):
    state = json.loads((stage / 'state.json').read_text())
    assert not Path('/nix-path-registration').exists(), 'bootstrap profile replacement is present'
    assert str(Path('/nix/var/nix/profiles/system').resolve()) == state['normal_profile']
    for name, expected in state['normal_files'].items():
        assert identity(Path('/boot') / name) == expected, 'normal boot file changed: ' + name
        assert identity(stage / 'backup' / name) == expected, 'rollback file changed: ' + name
    for name, expected in state['candidate']['boot_files'].items():
        assert identity(stage / name) == expected, 'candidate file changed: ' + name
    system = Path(state['candidate']['system'])
    assert identity(system / 'kernel') == identity(stage / 'Image')
    assert (stage / 'initrd.uimg').read_bytes()[64:] == (system / 'initrd').read_bytes()
    assert (stage / 'bootargs.txt').read_text() == 'bootargs=' + state['candidate']['bootargs'] + '\n'
    paths = (stage / 'store-paths').read_text().splitlines()
    subprocess.run(['nix-store', '--check-validity', *paths], check=True,
                   stdout=subprocess.DEVNULL)
    actual = subprocess.check_output(['nix-store', '-qR', str(system)], text=True).splitlines()
    assert set(actual) == set(paths), 'registered board closure differs from inspected host closure'
    return state


def candidate_present(system, current=Path('/run/current-system')):
    """A candidate may be the running system or an imported, registered one.

    A different system (for example another kernel family) is imported over
    the private transport before staging; check() then proves its closure.
    """
    if current.resolve() == Path(system):
        return True
    return subprocess.run(['nix-store', '--check-validity', system],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def prepare(stage):
    os.umask(0o077)
    candidate = json.loads((stage / 'manifest.json').read_text())
    assert candidate['host_inspection'] == 'PASS'
    assert re.fullmatch(r'/nix/store/[a-z0-9]{32}-nixos-system-[A-Za-z0-9._+-]+', candidate['system'])
    assert candidate_present(candidate['system']), 'candidate system is neither running nor registered'
    assert not (stage / 'state.json').exists(), 'preserve an existing trial'
    assert not Path('/nix-path-registration').exists()
    for column, expected in [('FSTYPE', 'ext4'), ('LABEL', 'NIXOS_SD')]:
        assert subprocess.check_output(['findmnt', '-nro', column, '/'], text=True).strip() == expected
    assert subprocess.check_output(['findmnt', '-nro', 'SOURCE', '/boot'], text=True).strip() == '/dev/mmcblk1p1'
    assert shutil.disk_usage('/').free > 200 * 1024**2
    for name, expected in candidate['boot_files'].items():
        assert name in NORMAL_FILES and identity(stage / name) == expected
    backup = stage / 'backup'; backup.mkdir(mode=0o700)
    for name in NORMAL_FILES:
        shutil.copy2(Path('/boot') / name, backup / name)
    profile = str(Path('/nix/var/nix/profiles/system').resolve())
    state = dict(candidate=candidate, normal_profile=profile,
                 normal_files={name: identity(backup / name) for name in NORMAL_FILES},
                 initial_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 stage=str(stage), persistent_boot_selection_changed=False)
    (stage / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    subprocess.run(['nix-store', '--add-root', str(stage / 'system-gc-root'), '-r', candidate['system']],
                   check=True, stdout=subprocess.DEVNULL)
    os.sync()
    return check(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'check'))
    parser.add_argument('stage', type=Path)
    parser.add_argument('--token', default='')
    args = parser.parse_args()
    state = prepare(args.stage) if args.mode == 'prepare' else check(args.stage)
    print('K230_COHERENT_STATE ' + json.dumps(state), flush=True)
    print('K230_COHERENT_READY ' + args.token, flush=True)


if __name__ == '__main__':
    main()
