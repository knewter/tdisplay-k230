This change was split from `the-shell-behaves-as-one-coherent-system`
(tasks B.1-B.4, C.1-C.4 and the B/C half of D.2). The user authorized this
split on 2026-09-28 ("yes a-d and f"); the parent's own B.1-B.4/C.1-C.4 are
now ticked `[x] ... MOVED, NOT PERFORMED HERE` and cross-reference this
file. Task IDs keep the parent's numbering. B.5 is new: it tracks a parent
requirement that had no task. None of the tasks below are done yet;
authorization only removes the blocker on starting them.

## B. Shade quick toggles (host, Rust client)

- [x] B.1 Add a quick-toggle row to `Route::Shade`'s layout
  (`render.rs`, the `Route::Shade` branch) for keyboard show/hide, reusing
  `ControlState`/`ControlValue` exactly as Settings' existing rows do
  (`service_data.rs`). Brightness is already the shade slider from
  `the-brightness-control-is-a-slider`; do not add a second brightness
  control. Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [x] B.2 Extend `panel_intent`'s `Route::Shade` arm (`service_ui.rs`) with
  hit-testing for the new toggle, sending the same
  `ServiceRequest::KeyboardToggle` value Settings already sends, gated on the
  same `ControlState` the Settings row already checks. Add unit-test cases
  mirroring `service_ui.rs`'s existing
  `shade_and_settings_hits_are_bounded_and_cancel_scroll_taps` test. Verify
  with `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [x] B.3 Confirm the shade's existing notification scroll, per-item action,
  dismiss-all, brightness slider and Settings-entry hit regions are unaffected
  (no region overlap with the new toggle row). Verify with the same
  `cargo test` invocation as B.2, plus a host render screenshot of the shade
  with the new row committed to
  `docs/evidence/coherent-shell/shade-quick-toggles/`.
- [x] B.5 Give every shade tap target, including "Dismiss all" (currently
  `116.0..190.0` in `service_ui.rs`, 74 px), a hit region of at least 99
  logical px (48dp-equivalent) without overlap, and add a unit test asserting
  each region's height. Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [x] B.4 On a reserved board, confirm the toggles are reachable and
  correctly reflect live capability state (including an unavailable
  capability). Operator command: `python3 tools/capture-feature.py
  shade-quick-toggles --provenance real-touch --duration 30 --description
  'Shade quick-toggle reachability and live state' --output-dir
  docs/evidence/coherent-shell/shade-quick-toggles`. Keep open until
  committed.
  2026-10-16: done with **injected events** (uinput pointer and the
  compositor trackpad command) on HDMI 1280x800, not real touch, per the
  user's instruction to inject instead of asking for taps. Covered: reachable,
  toggles the keyboard with the Shade staying open, and shows "Unavailable"
  and ignores a tap once wvkbd is stopped
  (`docs/evidence/coherent-shell/shade-quick-toggles/README.md`, `board/`).
  The DSI panel orientation was not exercised.

## C. Vision accessibility option (host, Rust client + shared theme tokens)

- [x] C.1 Add a text-scale/high-contrast preference to Settings' state
  (`service_data.rs`) and persistence (following the existing theme-choice
  persistence mechanism). Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
  Done 2026-10-16 (host): `tools/theme_vision.py` stores `vision.json` with the
  theme state; see `docs/evidence/coherent-shell/accessibility-scale/README.md`.
- [x] C.2 Thread the chosen scale/contrast through the shared theme-token
  pipeline so both `render.rs` (Home/drawer/shade/Settings) and
  `nix/card-shell/render.c` (card headers) apply it consistently; this is
  the same cross-renderer boundary `webos-polish-review.md` P1-1 already
  names for fonts, so reuse rather than duplicate whatever token-passing
  mechanism that finding's eventual fix establishes if it lands first.
  Verify with `cargo test --manifest-path nix/rust-shell-client/Cargo.toml
  --locked` and `nix build .#card-shell --max-jobs 1 --cores 4 --no-link
  --print-out-paths`.
  Done 2026-10-16 (host): `sections.accessibility` in every generation; Rust
  and card-shell both scale by `text-scale`; high contrast rewrites the palette.
- [x] C.3 Add a Settings UI control to choose the scale/contrast, with a
  host render comparison (default vs. larger text vs. high contrast)
  committed to `docs/evidence/coherent-shell/accessibility-scale/`. Verify
  with the C.1/C.2 commands plus the new screenshots.
  Done 2026-10-16 (host): Settings "Vision ›" page; renders in
  `docs/evidence/coherent-shell/accessibility-scale/host/`.
- [ ] C.4 On a reserved board, confirm the choice persists across a reboot
  and is legibly larger/higher-contrast on the real panel. Operator command:
  `python3 tools/capture-feature.py accessibility-scale --provenance
  real-touch --duration 30 --description 'Text-scale and high-contrast
  option on glass' --output-dir docs/evidence/coherent-shell/accessibility-scale`.
  Keep open until committed.
  Progress 2026-10-16 (board, injected taps + grim, HDMI): toggles apply and
  the choice persists across a soft reboot; see
  `docs/evidence/coherent-shell/accessibility-scale/README.md`. Real-panel
  legibility (glass/camera) is still unrecorded. Panel `grim` captures on
  DSI-1 found the battery ring's percentage overflowing at the larger step;
  fixed by `91a60bfb` and re-captured (same README).
  Result 2026-10-16 (operator on glass, landscape panel): **not legible
  enough.** "the drawer is not particularly legible at 'large' text but also i
  think 'normal and large' is a pretty shitty accessibility option anyway".
  This task stays open for the redesign in C.5–C.8.
