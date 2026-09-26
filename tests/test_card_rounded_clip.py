"""Compare the production Pixman clip to an independent full-mask oracle."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class RoundedClipPixels(unittest.TestCase):
    def test_pixman_composition(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='card-rounded-clip-') as tmp:
            exe = Path(tmp) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                '-Werror', '-I' + str(ROOT / 'nix/card-shell'),
                str(ROOT / 'tests/card_rounded_clip.c'), '-o', str(exe), '-lm', *flags], check=True)
            subprocess.run([str(exe)], check=True)

if __name__ == '__main__':
    unittest.main()
