# Kernel finding: the VO's shadow-register commit is not synchronized to scanout

Branch `fix/drm-vblank-latch-and-idle-redraws`, based on `origin/master`
(`fed8fdb2`). Follows the board diagnostic in
`docs/evidence/card-shell/bottom-band-flicker/board-diagnostic.md`, whose
result (installed as `3f1dlarv…`, log at
`/tmp/claude-1000/.../scratchpad/bottom-strip.log`, 74,513 lines, real
finger gestures recorded in `scratchpad/flick4.mkv`) is the evidence this
fix is grounded in:

- **The scene is stable.** Over 7,598 frames, no bottom-strip scene node
  changed visibility frame to frame; only 4-13 state transitions per label
  the whole session (overview enter/exit, drawer map). Content-shaped
  causes (a mistoggling drawer/Home/hint surface) are ruled out.
- **Presents are vblank-aligned.** 7,584 presentation events, interval
  p10/p50 = 19.2ms (exactly the 52.19Hz panel period), p90 = 38.3ms
  (a dropped frame). wlroots' own present-timestamp feedback, driven by
  `drm_crtc_handle_vblank()` from the real hardware IRQ, is clean.
  Composition and the software-visible page-flip timing are not the fault.
- **Renders are occasionally slow.** Median 1.4ms, p90 31.7ms, p99 41.9ms,
  max 81.2ms; 1,145 of 7,598 frames (15%) took over 19.16ms (one refresh
  period), concentrated during gestures (this software Pixman compositor
  building a near-full-screen animated scene, as this project's own
  `perf/card-scaled-cache`, `measure/card-render-cost` etc. lines of work
  already establish is expensive on this CPU).
- **The physical panel still flickers exactly when renders run late,**
  despite composition and present-timestamp reporting both being clean.

## What the driver source shows

`drivers/gpu/drm/canaan/` (pinned `ruyisdk/linux-xuantie-kernel` @
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, `nix/kernel-src.nix`):

- `canaan_crtc_atomic_flush()` (`canaan_crtc.c`) runs on **every** atomic
  commit and, before this change, called `canaan_vo_flush_config(vo)`
  directly: `writel(0x11, vo->reg_base + VO_REG_LOAD_CTL)`. This is a
  synchronous register write at whatever arbitrary point in the current
  scanout the atomic-commit worker happens to run -- driven by wlroots'
  own commit timing, with **no relationship at all** to the panel's actual
  scan position.
- The plane's own per-frame registers (format, size, position, and
  crucially the framebuffer address, `canaan_vo_update_osd()` in
  `canaan_vo.c`) are written earlier in the same commit
  (`canaan_plane_atomic_update` -> `canaan_vo_update_plane` ->
  `canaan_vo_update_osd`), also synchronously, also with no scan-position
  relationship.
- `VO_REG_LOAD_CTL`'s name and its two other call sites both say "this is
  a shadow-register commit/latch trigger, not a per-register apply": it is
  written once at `canaan_vo_enable_crtc()` (after `canaan_vo_set_timing()`
  programs a whole batch of timing registers, committing them together at
  modeset) and once inside `canaan_vo_update_layer1()` (the hardware YUV
  video-overlay path, immediately after that path's own address/size/
  position writes). The OSD path (`canaan_vo_update_osd()`, what wlroots'
  Pixman-rendered desktop actually uses) writes no such bit itself and
  relies entirely on `canaan_crtc_atomic_flush()`'s single, shared,
  synchronous write to commit it.
- The vblank IRQ handler, `canaan_vo_irq_handler()`, does only two things:
  clear `VO_DISP_IRQ_STATUS` and call `drm_crtc_handle_vblank()`. It does
  **no register-apply work of its own** -- it is purely a notification
  path, never the place where the actual plane-register commit happens.
- `drm_crtc_arm_vblank_event()`/`drm_crtc_vblank_get()` in
  `canaan_crtc_atomic_flush()` are correct and unchanged: they already
  defer the userspace-visible completion *event* to the real hardware
  vblank. That part of the driver was never the problem -- it is exactly
  why wlroots' own present timestamps came back clean in the board log.

