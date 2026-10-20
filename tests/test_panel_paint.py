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
    def test_label_ink_preserves_glyph_pixels_clips_and_alpha(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1', 'pangocairo'], text=True))
        with tempfile.TemporaryDirectory(prefix='label-ink-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/panel_label_ink.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True,
                           env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})

    def test_rotations_padding_alignment_and_live_pixels(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1', 'libdrm'], text=True))
        with tempfile.TemporaryDirectory(prefix='panel-paint-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/panel_paint.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True, env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})

    def test_full_precision_cache_corners_damage_and_output_guard(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1', 'libdrm'], text=True))
        with tempfile.TemporaryDirectory(prefix='panel-cache-') as directory:
            include = Path(directory) / 'sway'
            include.mkdir()
            (include / 'card_shell_scaled_cache.h').symlink_to(ROOT / 'nix/card-shell/scaled-cache.h')
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + directory, '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/panel_cache.c'),
                            str(ROOT / 'nix/card-shell/scaled-cache.c'),
                            '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True,
                           env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})

    def test_unscaled_rgb565_conversion_clip_and_alpha_fallback(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='rgb565-blit-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/rgb565_blit.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True,
                           env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})


    def test_retained_output_damage_buffer_age_and_failure_lifetime(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='output-damage-') as directory:
            (Path(directory) / 'k230_quarter_turn.h').symlink_to(ROOT / 'nix/card-shell/quarter-turn.h')
            for fixture in ['panel_output_cache_state.c', 'panel_output_damage.c']:
                exe = Path(directory) / fixture.removesuffix('.c')
                subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                                '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                                '-I' + directory, '-I' + str(ROOT / 'nix/card-shell'),
                                str(ROOT / 'tests' / fixture), '-o', str(exe), *flags], check=True)
                subprocess.run([str(exe)], check=True,
                               env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})


    def test_opaque_interiors_keep_precise_corners_and_budget(self):
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'pixman-1'], text=True))
        with tempfile.TemporaryDirectory(prefix='opaque-interior-') as directory:
            exe = Path(directory) / 'pixels'
            subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2',
                            '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
                            '-I' + str(ROOT / 'nix/card-shell'),
                            str(ROOT / 'tests/panel_opaque_interior.c'), '-o', str(exe), *flags], check=True)
            subprocess.run([str(exe)], check=True,
                           env={**os.environ, 'UBSAN_OPTIONS': 'halt_on_error=1'})


if __name__ == '__main__':
    unittest.main()
