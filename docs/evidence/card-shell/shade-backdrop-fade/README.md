# Shade backdrop: stationary, eased fade (board check)

Evidence class: board webcam recording with **injected** touch, not a real
finger. Captured 2026-09-25.

- System: `x1a9yzxv…-nixos-system-nixos-26.11.20260919.20b1ddd`,
  test-activated over `x2glknys` (patch-free kernel). The running client was
  `ih1apdra…-k230-shell-rust`, which is in that closure.
- Input: `slow-shade.sh` (in this directory) ran on the board against the
  evemu clone of the touchscreen. It pulls from the top edge to y≈620 in 31
  steps 80 ms apart, holds 1.5 s, drags back to y≈200, then pulls to y≈1000
  and releases.
- Recording: 22 s, 1280×720 MJPEG at 30 fps, from the camera at the device's
  top edge. In the frames, the panel's top is on the left.

What the frames show:

- `injected-slow-drag-2fps.png` (2 fps): the tray grows from the left, and
  the uncovered part of the screen darkens gradually as it does.
- `injected-mid-drag.png` (t = 3.2 s, full resolution): one uniform dim over
  the whole uncovered area, with no band moving with the tray edge.
- Luminance of a 150×70 crop near the panel's bottom end, per frame:
  - 100.3 at rest, falling steadily to 85.4 by the hold at 4.4 s;
  - flat during the hold;
  - rising back to 97.3 as the drag returns up (6.0–9.4 s);
  - falling to about 84 on the full pull.
  Across 660 frames there is no frame-to-frame change larger than 5 levels,
  so the dim tracks the drag and never pops.

Not obtained: a real-finger session, and the settle animations viewed frame
by frame.
