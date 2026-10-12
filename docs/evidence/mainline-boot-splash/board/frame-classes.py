#!/usr/bin/env python3
"""Classify every film frame as stage-1 logo, shell, or neither.

    frame-classes.py FILM --logo-ref SECONDS --shell-ref SECONDS [--box Y0 Y1 X0 X1]

Brightness alone is unusable on this bench: room reflections sweep the
glass and move the panel mean by more than a logo-to-terminal change. So
each frame's panel box is reduced to an edge map (Sobel magnitude of a
blurred grey image), which diffuse glare barely changes, and correlated
against the same map of two reference frames from the same film. A frame
is "logo" or "shell" when its correlation with that reference is >= 0.5
and higher than with the other; anything else -- a dark, torn or garbage
frame -- is printed individually with its time.
"""
import argparse
import numpy as np
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("film")
ap.add_argument("--logo-ref", type=float, required=True)
ap.add_argument("--shell-ref", type=float, required=True)
ap.add_argument("--box", type=int, nargs=4, default=(200, 500, 600, 1240))
ap.add_argument("--fps", type=float, default=30.0)
a = ap.parse_args()
y0, y1, x0, x1 = a.box


def edges(f):
    g = cv2.GaussianBlur(cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32), (5, 5), 0)
    e = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    e -= e.mean()
    return e / (np.linalg.norm(e) + 1e-9)


cap = cv2.VideoCapture(a.film)
maps = []
while True:
    ok, f = cap.read()
    if not ok:
        break
    maps.append(edges(f))
ref_l = maps[int(round(a.logo_ref * a.fps))]
ref_s = maps[int(round(a.shell_ref * a.fps))]
cls = []
for m in maps:
    cl, cs = float((m * ref_l).sum()), float((m * ref_s).sum())
    cls.append(("logo" if cl >= cs else "shell") if max(cl, cs) >= 0.5 else "other")
    cls[-1] = (cls[-1], cl, cs)
runs, start = [], 0
for i in range(1, len(cls) + 1):
    if i == len(cls) or cls[i][0] != cls[start][0]:
        runs.append((cls[start][0], start, i - 1)); start = i
print(f"{a.film}: {len(cls)} frames at {a.fps} fps, logo ref {a.logo_ref}s, shell ref {a.shell_ref}s")
for kind, s, e in runs:
    lo = min(c[1] if kind == "logo" else c[2] if kind == "shell" else max(c[1], c[2]) for c in cls[s:e + 1])
    print(f"  {kind:5s} {s / a.fps:8.2f} .. {e / a.fps:8.2f} s  ({e - s + 1} frames, min corr {lo:.2f})")
