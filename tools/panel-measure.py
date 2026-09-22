#!/usr/bin/env python3
"""Measure panel image motion in real panel rows, via ArUco registration.

The panel is photographed at a steep oblique angle, so raw camera pixels
mean different numbers of panel rows at the two ends -- about 2.7x
across this panel. Two earlier analyses reported a jitter "gradient down
the frame" that was entirely that perspective. So nothing here is
measured in camera pixels: every frame is warped into panel space first,
using the four ArUco markers drawn by tools/panel-target.py.

THE HOMOGRAPHY IS FITTED ONCE AND THEN HELD FIXED. The markers are
themselves on the moving display; re-fitting per frame would let them
absorb the motion under investigation and report a confident zero.

  tools/panel-measure.py --record 20 --label "hsfreq 0x96"
  tools/panel-measure.py --video some.mp4
"""
import argparse, subprocess, sys, tempfile, os
import numpy as np
import cv2

W, H = 568, 1232
DICT = cv2.aruco.DICT_4X4_50
MARKERS = {0: (100, 90, 66), 1: (468, 90, 66),
           2: (150, 1070, 150), 3: (418, 1070, 150)}
FIELD = (250, 940, 170, 398)


def panel_corners(mid):
    cx, cy, s = MARKERS[mid]
    h = s // 2
    return np.float32([[cx - h, cy - h], [cx + h, cy - h],
                       [cx + h, cy + h], [cx - h, cy + h]])


def read_frames(path):
    cap = cv2.VideoCapture(path)
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    return fr


def fit_homography(frames):
    """Camera -> panel homography, fitted ONCE and held fixed.

    Three markers are enough: each contributes four corners, so three
    give twelve correspondences against the four a homography needs.
    Requiring all four made the tool refuse to run whenever one marker
    was clipped by the frame edge or covered by a finger, which is a
    routine occurrence and not an error.

    Markers are accumulated independently rather than only from frames
    where every one was visible -- the board is static, so a corner seen
    in any frame is evidence about the same fixed geometry.
    """
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT),
                                  cv2.aruco.DetectorParameters())
    acc = {k: [] for k in MARKERS}
    step = max(1, len(frames) // 200)
    for g in frames[::step]:
        corners, ids, _ = det.detectMarkers(g)
        if ids is None:
            continue
        for i, c in zip(ids.flatten(), corners):
            k = int(i)
            if k in acc:
                acc[k].append(c[0])
    usable = {k: v for k, v in acc.items() if len(v) >= 3}
    if len(usable) < 3:
        return None, usable
    src, dst = [], []
    for k, lst in sorted(usable.items()):
        src.append(np.median(np.array(lst), axis=0))
        dst.append(panel_corners(k))
    src = np.concatenate(src).astype(np.float32)
    dst = np.concatenate(dst).astype(np.float32)
    Hm, _ = cv2.findHomography(src, dst, 0)
    return Hm, usable


def norm1(p, k=41):
    ker = np.ones(k) / k
    b = np.convolve(np.pad(p, (k // 2, k // 2), mode="edge"), ker, mode="valid")[:len(p)]
    return (p - b) / (np.abs(b).mean() + 1e-9)


def shift(a, b, maxlag=40):
    a = a - a.mean(); b = b - b.mean(); cc = {}
    for L in range(-maxlag, maxlag + 1):
        if L < 0:   x, y = a[-L:], b[:len(b) + L]
        elif L > 0: x, y = a[:len(a) - L], b[L:]
        else:       x, y = a, b
        if len(x) < 80:
            continue
        cc[L] = np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-12)
    L = max(cc, key=cc.get)
    if L - 1 in cc and L + 1 in cc:
        a1, a2, a3 = cc[L - 1], cc[L], cc[L + 1]
        return L + (a1 - a3) / (2 * (a1 - 2 * a2 + a3) + 1e-12)
    return float(L)


def measure(frames, label):
    Hm, usable = fit_homography(frames)
    if Hm is None:
        print("%s: only %d marker(s) usable %s -- need 3 to register"
              % (label, len(usable), sorted(usable)))
        return None
    r0, r1, c0, c1 = FIELD
    profs, bright = [], []
    for g in frames:
        r = cv2.warpPerspective(g, Hm, (W, H))
        band = r[r0:r1, c0 + 25:c1 - 25].astype(np.float64)
        profs.append(band.mean(axis=1)); bright.append(band.mean())
    profs = np.array(profs); bright = np.array(bright); n = len(profs)
    ref = norm1(profs[0])
    s = np.array([shift(ref, norm1(profs[k])) for k in range(n)])
    half = (r1 - r0) // 2
    near = np.array([shift(norm1(profs[0][:half]), norm1(profs[k][:half])) for k in range(n)])
    far  = np.array([shift(norm1(profs[0][half:]), norm1(profs[k][half:])) for k in range(n)])
    m = bright.mean()
    print("\n=== %s   (%d frames, markers %s)"
          % (label, n, ", ".join("%d:%dx" % (k, len(v)) for k, v in sorted(usable.items()))))
    print("  motion   std %.2f panel rows   span %.2f   p5..p95 %.2f..%.2f"
          % (s.std(), s.max() - s.min(), np.percentile(s, 5), np.percentile(s, 95)))
    print("  near half std %.2f   far half std %.2f   ratio %.2f   corr %.3f"
          % (near.std(), far.std(), far.std() / max(near.std(), 1e-9),
             np.corrcoef(near, far)[0, 1]))
    d = np.abs(np.diff(s))
    print("  frame-to-frame  mean %.2f  max %.2f rows   jumps>3 rows: %d" % (d.mean(), d.max(), (d > 3).sum()))
    print("  brightness  min %.0f%%  max %.0f%%  std %.2f" % (100 * bright.min() / m, 100 * bright.max() / m, bright.std()))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video")
    ap.add_argument("--record", type=int, default=0, help="seconds to capture from /dev/video0")
    ap.add_argument("--label", default="measurement")
    ap.add_argument("--dev", default="/dev/video0")
    a = ap.parse_args()
    path = a.video
    if a.record:
        for c in (("auto_exposure", 1), ("exposure_time_absolute", 200)):
            subprocess.run(["v4l2-ctl", "-d", a.dev, "--set-ctrl=%s=%d" % c],
                           capture_output=True)
        path = os.path.join(tempfile.mkdtemp(), "cap.mp4")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "v4l2",
                        "-input_format", "mjpeg", "-video_size", "1280x720",
                        "-framerate", "30", "-i", a.dev, "-t", str(a.record),
                        "-y", path], check=True)
    if not path:
        print("need --video or --record"); return 2
    return 0 if measure(read_frames(path), a.label) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
