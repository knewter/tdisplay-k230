#!/usr/bin/env python3
"""Build the panel registration target: four ArUco markers + a test field.

WHY ARUCO RATHER THAN PLAIN BLOCKS

Registration used to be four bright squares whose approximate positions
were typed in by hand after looking at a frame. That broke twice, both
times silently: once when the detector locked onto specular highlights
on the worktop and cheerfully rectified a picture of the table, and
once when the board was nudged and the hardcoded search windows no
longer contained the markers. A marker that carries its own identity
cannot do either -- it is found or it is not, it says which corner it
is, and it gives four sub-pixel corners instead of one centroid, so
the homography is fitted from sixteen correspondences rather than four.

WHY THE MARKERS ARE DIFFERENT SIZES

The camera looks at the panel from the device's top edge, so panel row
0 is NEAREST and row 1232 is furthest, at roughly 1.05 against 0.39
camera px per panel px -- about 2.7x. Markers drawn the same size would
render 2.7x apart and the far pair drops below the detector's size
floor, which is exactly what happened. So the far pair is drawn larger
to land at a similar size on the sensor.

  tools/panel-target.py --out target.fb          # default: barcode field
  tools/panel-target.py --out t.fb --field solid
"""
import argparse, random, struct, sys
import numpy as np
import cv2

W, H = 568, 1232
DICT = cv2.aruco.DICT_4X4_50

# (id, centre col, centre row, size in panel px). ids 0,1 near; 2,3 far.
# Sizes are multiples of 6. DICT_4X4 renders 4 data cells plus a 1-cell
# black border on each side = 6 cells across; a size that is not a
# multiple of 6 puts cell edges on fractional pixels, and the decoder
# then reads the bits wrong after any perspective warp. Symptom is the
# worst kind: quads are found and all of them are rejected.
MARKERS = [
    (0, 100,  90,   66),
    (1, 468,  90,   66),
    (2, 150, 1070, 150),
    (3, 418, 1070, 150),
]
# The barcode field lives between them.
FIELD = (250, 940, 170, 398)          # row0, row1, col0, col1


def marker_panel_corners(mid):
    """The marker's four corners in panel (col,row), in ArUco's order:
    top-left, top-right, bottom-right, bottom-left."""
    for i, cx, cy, s in MARKERS:
        if i == mid:
            h = s // 2
            return np.float32([[cx - h, cy - h], [cx + h, cy - h],
                               [cx + h, cy + h], [cx - h, cy + h]])
    return None


def build(field="barcode", seed=20260921):
    img = np.zeros((H, W), np.uint8)
    d = cv2.aruco.getPredefinedDictionary(DICT)
    for mid, cx, cy, s in MARKERS:
        m = cv2.aruco.generateImageMarker(d, mid, s)
        # The quiet zone has to be GENEROUS, not token. A marker is found
        # by locating its black border against a lighter surround; on an
        # unlit panel everything outside is black, so a thin white ring
        # lets the border merge into the background and every candidate
        # quad is rejected. s // 3 keeps the border properly enclosed.
        q = max(8, s // 3)
        y0, x0 = cy - s // 2, cx - s // 2
        img[y0 - q:y0 + s + q, x0 - q:x0 + s + q] = 255
        img[y0:y0 + s, x0:x0 + s] = m

    r0, r1, c0, c1 = FIELD
    if field == "barcode":
        rnd = random.Random(seed)
        r = r0
        while r < r1:
            b = rnd.randint(4, 14)
            v = 255 if rnd.random() < 0.5 else 0
            img[r:min(r + b, r1), c0:c1] = v
            r += b
    elif field == "solid":
        img[r0:r1, c0:c1] = 255

    # 8-bit grey -> RGB565
    v = img.astype(np.uint16)
    rgb = ((v >> 3) << 11) | ((v >> 2) << 5) | (v >> 3)
    return rgb.astype('<u2').tobytes(), img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--field", default="barcode", choices=["barcode", "solid", "none"])
    ap.add_argument("--png", help="also write a preview PNG")
    a = ap.parse_args()
    buf, grey = build(a.field)
    assert len(buf) == W * H * 2, len(buf)
    open(a.out, "wb").write(buf)
    if a.png:
        cv2.imwrite(a.png, grey)
    # Prove the markers we just drew are actually detectable.
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICT),
                                  cv2.aruco.DetectorParameters())
    corners, ids, _ = det.detectMarkers(grey)
    found = sorted(int(i) for i in ids.flatten()) if ids is not None else []
    print("%s: %d bytes, field=%s, markers drawn %s, self-detected %s"
          % (a.out, len(buf), a.field, [m[0] for m in MARKERS], found))
    if found != sorted(m[0] for m in MARKERS):
        print("FAIL: not all markers are detectable in the source image")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
