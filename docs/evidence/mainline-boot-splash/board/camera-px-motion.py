#!/usr/bin/env python3
"""Unregistered panel motion in camera pixels, as dsi-hsfreqrange-hardcoded.md measured 0x87.

    camera-px-motion.py VIDEO --strip Y0 Y1 X0 X1 [--label TEXT]

The camera has moved since the ArUco bench geometry was set up: the two
far markers are outside the frame, so tools/panel-measure.py cannot
register (it needs three). The 0x87 table it is compared against was
itself measured WITHOUT registration, in camera pixels, with the camera
fixed for the run; this does the same. The strip is a camera-frame box
across the barcode field of tools/panel-target.py, whose bars vary along
panel rows -- which run left to right in this camera's view -- so the
profile is the strip's mean over camera rows, and motion is its lag
against the first frame, using panel-measure's own norm1/shift.
"""
import argparse, importlib.util, sys
from pathlib import Path
import numpy as np
import cv2

root = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("pm", root / "tools" / "panel-measure.py")
pm = importlib.util.module_from_spec(spec); spec.loader.exec_module(pm)

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--strip", type=int, nargs=4, required=True, metavar=("Y0", "Y1", "X0", "X1"))
ap.add_argument("--label", default="measurement")
a = ap.parse_args()
y0, y1, x0, x1 = a.strip
profs, bright = [], []
for g in pm.read_frames(a.video):
    band = g[y0:y1, x0:x1].astype(np.float64)
    profs.append(band.mean(axis=0)); bright.append(band.mean())
profs = np.array(profs); bright = np.array(bright); n = len(profs)
ref = pm.norm1(profs[0])
s = np.array([pm.shift(ref, pm.norm1(p)) for p in profs])
d = np.abs(np.diff(s)); m = bright.mean()
print(f"=== {a.label}  ({n} frames, strip y{y0}:{y1} x{x0}:{x1}, camera px)")
print(f"  motion std {s.std():.2f} px   span {s.max() - s.min():.2f} px")
print(f"  frame-to-frame mean {d.mean():.2f} px   max {d.max():.2f} px   jumps>2 px: {(d > 2).sum()}")
print(f"  brightness range {100 * bright.min() / m:.0f}..{100 * bright.max() / m:.0f}%   mean level {m:.1f}/255")
