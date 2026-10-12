#!/usr/bin/env python3
"""Turn tools/panel-target.py's RGB565 target into a U-Boot logo.xrgb.

    tools/panel-target.py --out target.rgb565
    target-to-xrgb.py target.rgb565 logo.xrgb

logo.xrgb is 568x1232 XRGB8888 stored B,G,R,X (nix/boot-splash-image.nix),
exactly 2 799 104 bytes, so U-Boot's stage-1 logo path draws the ArUco
target instead of the logo and tools/panel-measure.py can register it.
"""
import sys
import numpy as np

W, H = 568, 1232
px = np.frombuffer(open(sys.argv[1], 'rb').read(), '<u2')
assert px.size == W * H, px.size
r = ((px >> 11) & 0x1f).astype(np.uint16) * 255 // 31
g = ((px >> 5) & 0x3f).astype(np.uint16) * 255 // 63
b = (px & 0x1f).astype(np.uint16) * 255 // 31
out = np.stack([b, g, r, np.full_like(b, 255)], axis=1).astype(np.uint8).tobytes()
assert len(out) == W * H * 4
open(sys.argv[2], 'wb').write(out)
