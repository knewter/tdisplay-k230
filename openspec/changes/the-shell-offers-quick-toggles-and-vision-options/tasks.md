This change was split from `the-shell-behaves-as-one-coherent-system`
(tasks B.1-B.4, C.1-C.4 and the B/C half of D.2). It is staged pending the
user's authorization of that split. Task IDs keep the parent's numbering.
B.5 is new: it tracks a parent requirement that had no task.

## B. Shade quick toggles (host, Rust client)

- [ ] B.1 Add a quick-toggle row to `Route::Shade`'s layout
  (`render.rs`, the `Route::Shade` branch) for keyboard show/hide, reusing
  `ControlState`/`ControlValue` exactly as Settings' existing rows do
  (`service_data.rs`). Brightness is already the shade slider from
  `the-brightness-control-is-a-slider`; do not add a second brightness
  control. Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] B.2 Extend `panel_intent`'s `Route::Shade` arm (`service_ui.rs`) with
  hit-testing for the new toggle, sending the same
  `ServiceRequest::KeyboardToggle` value Settings already sends, gated on the
  same `ControlState` the Settings row already checks. Add unit-test cases
  mirroring `service_ui.rs`'s existing
  `shade_and_settings_hits_are_bounded_and_cancel_scroll_taps` test. Verify
  with `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] B.3 Confirm the shade's existing notification scroll, per-item action,
  dismiss-all, brightness slider and Settings-entry hit regions are unaffected
  (no region overlap with the new toggle row). Verify with the same
  `cargo test` invocation as B.2, plus a host render screenshot of the shade
  with the new row committed to
  `docs/evidence/coherent-shell/shade-quick-toggles/`.
- [ ] B.5 Give every shade tap target, including "Dismiss all" (currently
  `116.0..190.0` in `service_ui.rs`, 74 px), a hit region of at least 99
  logical px (48dp-equivalent) without overlap, and add a unit test asserting
  each region's height. Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] B.4 On a reserved board, confirm the toggles are reachable and
  correctly reflect live capability state (including an unavailable
  capability). Operator command: `python3 tools/capture-feature.py
  shade-quick-toggles --provenance real-touch --duration 30 --description
  'Shade quick-toggle reachability and live state' --output-dir
  docs/evidence/coherent-shell/shade-quick-toggles`. Keep open until
  committed.

## C. Vision accessibility option (host, Rust client + shared theme tokens)

- [ ] C.1 Add a text-scale/high-contrast preference to Settings' state
  (`service_data.rs`) and persistence (following the existing theme-choice
  persistence mechanism). Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] C.2 Thread the chosen scale/contrast through the shared theme-token
  pipeline so both `render.rs` (Home/drawer/shade/Settings) and
  `nix/card-shell/render.c` (card headers) apply it consistently; this is
  the same cross-renderer boundary `webos-polish-review.md` P1-1 already
  names for fonts, so reuse rather than duplicate whatever token-passing
  mechanism that finding's eventual fix establishes if it lands first.
  Verify with `cargo test --manifest-path nix/rust-shell-client/Cargo.toml
  --locked` and `nix build .#card-shell --max-jobs 1 --cores 4 --no-link
  --print-out-paths`.
- [ ] C.3 Add a Settings UI control to choose the scale/contrast, with a
  host render comparison (default vs. larger text vs. high contrast)
  committed to `docs/evidence/coherent-shell/accessibility-scale/`. Verify
  with the C.1/C.2 commands plus the new screenshots.
- [ ] C.4 On a reserved board, confirm the choice persists across a reboot
  and is legibly larger/higher-contrast on the real panel. Operator command:
  `python3 tools/capture-feature.py accessibility-scale --provenance
  real-touch --duration 30 --description 'Text-scale and high-contrast
  option on glass' --output-dir docs/evidence/coherent-shell/accessibility-scale`.
  Keep open until committed.

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
