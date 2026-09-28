All tasks are initially open. Commands naming new tools, tests or flake
outputs below are **planned interfaces**, to be added by that task before
invocation; they are not claims those interfaces exist or have passed
today. Host, cross-build and physical proof are separate. Store committed
results under `docs/evidence/omarchy-themes/` with revisions, commands and
limitations, per this project's own convention.

## 1. Fit-mode choice

- [ ] 1.1 Add `FitMode::Fill`/`FitMode::Solid` to
  `background_decode.rs::place()` alongside the existing `Crop`/`Fit`/
  `Center`; `Solid` takes a resolved RGBA color and ignores the source
  image entirely. Verify with new `cargo test --offline --lib
  background_decode` cases covering aspect-distorting fill and a solid-color
  canvas at several sizes.
- [ ] 1.2 Thread a per-background fit-mode choice from `theme_carousel.rs`/
  `theme_ui.rs`/`main.rs` (today all three hardcode `FitMode::Crop`) through
  to `render`/`render_uncached`, and persist it in
  `tools/theme_preferences.py`'s existing bounded per-source store
  (extend, do not replace, its schema). Verify with
  `cargo test --offline --lib theme_ui` and
  `python3 -m unittest tests.test_theme_preferences`.
- [ ] 1.3 Resolve the open question in `design.md` (does `Solid` derive from
  the active palette or take an explicit color) and implement accordingly.

Proof: the named host/cargo tests above. No device claim.

## 2. User overlays and video decode

- [ ] 2.1 Add user-supplied background overlay staging to
  `tools/theme_activate.py`, bounded and discovered the same way a theme's
  own assets already are (reuse `MAX_ASSET`/`MAX_TOTAL`, `STILLS`/`VIDEOS`
  suffix sets); an overlay lives outside any theme's own content-hashed
  tree (see `design.md`'s own risk note on generation-identity hashing).
  Verify with `python3 -m unittest tests.test_omarchy_theme_activation`
  (new cases for overlay staging/bounds/rejection).
- [ ] 2.2 Add bounded, muted video decode to `background_decode.rs` behind
  its own isolated flake output, `nix build .#handheld-wallpaper`; format
  diagnostics for a recognized-suffix-but-undecodable file surface as a
  named compatibility-report entry, never a crash. Verify with
  `cargo test --offline` for the new decode module and
  `nix build .#handheld-wallpaper --no-link --print-out-paths`.
- [ ] 2.3 Add visibility pause (stop decoding/advancing when the wallpaper
  surface is not visible) and reduced-motion behavior (no video autoplay
  when `reduced_motion_enabled`), plus a still-frame or `FitMode::Crop`
  fallback of the theme's own paired still on any decode failure. Verify
  with a new `tests/test_handheld_theme_backgrounds.py --video` (the file
  this scope's parent task named but never created) covering lifecycle,
  pause/resume, reduced-motion and every failure case named above.

Proof: the named host/cargo tests and the isolated `handheld-wallpaper`
build. Video suffix recognition or a first frame is not playback/
performance acceptance.

## 3. Prove it on the actual handheld

- [ ] 3.1 Build the full changed system
  (`nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`)
  before any board time; record exact closure and source identities.
- [ ] 3.2 On the reserved board, apply each new fit mode to a still
  background; confirm each reads correctly (no unexpected letterboxing,
  stretch, or clipping) with native `grim` captures for at least one dark
  and one light theme.
- [ ] 3.3 On the reserved board, run
  `tools/handheld-theme-trial.py --workload backgrounds` against a paired
  static and video background; record combined CPU, RSS, decode/
  presentation cost and card input/frame budgets, and covered-media pause
  and restoration. Compare against this project's existing card CPU/frame
  budgets (the same gate `the-shell-swaps-themes-without-a-python-stall`
  holds itself to). Do not enable video by default in `nix/shell.nix` until
  this passes.
- [ ] 3.4 Confirm a user-supplied overlay stages, applies, and survives a
  shell/helper restart on the board, the same way the pinned/bundled
  background test in `docs/evidence/theme-picker/background-selection/README.md`
  already proved for a bundled choice.

Proof: the exact recorded build invocation and reserved-board commands
above, with committed native captures and the workload's own sanitized
result. No flash or full-image readback is inherently required by this
userspace feature.

## 4. Publish evidence and close deliberately

- [ ] 4.1 Publish feature screenshots/video (each fit mode, the overlay
  path, and video playback if enabled), measured limitations and the
  compatibility matrix entries this scope adds; verify site links with
  `python3 scripts/build_site.py`.
- [ ] 4.2 After every required task and physical gate passes, validate,
  archive/sync and push the change; verify `openspec validate --all
  --strict`, then inspect the resulting master/CI/Pages revision. Keep this
  change open if any required consumer or hardware proof is missing.

Proof: `openspec validate --all --strict` and `python3 scripts/build_site.py`,
followed by exact-revision CI and published URL inspection.