**Conclusion:** the driver has the plumbing for a real double-buffered,
vblank-synchronized commit (`VO_REG_LOAD_CTL` as a distinct "go" step, kept
separate from the individual register writes, and a working vblank IRQ
already wired into DRM's own event/vblank-counter machinery) -- it just
never connects the two. `VO_REG_LOAD_CTL` fires synchronously at commit
time instead of at the interrupt. Whether the underlying VO hardware
*additionally* has its own internal shadow-latch behavior on that bit is a
question this source reading cannot answer (no datasheet is grounding
here, per `.skills/k230-spec-change/SKILL.md`) -- but the software gives
the bit no chance to matter either way, since it is written at an
arbitrary point in the current frame's scan rather than during the
blanking window the driver's own IRQ line (`VO_DISP_IRQ1_CTL`, computed
from `vtotal` in `canaan_vo_set_timing()`) is positioned at.

This is also consistent with the separately-established, unrelated
`docs/evidence/flicker-after-headroom-revert.md` finding that this panel's
own TE line is never consumed (a free-running host/panel phase). That is a
*display/panel*-side gap this change does not touch; the fix below is
scoped to making the *VO's own* commit timing correct, which is a
necessary condition for correctness regardless of what the panel side
turns out to need later.

## The fix

`nix/patches/canaan-drm-defer-reg-load-to-vblank.patch` (see
`nix/kernel.nix` for where it's added to the pinned kernel's patch list):

- `canaan_crtc_atomic_flush()` now calls a new `canaan_vo_arm_flush(vo)`
  (`atomic_set(&vo->flush_pending, 1)`) instead of writing
  `VO_REG_LOAD_CTL` directly. The per-plane register writes earlier in the
  same commit are unchanged -- only the final "go" write moves.
- `canaan_vo_irq_handler()` now checks `atomic_xchg(&vo->flush_pending, 0)`
  and, if set, calls the existing `canaan_vo_flush_config(vo)` (the actual
  `VO_REG_LOAD_CTL` write) **before** `drm_crtc_handle_vblank()`. The
  actual commit now happens at the hardware's own vblank interrupt --
  exactly where the driver's own IRQ-line timing already says is safe --
  instead of whenever userspace happened to submit the frame.
- Because `canaan_crtc_atomic_flush()` already calls
  `drm_crtc_vblank_get()` for every commit that carries a completion event
  (which is every real wlroots commit), vblank is already guaranteed
  enabled by the time `flush_pending` is set, so the very next hardware
  vblank interrupt is guaranteed to consume it within one frame period.
  `canaan_vo_update_layer1()`'s own separate, immediate `VO_REG_LOAD_CTL`
  write (the hardware video-overlay path) is untouched -- out of scope for
  this report (it isn't implicated in the board evidence, which is about
  the OSD/desktop plane), and touching it risks a real, working feature
  this investigation has no board time to re-verify.

This is the smallest change that makes the existing plumbing do what its
own naming and structure already imply it should: apply the shadow
registers only inside the interrupt the driver author positioned at the
blanking window, and never anywhere else. It cannot make the existing
behavior worse (the write still happens, at most one frame period later,
and only ever exactly once per armed commit); if the VO hardware's own
internal latching already made this bit's timing irrelevant, this change
is inert. If it did not -- which the board symptom (torn/flickering band
specifically on late-render frames) is most consistent with -- this
removes the race.

## What this does not claim

- It does not prove the fix eliminates the flicker; that requires a real
  board re-check (see `docs/evidence/card-shell/bottom-band-flicker/
  kernel-board-test.md`).
- It does not address the separately-established TE/panel free-running
  gap. If the flicker persists after this fix, that gap -- not this one --
  is the next thing to test, per the hypothesis list in
  `docs/evidence/card-shell/bottom-band-flicker/hypotheses.md`.
- It does not touch `canaan_vo_update_layer1()`'s hardware-video-overlay
  commit path.

## Verification performed (host only; no board access)

- Kernel source read: `nix/store/.../drivers/gpu/drm/canaan/{canaan_crtc,
  canaan_vo,canaan_plane}.c` (`nix/kernel-src.nix`'s pin).
- The patch applies cleanly to pristine source (`patch -p1`, dry-run and
  real) and was regenerated the same way this repo's other kernel patches
  are checked in this session.
- `nix build .#kernel --max-jobs 1 --cores 6`: succeeds --
  `/nix/store/43q2v8a8c0jng3ih95lk5xkn7lvyl2cc-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`.
