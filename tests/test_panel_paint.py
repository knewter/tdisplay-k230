#!/usr/bin/env python3
"""Guarded multi-frame reference checks for the production panel copy."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PanelPaint(unittest.TestCase):
    def test_rotations_padding_alignment_and_live_pixels(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='panel-paint-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/panel_paint.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True, env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})


if __name__ == '__main__':
    unittest.main()
