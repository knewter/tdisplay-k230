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
- [x] 2.2 Add bounded, muted video decode to `background_decode.rs` behind
  its own isolated flake output, `nix build .#handheld-wallpaper`; format
  diagnostics for a recognized-suffix-but-undecodable file surface as a
  named compatibility-report entry, never a crash. Verify with
  `cargo test --offline` for the new decode module and
  `nix build .#handheld-wallpaper --no-link --print-out-paths`.
  Reconciled 2026-10-17 (audit: `docs/evidence/omarchy-themes/background-video-audit.md`).
  The decode already shipped in `68badde1` as `video_wallpaper.rs` (not
  `background_decode.rs`). Added: the `handheld-wallpaper` output
  (`nix/handheld-wallpaper.nix`) -- the minimal ffmpeg/ffprobe pair the decoder
  child runs, NOT a separate Rust crate (the decode module shares the shell
  crate's types; the audit explains why) -- and the named report entry
  (`theme_activate.video_diagnostic`, a line in the report's `unavailable`
  list using the decoder's own category, for theme assets and user overlays).
  Proof (host, 2026-10-17): `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --tests` -- all targets ok (lib 575, bin 23,
  appearance_module 16, new video_wallpaper_module 5); `python3 -m unittest
  tests.test_omarchy_theme_activation` -- 21 ok; `python3
  tests/test_handheld_theme_backgrounds.py --video` -- 11 run, 3 board-only
  skips; `flock /tmp/k230-nix-build.lock nix build .#handheld-wallpaper
  --no-link --print-out-paths --max-jobs 1 --cores 4` -> `/nix/store/fg79cz66dpqhrhm6xf0rcjy3h5c0wqz5-handheld-wallpaper`
  (cross-build only; decodes nothing). Codec check at report time runs only
  when the helper's environment names an absolute `K230_WALLPAPER_FFPROBE`
  <!-- UNVERIFIED: whether the board's theme helper has it -->; otherwise
  play time names the same category.
- [x] 2.3 Add visibility pause (stop decoding/advancing when the wallpaper
  surface is not visible) and reduced-motion behavior (no video autoplay
  when `reduced_motion_enabled`), plus a still-frame or `FitMode::Crop`
  fallback of the theme's own paired still on any decode failure. Verify
  with a new `tests/test_handheld_theme_backgrounds.py --video` (the file
  this scope's parent task named but never created) covering lifecycle,
  pause/resume, reduced-motion and every failure case named above.
  Audited 2026-10-17: the behaviours already existed (`video_visibility.rs`,
  `main.rs`, `video_wallpaper.rs`); added the single `should_decode`
  predicate at all five gates, `appearance::fallback_still`, the stand-in
  decoder lifecycle/failure tests and the test file. Proof (host,
  2026-10-17): `python3 tests/test_handheld_theme_backgrounds.py --video` --
  OK (11 run, 3 skipped): decoder start/stop/restart reaps the child, every
  failure category, the pause predicate, the still fallback, a real host-ffmpeg
  decode of two distinct frames, and the compatibility-report cases. The three
  skips are board-only and stay under 3.3: the compositor's real cover signal
  end to end, the live reduced-motion setting (read once at shell start;
  <!-- UNVERIFIED: live toggle -->), and CPU/frame budgets.

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
  Trial checkpoint 2026-10-21: the named installed-board command completed
  playback/resource sampling and restoration. The original and first-candidate
  cover failures are preserved; corrected source `88f04401` proves opaque-app
  decoder pause/resume and reduced-motion startup on the board. CPU/input/
  release/session-memory checks pass on the named landscape runs, but tracking
  p95 remains about 38.323 ms against 33.334 ms in both still/video arms. No
  performance waiver is inferred; this box remains open. Evidence:
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`.

  Follow-up 2026-10-21: five original-still 8/12/8 ms render-allowance
  diagnostic arms do not resolve the three-card tracking gate (p95 38.310–38.312
  ms). Correlated-input gaps and actual presentation gaps are distinguished;
  no frozen metric is replaced. Normal 8 ms, original still, and landscape
  were restored. Replay and exact commands:
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/tracking-cadence/README.md`.

  Elapsed probe 2026-10-21: benchmark-only source `1a8e72ac` cross-builds and
  runs on the reserved board. Three-card render wall p95 8.946 ms exceeds the
  unchanged 8 ms allowance although CPU passes; commit-return p95 0.776 ms and
  render-start lateness p95 0.521 ms do not isolate a kernel cause. One/three-card
  tracking still fails. The normal compositor/system/still/landscape were
  restored, including independent post-trial checks. Exact commands/results:
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/tracking-elapsed/README.md`.

  Scheduler profile 2026-10-21: untraced/traced/untraced three-card arms on
  the same benchmark compositor retain tracking p95 38.320–38.321 ms. The
  loss-free isolated trace shows main-thread runnable wait p95 2.835 ms
  during render, with no blocked partition there. First-switched-to peer
  labels do not establish causal CPU ownership; logging contention remains
  a hypothesis. Normal system/compositor/still/landscape and trace controls
  were restored and independently audited. This diagnoses task 3.3 without
  closing its frozen performance gate:
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/render-profile/README.md`.

  Logging comparison 2026-10-21: same-binary journal/file/journal three-card
  arms give render elapsed p95 9.181/7.150/9.141 ms and journal-service mean
  CPU 0.103509/0.000868/0.101581 cores. This supports benchmark logging cost;
  file-arm frozen tracking still fails at 38.315 ms. All-present p95 is a
  separate diagnostic, not a replacement gate. The failed first controller
  assertion and complete retry are preserved; normal compositor, journal
  routing, still, landscape, and timers were independently audited restored.
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination/README.md`.

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

- [x] 4.1 Publish feature screenshots/video (each fit mode, the overlay
  path, and video playback if enabled), measured limitations and the
  compatibility matrix entries this scope adds; verify site links with
  `python3 scripts/build_site.py`.
  Done 2026-10-21: linked existing dark/light fit-mode and overlay gallery,
  new native video/fallback/Home captures and a physical panel movie, plus
  explicit compatibility/performance limits. Local site check: 823 pages,
  22,201,074 bytes, 74.27 s, within unchanged limits. Evidence:
  `docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`.
- [ ] 4.2 After every required task and physical gate passes, validate,
  archive/sync and push the change; verify `openspec validate --all
  --strict`, then inspect the resulting master/CI/Pages revision. Keep this
  change open if any required consumer or hardware proof is missing.

Proof: `openspec validate --all --strict` and `python3 scripts/build_site.py`,
followed by exact-revision CI and published URL inspection.
