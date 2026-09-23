#!/usr/bin/env python3
"""Host contract check for the opt-in renderer checkpoint.

This checks the explicit source boundary. It does not claim VG-Lite, dma-buf,
scanout, or board behavior.
"""
from pathlib import Path
PATCH = Path(__file__).parents[1] / "nix/patches/wlroots-vglite-full-pass-pixman.patch"
NIX = Path(__file__).parents[1] / "nix/wlroots-vglite.nix"
SOURCE = Path(__file__).parents[1] / "nix/wlroots-vglite/renderer.c"
text = PATCH.read_text()
assert '\t\t"vglite",' in text
assert 'strcmp(renderer_name, "vglite")' in text
assert 'wlr_pixman_renderer_create()' in text
assert 'VG-Lite experiment selected' in text
assert 'drmSetMaster' not in text and 'drmModeSetCrtc' not in text
source = SOURCE.read_text()
assert 'vg_lite_map' in source and 'vg_lite_finish' in source
assert 'wlr_render_pass_add_texture' in source
assert 'target_cache_to_gpu' in source
assert 'VG_LITE_RGBA8888' in source
assert 'vg_lite_blit(' in source
assert 'K230_VGLITE_ALLOW_UNPROVEN_CACHE' in source
nix = NIX.read_text()
assert 'WLR_RENDERER=vglite' in nix
assert 'real-rgb565-rect-shm-upload-route-with-pixman-fallback' in nix
print("VGLITE_FALLBACK_CONTRACT=PASS")
print("VGLITE_FALLBACK_SCOPE=real-rgb565-rect-shm-upload-route-with-fail-closed-full-pass-fallback")
