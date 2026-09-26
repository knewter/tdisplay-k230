# Shade drag-to-close (board check)

Evidence class: board webcam recording with **injected** touch, not a real
finger. Captured 2026-09-25.

- System: `yb815pr0…-nixos-system-nixos-26.11.20260919.20b1ddd`
  (`fix/shade-drag-to-close` at `ac6dc11d`), test-activated over `x1a9yzxv`.
- Input: `close-test.sh` (in this directory), run on the board against the
  evemu touchscreen clone. It opens the shade, then:
  - drags slowly up from the backdrop (y 1100→400, 15 px per 60 ms), holds
    0.8 s, releases;
  - reopens, drags up only 90 px, releases;
  - taps the backdrop at y 1150.
- Recording: 38 s, 1280×720 MJPEG at 30 fps. In the frames, the panel's top
  is on the left. `injected-close-sequence-2fps.png` covers 3–16.5 s.

The tray's edge was tracked per frame along one camera row (x = the
strongest light-to-dim step):

| Phase (video time) | What was measured |
| --- | --- |
| Slow close, 4.3–9.2 s | Edge moves steadily 810 → 363 px with the finger, then leaves the measured span. Mean brightness rises gradually (126 → 143) as the backdrop fades through the release settle. No jumps. |
| Short drag, 20.0–21.5 s | Edge follows to 713 and holds. On release it eases back open: 723, 769, 797, 808, 810 on consecutive frames. |
| Backdrop tap, 23.90 s | The sheet closes over about 3 frames (811, 724, 403, gone). |

Not obtained: a real-finger session, and a fling-velocity close.
