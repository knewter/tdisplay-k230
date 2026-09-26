## Why

During real-finger bottom-edge gestures and in the card overview, a band
about 50 px tall along the panel's bottom edge cycled between the correct
image, a stale-dark frame and black. The compositor's scene and DRM present
timestamps stayed clean, so the fault lies below composition, in scanout.

This change replaces the withdrawn change `the-vo-commits-registers-at-vblank`.
That change deferred the VO's shadow-register commit to the vblank interrupt
(`nix/patches/canaan-drm-defer-reg-load-to-vblank.patch`). On the board the
patch left the band unchanged, and a kernel carrying it panicked at boot once
in two attempts. The patch is no longer applied. Its evidence stays under
`docs/evidence/card-shell/bottom-band-flicker/`, and its history is in git.
The operator approved dropping it on 2026-09-25.

## What Changes

- Sway's output line gains `max_render_time 8` (in `nix/shell.nix`, commit
  `ece1ee74`), so composition starts about 8 ms before each vblank instead
  of right after the previous one. The flicker stopped once this was applied.
- The `display/panel` requirement's grounding records this fix and its
  evidence, replacing the unverified vblank-latch text.

## Capabilities

### Modified Capabilities

- `display/panel`: "The panel displays what the system draws" gains a
  scenario for continuous gesture animation and its grounding.

## Impact

- `nix/shell.nix` (already landed). No kernel, device-tree or boot change.
- If a frame needs more than about 8 ms to render, it can miss its vblank and
  the previous frame repeats. That is preferable to a torn band.
