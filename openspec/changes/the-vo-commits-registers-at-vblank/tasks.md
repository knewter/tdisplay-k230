## 1. Kernel driver read and fix

- [x] 1.1 Read `drivers/gpu/drm/canaan/{canaan_crtc,canaan_plane,canaan_vo}.c`
  (pinned `nix/kernel-src.nix` source) and confirm whether the VO's
  framebuffer/shadow-register commit is latched at vblank or applied at
  arbitrary atomic-commit time; record the finding with file:line citations.
  Verify with `docs/evidence/card-shell/bottom-band-flicker/
  kernel-vblank-latch.md`.
- [x] 1.2 Implement the minimal fix: defer the `VO_REG_LOAD_CTL` shadow-
  register commit write from `canaan_crtc_atomic_flush()` into
  `canaan_vo_irq_handler()` (the real vblank interrupt), via a new
  `canaan_vo_arm_flush()`/`flush_pending` pair. Leave the per-plane
  register writes, the DRM completion-event arming, and the separate
  hardware-video-overlay commit path unchanged.
  `nix/patches/canaan-drm-defer-reg-load-to-vblank.patch`, added to
  `nix/kernel.nix`. Verify with `nix build .#kernel --max-jobs 1 --cores 6`.
- [x] 1.3 Build the full image with the patched kernel. Verify with
  `nix build .#sdImage --max-jobs 1 --cores 6`.

## 2. Stop scheduling idle frames

- [x] 2.1 Narrow `tick_impl`'s `wlr_output_schedule_frame()` call
  (`nix/card-shell/adapter.c`) to fire only while a touch/drag is active
  or a time-based card-shell animation (entry settle/reverse, expand,
  close timeout) is actually progressing, not for the whole time the
  overview happens to be open. Verify with `nix build .#card-shell
  --max-jobs 1 --cores 6` and `python3 -m unittest test_card_shell_state`
  (run from `tests/`, unaffected).
- [x] 2.2 Confirm this does not regress the approved gesture feel: a real
  animated-gesture QEMU regression
  (`tests/test_rust_overlay_bottom_escape_runtime.py`, which exercises the
  bottom-edge entry/switch/close gestures against the real Rust client)
  still passes. <!-- UNVERIFIED: this confirms the gesture still *works*
  under injected touch; it does not measure the idle frame-rate reduction
  itself, which needs a board repeat of the diagnostic
  (docs/evidence/card-shell/bottom-band-flicker/board-diagnostic.md) to
  quantify. -->

## 3. Specs

- [x] 3.1 Add the `display/panel` requirement delta (grounding paragraph
  and a new scenario) in this change. Verify with `openspec validate
  the-vo-commits-registers-at-vblank --strict`.

## 4. Outstanding (hardware-only; keep this change open until done)

- [x] 4.1 Board re-check: flash the image built in 1.3 (
  `docs/evidence/card-shell/bottom-band-flicker/kernel-board-test.md` has
  the exact commands and a card-reader fallback), confirm the new kernel
  is running (`uname -a`), and repeat the real-finger bottom-edge gesture
  with the camera and/or the bottom-strip diagnostic
  (`SWAY_K230_CARD_BOTTOM_STRIP_DEBUG=1`, from
  `diag/bottom-strip-frame-debug`, if that branch's compositor changes are
  also on the flashed image) to see whether the flickering band is gone,
  reduced, or unchanged. Not performed here: no board/`/dev/ttyACM0`
  access in this task.
  Result (2026-09-25, board camera frames plus operator report): the
  patched kernel ran as system `f102jiy0` and the band was unchanged; see
  `docs/evidence/card-shell/bottom-band-flicker/max-render-time-fix.md`.

## 5. Withdrawn from the build

- [x] 5.1 Remove `canaan-drm-defer-reg-load-to-vblank.patch` from
  `nix/kernel.nix`. The patch did not fix the flicker (Sway
  `max_render_time 8` did), and a kernel carrying it panicked at boot once
  in two attempts (`docs/evidence/card-shell/bottom-band-flicker/
  kernel-patch-boot-panic.md`). Verify with `nix build .#sdImage-coherent
  --max-jobs 1 --cores 6`.
- [ ] 5.2 Board: boot the patch-free kernel persistently and confirm on
  camera that the bottom band stays stable with `max_render_time 8` alone.
- [ ] 5.3 Decide this change's fate: its `display/panel` delta describes a
  vblank-latched commit that the shipped kernel no longer performs, so it
  must not be archived as written. Drop the change or rewrite the delta.
