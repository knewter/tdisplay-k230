## Context

A band about 50 px tall at the panel's bottom edge flickered during bottom-edge
gestures. The compositor's scene and present timing were clean
(`docs/evidence/card-shell/bottom-band-flicker/board-diagnostic.md`). The
pinned vendor DRM driver writes the VO's shadow-register commit bit
(`VO_REG_LOAD_CTL`) at atomic-commit time, not at vblank
(`kernel-vblank-latch.md`).

## Goals / Non-Goals

**Goals:**

- Remove the bottom-band flicker on real glass.
- Stop scheduling compositor frames while nothing animates.

**Non-Goals:**

- Rewriting the vendor VO driver beyond the single register-commit write.
- Changing the hardware video overlay's own commit path.

## Decisions

1. Defer the `VO_REG_LOAD_CTL` write into the vblank IRQ handler
   (`nix/patches/canaan-drm-defer-reg-load-to-vblank.patch`). **Withdrawn:**
   on the board this left the band unchanged, and a kernel carrying it
   panicked at boot once in two attempts
   (`kernel-patch-boot-panic.md`). The patch is no longer applied in
   `nix/kernel.nix`.
2. Set Sway `max_render_time 8` on `DSI-1`. This removed the band on the
   board (`max-render-time-fix.md`) and on the patch-free kernel under
   injected gestures (`kernel-patch-boot-panic.md`).
3. Narrow `tick_impl`'s frame scheduling to active touches and running
   animations. This decision is kept.

## Risks / Trade-offs

- `max_render_time 8` starts composition later in each refresh. A frame that
  needs more than about 8 ms can miss its vblank and repeat the previous
  frame, which is preferable to a torn band.
- The root cause below composition (scanout or DDR bandwidth near the end of
  the scan) is inferred, not measured.
- This change's `display/panel` delta still describes a vblank-latched
  commit. Task 5.3 must rewrite or drop it before archive.
