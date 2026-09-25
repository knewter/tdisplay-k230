Three independent slices (A, B, C) plus a shared evidence/spec task, plus a
fourth slice (E) added later and already implemented. Each slice touches a
disjoint file set and can be implemented, tested, and landed in parallel by
separate worktrees without coordination beyond the usual
`python3 tools/work-status.py` check, per `AGENTS.md`. Slices A-C's tasks
below are `[ ]` open for a future implementer; slice E's host/QEMU tasks are
ticked with their evidence, its board task is left open per `AGENTS.md`'s
"do not tick physical tasks" and the k230-spec-change skill's QEMU-vs-board
distinction.

## A. Deck legibility (host, C compositor policy + render)

- [ ] A.1 Choose and record a target neighbor-peek fraction (replacing the
  current ~8.7%-of-card-width sliver computed from
  `card_width=.84*(width-48)`, `gap=16`) large enough to show a legible icon
  badge at the existing card-header badge size, with the arithmetic and
  rendered comparison committed under `docs/evidence/`. Verify by computing
  the resulting `pitch`/edge-peek numbers for the real 568×1232 panel and
  confirming `valid_config()`'s existing bounds
  (`card-shell-policy.c:7-28`) still accept them.
- [ ] A.2 Update `cs_default_config` and the deck layout math
  (`card-shell-policy.c:29-38,192-210`) to the chosen peek, without changing
  `cs_entry_motion`/`cs_entry_up_at`'s drag-time geometry (design.md risk
  note — confirm the two-axis carousel's "full or near-full" feel during an
  active drag is unaffected, only the released/idle layout). Verify with
  `python3 -m unittest test_card_shell_state` (run from `tests/`; all
  existing cases must still pass) plus any new case this task adds for the
  new peek geometry.
- [ ] A.3 Confirm card labels/badges at the new card width remain within
  `render.c`'s existing clipping (`label_clip`, `clip_box`) and do not
  overflow into the now-larger neighbor gutter. Verify with
  `nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths`
  and a host render comparison screenshot committed to
  `docs/evidence/card-shell/deck-legibility/`.
- [ ] A.4 On a reserved board, confirm the widened peek is actually legible
  at arm's length with a real theme and real running apps, and that it does
  not regress the two-axis quick-switch drag feel. Operator command:
  `python3 tools/capture-feature.py deck-legibility --provenance real-touch
  --duration 30 --description 'Card overview neighbor peek legibility' 
  --output-dir docs/evidence/card-shell/deck-legibility`. Keep this task
  open until that capture is committed; a host/QEMU render alone does not
  complete it.

## B. Shade quick toggles (host, Rust client)

- [ ] B.1 Add a quick-toggle row to `Route::Shade`'s layout
  (`render.rs`, the `Route::Shade` branch) for brightness step and keyboard
  show/hide, reusing `ControlState`/`ControlValue` exactly as Settings'
  existing rows do (`service_data.rs`). Verify with
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] B.2 Extend `panel_intent`'s `Route::Shade` arm (`service_ui.rs:279-320`)
  with hit-testing for the new toggles, sending the same
  `ServiceRequest::Brightness`/`KeyboardToggle` values Settings already
  sends, gated on the same `ControlState` the Settings row already checks.
  Add unit-test cases mirroring `service_ui.rs`'s existing
  `shade_and_settings_hits_are_bounded_and_cancel_scroll_taps` test. Verify
  with `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`.
- [ ] B.3 Confirm the shade's existing notification scroll, per-item action,
  dismiss-all, and Settings-entry hit regions are unaffected (no region
  overlap with the new toggle row). Verify with the same `cargo test`
  invocation as B.2, plus a host render screenshot of the shade with the new
  row committed to `docs/evidence/coherent-shell/shade-quick-toggles/`.
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

## E. Bottom-edge overlay escape and dismiss-direction consistency (host + QEMU, implemented)

