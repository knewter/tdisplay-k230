All tasks are initially open. Commands naming new tools, tests or flake
outputs below are **planned interfaces**, to be added by that task before
invocation; they are not claims those interfaces exist or have passed
today. Host, cross-build and physical proof are separate. Store committed
results under `docs/evidence/omarchy-themes/` with revisions, commands and
limitations, per this project's own convention.

## 1. Fit-mode choice

- [x] 1.1 Add `FitMode::Fill`/`FitMode::Solid` to
  `background_decode.rs::place()` alongside the existing `Crop`/`Fit`/
  `Center`; `Solid` takes a resolved RGBA color and ignores the source
  image entirely. Verify with new `cargo test --offline --lib
  background_decode` cases covering aspect-distorting fill and a solid-color
  canvas at several sizes.
  Proof (host, 2026-10-16): `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --test background_decode_module` -- 11
  passed, including `fill_stretches_without_letterbox_or_crop_and_differs_from_crop`,
  `solid_paints_one_colour_and_never_opens_the_source` (four sizes up to
  568x1232, missing source file, bound and cache-key checks) and
  `fit_mode_names_round_trip_and_cycle`. (The module's tests live in
  `tests/background_decode_module.rs`, not `--lib`.)
- [x] 1.2 Thread a per-background fit-mode choice from `theme_carousel.rs`/
  `theme_ui.rs`/`main.rs` (today all three hardcode `FitMode::Crop`) through
  to `render`/`render_uncached`, and persist it in
  `tools/theme_preferences.py`'s existing bounded per-source store
  (extend, do not replace, its schema). Verify with
  `cargo test --offline --lib theme_ui` and
  `python3 -m unittest tests.test_theme_preferences`.
  Proof (host, 2026-10-16): `cargo test --offline --lib theme_ui` -- 46
  passed (cycle fit preview-then-activate, failure keeps the old fit, theme or
  background tap supersedes a fit change, heading hit target, `report.json`
  read-back, `FIT_NAMES` pinned to `FitMode::NAMES`); `--test
  theme_catalog_module` 7 passed (the `Fit` request sends `fit` through the
  helper socket in both steps; an unknown mode never reaches it); `--test
  appearance_module` 15 passed (`generation_wallpaper_fit`); `python3 -m
  unittest tests.test_theme_preferences` -- 15 passed (fit remembered per
  source, changes the generation, crop identity unchanged, rollback with a
  rejected ack, corrupt `fits` fails closed, pre-fit files read as crop);
  `tests.test_theme_catalog` and `tests.test_theme_helper_daemon` also pass
  with `--fit`/`--overlays`. Full run: `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --no-fail-fast` -- every target ok,
  including `responsive_pixel_identity` (portrait renders byte-identical).
  Host evidence: `docs/evidence/omarchy-themes/background-fit-modes-host/`
  (one dark and one light theme, all five modes). Not a panel capture.
