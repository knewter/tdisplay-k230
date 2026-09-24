"""Compare cached pixels to the pinned Pixman direct composite path."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScaledCachePixels(unittest.TestCase):
    def test_opaque_bilinear_rgb565_and_reused_source(self):
        with tempfile.TemporaryDirectory(prefix='card-scaled-cache-') as tmp:
            include = Path(tmp) / 'sway'
            include.mkdir()
            (include / 'card_shell_scaled_cache.h').symlink_to(ROOT / 'nix/card-shell/scaled-cache.h')
            flags = shlex.split(subprocess.check_output(
                ['pkg-config', '--cflags', '--libs', 'pixman-1', 'libdrm'], text=True))
            exe = Path(tmp) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra',
                            '-Werror', '-I' + tmp,
                            str(ROOT / 'nix/card-shell/scaled-cache.c'),
                            str(ROOT / 'tests/card_scaled_cache.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
