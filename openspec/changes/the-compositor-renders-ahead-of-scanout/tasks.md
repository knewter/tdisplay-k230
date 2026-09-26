## 1. Render deadline

- [x] 1.1 Add `max_render_time 8` to the DSI-1 output line in
  `nix/shell.nix` (commit `ece1ee74`). Verify with `nix build
  .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`
  and by reading the live `k230-sway.conf` on the board (board observation,
  recorded in `docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`).
- [x] 1.2 Board check with real fingers and the camera, on a system that
  still carried the vblank-latch patch: consecutive full-resolution camera
  frames before and after, and the operator's report "it's fixed now"
  (`docs/evidence/card-shell/bottom-band-flicker/max-render-time-fix.md`,
  `before-max-render-time.png`, `after-max-render-time.png`).
- [x] 1.3 Board check on the patch-free kernel with injected gestures and
  the camera: 720 frames with no one-frame spike in the bottom band
  (`kernel-patch-boot-panic.md`, `without-kernel-patch-injected-gestures.png`).
- [ ] 1.4 **Board, real finger.** Operator confirms on a patch-free system
  that bottom-edge app switching and the card overview show no bottom-band
  flicker. Record the report, with the system path, in
  `docs/evidence/card-shell/bottom-band-flicker/` (operator report).

## 2. Specs

- [x] 2.1 Modify the `display/panel` requirement "The panel displays what the
  system draws" with the gesture scenario and its grounding. Verify with
  `openspec validate the-compositor-renders-ahead-of-scanout --strict`.
