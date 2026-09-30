#!/usr/bin/env python3
"""Compare the production tiled copy against Pixman's affine sampler."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class QuarterTurnPixels(unittest.TestCase):
    def test_pixels_and_fresh_texture_updates(self):
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='pixman-quarter-turn-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(ROOT / 'nix/card-shell'), str(ROOT / 'tests/pixman_quarter_turn.c'),
                            '-o', str(exe), '-lm', *flags], check=True)
            subprocess.run([str(exe)], check=True)
if __name__ == '__main__':
    unittest.main()
