## Why

A person choosing a background today gets exactly one placement (a centered
cover-crop) and exactly one media kind (a still image) — regardless of what
the active theme or their own overlay would actually look like fit,
letterboxed, or as a muted video. `the-shell-loads-omarchy-themes`'s own
task 4.1 asked for "crop/fit/fill/center/solid choices" and "user overlays,"
and task 4.3 asked for "bounded muted video backgrounds"; neither shipped.
`nix/rust-shell-client/src/background_decode.rs` already implements
`FitMode::Crop`/`Fit`/`Center`, but every call site
(`theme_thumbnails.rs`, `main.rs`, `theme_ui.rs`) hardcodes `FitMode::Crop`
— nothing lets a person choose, `Fill`/`Solid` don't exist at all, and there
is no video decode path (the module's own doc comment says so outright).

This is a scope split under `AGENTS.md`'s "Close OpenSpec changes
deliberately": `the-shell-loads-omarchy-themes` is otherwise close to done
(the closeout audit dated 2026-09-28 found the coordinator, activation,
transaction, keyboard and app-appearance adapters implemented and
host-tested, with the daily-use dark/light/community theme cases already
proved on the board). Background presentation is real, separable,
substantially-sized feature work — not a rounding error, and not something
that should either block that change's remaining board gates or tempt
someone into ticking 4.1/4.3 against partial delivery.

## What Changes

- Extend `background_decode.rs`'s existing `place()` with two more
  variants: `Fill` (cover the full canvas without preserving aspect ratio —
  distinct from `Crop`, which preserves it) and `Solid` (an explicit flat
  color, for a theme or a person who wants no image at all). `Crop`/`Fit`/
  `Center` are unchanged.
- Let a person actually pick a fit mode per background, persisted the same
  way `tools/theme_preferences.py` already persists a background choice
  (source-relative, hash-keyed, bounded). No new palette format, no new
  activation path, no new build slot.
- Add user-supplied background overlays: a person's own image file, staged
  and bounded the same way `theme_activate.py` already bounds a theme's own
  `MAX_ASSET`/`MAX_TOTAL` staged assets, discovered alongside a theme's
  bundled choices rather than replacing them.
- Add bounded, muted video backgrounds: format diagnostics (recognized
  suffix but undecodable content is a named, reported failure, not a
  crash), pause when the surface is not visible, a still-frame or `Crop`
  fallback on any decode failure, and reduced-motion behavior (no video
  autoplay when the system's reduced-motion setting is active — the same
  flag `protocol.rs`/`service_ui.rs` already thread through for animation
  duration). Performance is a physical gate: this proposal does not enable
  video by default until the reserved-board workload (task group 3 below)
  passes the existing card CPU/frame budgets.

**Non-goals:** a general-purpose image editor or crop tool (fit modes are a
fixed enum, not a draggable crop rectangle); animated GIF backgrounds
(`STILLS` already excludes them from `theme_activate.py`'s asset
recognition; out of scope here); changing what counts as a still versus a
video (`tools/theme_activate.py`'s existing `STILLS`/`VIDEOS` suffix sets
are reused unchanged); redesigning the chooser UI itself
(`nix/rust-shell-client/src/theme_ui.rs`'s carousel and tap-to-apply model,
from the sibling change, are unchanged — this only adds a fit-mode/overlay
affordance to the existing background row).

## Capabilities

### New Capabilities

None. This targets the same `runtime/shell-themes` capability
`the-shell-loads-omarchy-themes` already proposed. Neither change has
archived, so `openspec/specs/runtime/shell-themes/` does not exist yet;
this change's own delta therefore also uses `ADDED Requirements`, scoped to
exactly the fit-mode/overlay/video scope this proposal implements, rather
than restating the parent's broader requirement. Whichever of the sibling
proposals for this capability archives first fixes the base spec; the
others then sync against it normally.

## Impact

`nix/rust-shell-client/src/background_decode.rs` (new `FitMode` variants,
video decode path), `theme_carousel.rs`/`theme_ui.rs`/`main.rs` (fit-mode
selection wiring, all three currently hardcode `Crop`), `tools/theme_activate.py`
(overlay staging, video format diagnostics surfaced in the compatibility
report), `tools/theme_preferences.py` (persist a fit-mode choice alongside
the existing background choice), and a new `nix build .#handheld-wallpaper`
isolated output for the video decode path specifically, so it can be built
and evaluated for cost independently of the rest of the theme package.
Host-provable: fit-mode placement math, overlay staging/bounds, and video
format diagnostics all need no board. Whether video playback actually meets
this project's existing card CPU/frame budgets, and whether any fit mode
reads correctly on the panel, still needs the reserved board — this
proposal does not claim that gate closed by construction, and does not
enable video backgrounds by default until it passes.
