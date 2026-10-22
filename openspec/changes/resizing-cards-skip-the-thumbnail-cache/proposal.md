## Why

With a busy app open, card entry and tap-to-expand presented only on every
second refresh (38.3 ms). Touch acknowledgement for entry had a median of
129 ms. A board profile put 42% of all sampled CPU in sway's `sync_card`.
About half of that was rebuilding the RGB565 thumbnail cache. The cache is
keyed on thumbnail size, and a resizing card has a new size every frame, so
every frame rebuilt a full thumbnail, used it once and then composited it.

## What Changes

- In `nix/card-shell/adapter.c`'s `scaled_mirror`, the cache is skipped while
  the scene is in motion and the card's size differs from the cached
  thumbnail. The mirror then takes the existing direct composite path, which
  ineligible buffers such as video already use.
- Drags, where the size is fixed, keep their cache hits. At rest the cache is
  rebuilt with the bilinear filter, as before.
- Non-goals:
  - changing what cards look like at rest;
  - changing the 15 Hz small-thumbnail cap;
  - opaque regions on sliding surfaces, excluded by the operator on
    2026-10-22.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a performance change within `runtime/card-shell`'s existing
requirement "Every card's small deck thumbnail stays live at a bounded cost",
and its scenario that the overview stays responsive with a fast-committing
card present.

## Impact

`nix/card-shell/adapter.c` only, in the compositor build. Evidence is in
`docs/evidence/interaction-jank/card-resize/`. Proof needs the physical board
for injected card gestures; the cache's own pixel test still covers the
cached path.
