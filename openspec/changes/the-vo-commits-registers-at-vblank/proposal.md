## Why

A user swiping between apps and opening the app switcher on real glass saw a
flickering band across the panel's bottom ~50-100 px, specifically during
gestures. Camera evidence (splitting the panel into twelve strips along its
long axis) shows the two strips nearest the bottom alternating brightness
frame to frame; every other strip is stable. A board-side scene/render/
present diagnostic (`docs/evidence/card-shell/bottom-band-flicker/
board-diagnostic.md`) then showed the *compositor* is not the cause: no
scene node toggles visibility frame to frame, and DRM presentation
timestamps stay cleanly vblank-periodic (19.2 ms, matching 52.19 Hz)
throughout. But 15% of frames took longer than one refresh period to
render, concentrated during the same gestures, and the panel flickers
specifically then -- while the software-visible "presented" signal stays
clean. That gap is between composition and the glass.

## What Changes

Reading the pinned vendor kernel's DRM driver
(`drivers/gpu/drm/canaan/{canaan_crtc,canaan_plane,canaan_vo}.c`) found that
`canaan_crtc_atomic_flush()` writes the VO's shadow-register commit bit
(`VO_REG_LOAD_CTL`) synchronously, at whatever arbitrary point in the
current scanout the atomic-commit worker happens to run -- not at the
vblank interrupt, which does no register-apply work of its own. The
DRM-visible completion event is correctly deferred to the real vblank
already (`drm_crtc_arm_vblank_event`/`drm_crtc_handle_vblank`); only the
register commit itself is not. Defer that one write into the vblank IRQ
handler instead, so it always happens where the driver's own IRQ-line
timing already says is safe, regardless of how late a frame's render ran.
See `docs/evidence/card-shell/bottom-band-flicker/kernel-vblank-latch.md`
for the full reasoning and its limits (this driver-side gap is real
regardless of whether the previously-identified, separate panel-side gap --
the RM69A10's Tearing-Effect line is never consumed,
`docs/evidence/flicker-after-headroom-revert.md` -- turns out to be the
dominant cause; this change does not touch that).

Separately, the same diagnostic found the compositor rendering continuously
at ~42 fps even during idle stretches. `card_shell`'s own per-16ms tick
was one contributor: it called `wlr_output_schedule_frame()` for the
entire time the overview was open, whether or not anything in it was
actually animating. Narrow that to only schedule while a touch/drag is
active or a time-based animation (entry settle/reverse, expand, close
timeout) is actually progressing. This reduces render load and the odds
of a late frame, without changing input-driven redraw (which already goes
through `handle_result`'s own synchronous path) or the approved gesture
feel -- verified against the existing card-shell test suites and a real
animated-gesture QEMU regression.

## Capabilities

### Modified Capabilities

- `display/panel`: extends "The panel displays what the system draws"
  with the VO shadow-register commit-timing finding and fix, alongside
  the requirement's existing, still-open TE/free-running-panel-scan note.

## Impact

- `nix/patches/canaan-drm-defer-reg-load-to-vblank.patch` (new),
  `nix/kernel.nix` (adds it to the pinned kernel's patch list).
- `nix/card-shell/adapter.c` (`tick_impl`'s frame-scheduling condition).
- No device-tree change. No change to any userspace behavior other than
  render/schedule timing (card-shell's own test suites, unaffected,
  confirm this).
- This is a kernel change: it needs a full image rebuild, flash, and
  reboot to take effect -- see `docs/evidence/card-shell/
  bottom-band-flicker/kernel-board-test.md` for the exact commands and a
  fallback (card-reader) flash path. QEMU's `k230` machine models no
  display pipeline, so board evidence is the only thing that can close
  this; it remains open until that repeat is run.