- [x] 1.3 Resolve the open question in `design.md` (does `Solid` derive from
  the active palette or take an explicit color) and implement accordingly.
  Decided 2026-10-16: `Solid` takes the active generation's resolved
  `background` palette role; no picker. Recorded in `design.md` ("Resolved
  Questions"); verified by the `appearance_module` and
  `background_decode_module` tests above.

Proof: the named host/cargo tests above. No device claim.

## 2. User overlays and video decode

- [x] 2.1 Add user-supplied background overlay staging to
  `tools/theme_activate.py`, bounded and discovered the same way a theme's
  own assets already are (reuse `MAX_ASSET`/`MAX_TOTAL`, `STILLS`/`VIDEOS`
  suffix sets); an overlay lives outside any theme's own content-hashed
  tree (see `design.md`'s own risk note on generation-identity hashing).
  Verify with `python3 -m unittest tests.test_omarchy_theme_activation`
  (new cases for overlay staging/bounds/rejection).
  Proof (host, 2026-10-16): `python3 -m unittest
  tests.test_omarchy_theme_activation` -- 21 passed, including the new
  `UserOverlays` cases: listing/staging/selection beside a theme's own,
  outside the hashed theme tree, an edit or addition makes a new generation,
  unsupported/unsafe/oversized/symlinked/non-regular rejection without failing
  activation, count and total bounds, theme-name collision, symlinked
  directory ignored, remembered overlay choice and its removal diagnostic.
- [ ] 2.2 Add bounded, muted video decode to `background_decode.rs` behind
  its own isolated flake output, `nix build .#handheld-wallpaper`; format
  diagnostics for a recognized-suffix-but-undecodable file surface as a
  named compatibility-report entry, never a crash. Verify with
  `cargo test --offline` for the new decode module and
  `nix build .#handheld-wallpaper --no-link --print-out-paths`.
  Not started in the host pass of 2026-10-16. Finding for whoever takes it:
  the premise above is partly stale -- `nix/rust-shell-client/src/
  video_wallpaper.rs`, `video_status.rs` and `video_visibility.rs` already
  exist (commit `68badde1`: a bounded, muted decoder child process with
  proven-opaque pause and rollback retention), and `main.rs` already plays a
  selected video. What is absent is a `handheld-wallpaper` flake output and
  the named compatibility-report entry for a recognised-suffix-but-
  undecodable file. Reconcile this task with what `68badde1` shipped (and
  with `docs/evidence/omarchy-themes/background-workload-host.md`) before
  writing code, then build the isolated output and run 3.3.
- [ ] 2.3 Add visibility pause (stop decoding/advancing when the wallpaper
  surface is not visible) and reduced-motion behavior (no video autoplay
  when `reduced_motion_enabled`), plus a still-frame or `FitMode::Crop`
  fallback of the theme's own paired still on any decode failure. Verify
  with a new `tests/test_handheld_theme_backgrounds.py --video` (the file
  this scope's parent task named but never created) covering lifecycle,
  pause/resume, reduced-motion and every failure case named above.
  Left open on 2026-10-16: every host test named here is video behaviour (none
  applies to a still background), and see the 2.2 note -- visibility pause
  and a decode-failure still fallback may already exist in `video_visibility.rs`
  and `video_wallpaper.rs`; audit them against this task before adding tests.

Proof: the named host/cargo tests and the isolated `handheld-wallpaper`
build. Video suffix recognition or a first frame is not playback/
performance acceptance.

## 3. Prove it on the actual handheld

- [x] 3.1 Build the full changed system
  (`nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`)
  before any board time; record exact closure and source identities.
  Done 2026-10-16 (host build, after the board runs): master `64481159` →
  `zjdyp4mv…-nixos-system-…`, 1183 paths; see
  `docs/evidence/omarchy-themes/background-fit-modes-board/full-closure-2026-10-16.md`.
- [x] 3.2 On the reserved board, apply each new fit mode to a still
  background; confirm each reads correctly (no unexpected letterboxing,
  stretch, or clipping) with native `grim` captures for at least one dark
  and one light theme.
  Done 2026-10-16 with injected input on HDMI: all five modes on retro-82
  (dark) and catppuccin-latte (light), each captured by `grim` on Home, plus a
  shell-restart persistence check (`docs/evidence/omarchy-themes/background-fit-modes-board/README.md`).
- [ ] 3.3 On the reserved board, run
  `tools/handheld-theme-trial.py --workload backgrounds` against a paired
  static and video background; record combined CPU, RSS, decode/
  presentation cost and card input/frame budgets, and covered-media pause
  and restoration. Compare against this project's existing card CPU/frame
  budgets (the same gate `the-shell-swaps-themes-without-a-python-stall`
  holds itself to). Do not enable video by default in `nix/shell.nix` until
  this passes.
- [x] 3.4 Confirm a user-supplied overlay stages, applies, and survives a
  shell/helper restart on the board, the same way the pinned/bundled
  background test in `docs/evidence/theme-picker/background-selection/README.md`
  already proved for a bundled choice.
  Done 2026-10-16 with injected input on HDMI. The overlay staged as
  `user-overlay-test.png`, applied from the chooser and survived a
  `shell-ui`/`theme-helper` restart; a symlink and a `.txt` file were reported
  under `unknown`. The over-256 MiB case was host-only (same README).

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
