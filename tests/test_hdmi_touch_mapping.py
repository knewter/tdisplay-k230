#!/usr/bin/env python3
"""Check the Nix HDMI calibration through real native wlroots touch/cursor APIs.

No Wayland socket is bound. Contacts and the libinput affine calibration step
are simulated; this does not verify physical glass or installation on the board.
Pass a configured and built pinned wlroots source tree with Pixman/headless.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wlroots-source', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, default=Path('.scratch/touch-mapping'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source = args.wlroots_source.resolve()
    library = source / 'builddir/libwlroots-0.20.so'
    if not library.is_file():
        parser.error('expected a built pinned native libwlroots-0.20.so in builddir')
    build = args.build_dir.resolve(); build.mkdir(parents=True, exist_ok=True)
    binary = build / 'probe'
    # The regression control intentionally asserts. Never leave a core dump.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    command = [os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
               '-DWLR_USE_UNSTABLE', f'-I{source}/include', f'-I{source}/builddir/include',
               str(root / 'tests/hdmi_touch_mapping.c'), str(library),
               f'-Wl,-rpath,{source}/builddir',
               *shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
                                                    'wayland-server', 'pixman-1'], text=True)),
               '-o', str(binary)]
    subprocess.run(command, check=True, timeout=60)
    expression = 'map (t: { transform = t; matrix = import ./nix/hdmi-touch-calibration.nix t; }) [ "normal" "90" "180" "270" ]'
    rows = json.loads(subprocess.check_output(['nix-instantiate', '--eval', '--strict', '--json',
                                               '--expr', expression], cwd=root, text=True, timeout=15))
    # Sway converts clockwise CLI rotations to inverse Wayland enums.
    enums = {'normal': 0, '90': 3, '180': 2, '270': 1}
    results = []
    for row in rows:
        transform = row['transform']; enum = enums[transform]
        argv = [str(binary), str(enum), *row['matrix'].split()]
        result = subprocess.run(argv, check=True, text=True, capture_output=True, timeout=10)
        print(result.stdout.strip())
        regression = None
        if transform != 'normal':
            old = subprocess.run([str(binary), str(enum), '1', '0', '0', '0', '1', '0'],
                                 text=True, capture_output=True, timeout=10)
            assert old.returncode == -signal.SIGABRT and 'actual_x-x' in old.stderr, (
                'uncalibrated control did not fail the expected coordinate assertion', transform, old.returncode)
            regression = 'uncalibrated mapping rejected by coordinate assertion'
        results.append({'sway_transform': transform, 'wlroots_enum': enum, 'matrix': row['matrix'],
                        'points': 9, 'down_and_motion_events': 18, 'result': 'PASS',
                        'old_mapping_control': regression})
    report = {'result': 'PASS', 'evidence_class': 'native-wlroots-simulated-contact-mapping',
              'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
              'cursor_source_sha256': hashlib.sha256((source/'types/wlr_cursor.c').read_bytes()).hexdigest(),
              'runs': results,
              'limits': ['Libinput affine calibration is simulated before the real wlroots cursor signals.',
                         'No physical touch, panel, HDMI scanout or installed NixOS profile was exercised.']}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS all four Nix calibrations preserve glass axes, corners and layout coordinates')


if __name__ == '__main__':
    main()
