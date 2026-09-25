# Bottom-band flicker: fixed by `max_render_time 8`

Observed 2026-09-25 on the reserved board.

**System:** `/nix/store/f102jiy0z120519793yk3bx90i6pd138-nixos-system-nixos-26.11.20260919.20b1ddd`,
booted persistently. It includes the VO vblank register-latch patch (`6cec8a3e`).

**Symptom.** During real-finger bottom-edge gestures (app switching and the
card overview), a band about 50 px tall along the panel's short bottom edge
cycled frame to frame between correct, stale-dark and black. The rest of the
panel stayed stable.

**What didn't cause it:**
- The compositor's per-frame bottom-strip log (`board-diagnostic.md`) showed a
  stable scene and vblank-aligned presents.
- The vblank latch fix (`kernel-vblank-latch.md`) left the band unchanged.

**Fix.** `swaymsg output DSI-1 max_render_time 8` was applied at runtime.
The operator then repeated the gestures and reported "it's fixed now". It is
now in `nix/shell.nix`'s Sway output line.

**Evidence:** 30 fps webcam frames, 16 consecutive full-resolution frames
cropped to the bottom end.
- `before-max-render-time.png`: the band cycles, black in frames 3 and 11,
  stale in frames 4–5 and 8–14.
- `after-max-render-time.png`: the edge is clean in all 16 frames.

**Interpretation, not proven.** The VO's end-of-scan fetch competes with the
compositor's rendering for DDR bandwidth. Deferring rendering to 8 ms before
vblank moves that traffic away from the scan of the last lines.
`diag/vo-underrun-and-ddr-qos` has the underflow-status and DMA-arbitration
diagnostics if it recurs.

**Limits.** The "after" frames may not include the heaviest gesture moments.
The acceptance comes from the operator's real-glass report. The cost is up to
8 ms of added input-to-photon latency for a rendered frame.
