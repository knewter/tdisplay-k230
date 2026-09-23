#!/usr/bin/env python3
"""Host contract check for the opt-in renderer checkpoint.

This checks the explicit source boundary. It does not claim VG-Lite, dma-buf,
scanout, or board behavior.
"""
from pathlib import Path
PATCH = Path(__file__).parents[1] / "nix/patches/wlroots-vglite-full-pass-pixman.patch"
NIX = Path(__file__).parents[1] / "nix/wlroots-vglite.nix"
text = PATCH.read_text()
assert 'strcmp(renderer_name, "vglite")' in text
assert 'wlr_pixman_renderer_create()' in text
assert 'full-pass Pixman fallback' in text
assert 'drmSetMaster' not in text and 'drmModeSetCrtc' not in text
nix = NIX.read_text()
assert 'WLR_RENDERER=vglite' in nix
assert 'no-gpu-claim' in nix
print("VGLITE_FALLBACK_CONTRACT=PASS")
print("VGLITE_FALLBACK_SCOPE=selection-and-full-pass-pixman-only")