- [x] C.5 Replace the two-way text choice with four steps (100/130/160/200%)
  end to end: `tools/theme_vision.py` (`TEXT_SCALES`), the helper protocol
  and Rust `VisionChoice`, `vision_text_scale` (bound raised to 2.0),
  `appearance.c` (its bound too), and the Vision page as a stepped control.
  An existing `large` choice maps to 130%. Verify with the theme Python
  suites and `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml`.
  Done 2026-10-16 on `vision-steps`; see `docs/evidence/coherent-shell/accessibility-scale/README.md` § Redesign.
- [x] C.6 Drawer reflow: tile width, icon size and column count derive from
  the step, labels wrap to two lines before ellipsizing, and the drawer sheet
  is opaque whenever a vision option is set. Verify with a host test that, at
  200% in 568x1232 and 1232x568, no label is ellipsized for the fixture app
  names, tiles do not overlap, and every icon and tap target is at least
  99 px.
  Done 2026-10-16 (host); tests named in the evidence README.
- [x] C.7 Settings, Vision and Shade cards grow with their text, so nothing
  clips at 200%. Verify with host renders at all four steps in both
  orientations, committed to `docs/evidence/coherent-shell/accessibility-scale/`,
  and a test that measures text height against card height.
  Done 2026-10-16 (host); renders in `docs/evidence/coherent-shell/accessibility-scale/steps/`.
- [ ] C.8 Board: at 160% and 200% on the landscape panel, native `grim`
  captures of Home, drawer, Shade, Settings and Vision, and the operator's
  legibility judgement on glass. Closes C.4 if accepted.

## D. Shared spec/evidence

- [x] D.1 Validate this change: `openspec validate
  the-shell-offers-quick-toggles-and-vision-options --strict`. Passed
  2026-09-28 on `close/shell-umbrella`.
- [ ] D.2 After B/C's host tasks land, evaluate the integrated closure:
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`
  (cross-build proof only, not board proof). The parent named the `k230`
  toplevel. The Rust client and card shell are only in the opt-in
  `k230-coherent-shell` configuration, so that configuration is the one that
  exercises this code.
- [ ] D.3 Do not archive until B.4 and C.4 are committed.