- [x] E.1 Claim the qualified bottom edge band for the compositor's existing
  `cs_begin_entry`/`cs_edge_down` (app-entry) and drawer-reveal recognizers
  even while a Rust overlay (Drawer/Shade/Settings/any sub-page) is mapped,
  instead of unconditionally ceding the touch
  (`nix/card-shell/adapter.c` `input_down`'s `drawer_mapped()` bail); signal
  the overlay to dismiss via the pre-existing `Route::Hide`
  (`card_shell_launch_surface`, now also accepting `"hide"` —
  `nix/card-shell/route.c`); protect the claimed gesture from
  `prepare_impl`'s defensive cancel-on-remap cleanup during the helper's
  asynchronous round-trip via a new `shell.overlay_escaping` flag. Verify:
  `nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths`,
  `python3 tests/test_card_shell_route.py`,
  `python3 -m unittest test_card_shell_state` (run from `tests/`, 29/29,
  unaffected — this task does not touch `card-shell-policy.c`),
  `python3 tests/test_card_touch_routing.py --sway <unwrapped card-shell
  sway>` (7/7 existing cases unaffected), and
  `CARD_SHELL_SWAY=<unwrapped sway> CARD_SHELL_CLIENT=<probe client>
  python3 tests/test_card_shell_two_axis_runtime.py` (already-approved
  two-axis mechanics unaffected).
- [x] E.2 Add a QEMU injected-touch regression exercising the fix directly:
  from Settings mapped over a plain running app, a bottom-edge swipe up
  reaches the overview (`cs_begin_entry` claims it, the overlay unmaps);
  from Settings mapped over a focused app with a second app running, a
  bottom-edge sideways swipe switches directly to the neighbour app; a tap
  on Settings' own top-area Close control is unaffected (no compositor-side
  card entry fires for it); a downward swipe near the top no longer
  dismisses Settings and an upward one does. New test:
  `tests/test_rust_overlay_bottom_escape_runtime.py`. Verify:
  `python3 tests/test_rust_overlay_bottom_escape_runtime.py --sway <unwrapped
  card-shell sway> --rust <handheld-shell-rust k230-shell-rust> --client
  <card-composition-probe-client> --output <dir>`. A negative control against
  the unmodified pre-fix `adapter.c`/`route.c` reproduces the reported bug
  (times out waiting for the compositor to claim the gesture at all). See
  `docs/evidence/coherent-shell/overlay-bottom-escape-qemu/README.md`.
- [x] E.3 Unify Settings' own local dismiss swipe with Shade's (both
  top-anchored sheets reached via the same downward path — upward drag near
  the top dismisses both, sharing `OVERLAY_DISMISS_ZONE_Y`/
  `OVERLAY_DISMISS_DY`); leave the Drawer's bottom-anchored,
  scrolled-to-top-only downward convention unchanged
  (`nix/rust-shell-client/src/service_ui.rs` `panel_intent`). Verify:
  `cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked`
  (172/172 lib tests plus the new
  `service_ui::tests::shade_and_settings_share_one_upward_dismiss_direction`
  case; full workspace 219/219), and E.2's QEMU command (scenarios 3-4 cover
  this end to end with real injected touch, not just the unit model).
- [ ] E.4 On a reserved board, confirm the bottom-edge escape from Settings
  (including the theme chooser and Wi-Fi/password-entry sub-pages) and the
  unified dismiss direction feel right from a real finger: no perceptible
  stall or visual glitch during the overlay's asynchronous dismiss, correct
  destination every time, and the Close/Back controls remain reachable.
  Operator command: `python3 tools/capture-feature.py
  overlay-bottom-escape --provenance real-touch --duration 30 --description
  'Bottom-edge overlay escape and dismiss-direction consistency on glass'
  --output-dir docs/evidence/coherent-shell/overlay-bottom-escape`. Keep
  open until that capture is committed; E.1-E.3's host/QEMU proof does not
  complete this task.

## D. Shared spec/evidence

- [x] D.1 Validate this change: `openspec validate
  the-shell-behaves-as-one-coherent-system --strict`.
- [ ] D.2 After A/B/C's host tasks land, evaluate the integrated closure:
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel`
  (cross-build proof only, not board proof). Slice E's own toplevel
  evaluation was run separately at implementation time (see
  `docs/evidence/coherent-shell/overlay-bottom-escape-qemu/README.md`); this
  task still covers A/B/C together once those land.
- [ ] D.3 Do not archive this change until each slice's board task (A.4,
  B.4, C.4, E.4) is committed, or the coordinator explicitly authorizes
  archiving a subset with the remaining slices split into a named successor
  per `AGENTS.md`'s "close deliberately" guidance.
