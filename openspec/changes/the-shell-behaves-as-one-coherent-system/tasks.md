Three independent slices (A, B, C) plus a shared evidence/spec task, plus a
fourth slice (E) added later and already implemented. Each slice touches a
disjoint file set and can be implemented, tested, and landed in parallel by
separate worktrees without coordination beyond the usual
`python3 tools/work-status.py` check, per `AGENTS.md`. Slice A's host/QEMU
tasks (A.1-A.3) and slice E's host/QEMU tasks are ticked with their
evidence; slices B and C remain `[ ]` open for a future implementer. Every
slice's board task (A.4, E.4) is left open per `AGENTS.md`'s "do not tick
physical tasks" and the k230-spec-change skill's QEMU-vs-board distinction.

## A. Deck legibility: webOS-fan overview (host, C compositor policy + render)

Superseded 2026-09-25: the user chose the richer webOS-fan direction
(2-3 small cards visible, real icon + app name header per card) over the
originally-scoped "widen the existing single-card peek," on the condition
that it stay the same `CS_DECK` mode/gestures, not a second destination —
see `design.md` decision 1's superseding note. This also folds in the
C-compositor half of `the-handheld-presents-a-coherent-shell` task 1.4
(real card-header icons): that task's own architecture note ("needs a
resolver reachable from the C compositor... build or share an icon
resolver on both sides of the Wayland boundary") is resolved here as an
independent, PNG-only resolver (`nix/card-shell/icon.c`), not a shared
process/library with `nix/rust-shell-client/src/icon.rs` — see that task's
own tracking for whether to unify them later.

- [x] A.1 Choose and record the webOS-fan card size (replacing the prior
  ~8.7%-of-card-width sliver and the originally-scoped "widened peek"):
  `card_width` ≈ 46% of panel width (`.5*(width-2*inset)`), `card_height`
  sized close to the panel's own portrait aspect, `gap=10`, giving 2-3
  cards visible with a >30%-of-card-width neighbor peek at the real
  568×1232 panel. Recorded in `card-shell-policy.c`'s `cs_default_config`
  comments and the policy driver's `overview-geometry` test case (below).
  `valid_config()`'s bounds extended for the new independent
  `entry_card_width`/`entry_card_height` fields and still accept the
  chosen sizes.
- [x] A.2 Update `cs_default_config` and the deck layout math
  (`card-shell-policy.c`) to the webOS-fan size, and split the direct
  bottom-edge app-switch gesture's own geometry into
  `entry_card_width`/`entry_card_height` (a new `cs_entry_target_rect()`,
  used by both `nix/card-shell/adapter.c` call sites that previously fed
  `cs_entry_set_geometry` from the shared `cs_card_rect`) plus a new
  `entry_anchor_shift_y` vertical tracking correction, so the two-axis
  carousel's "full or near-full" feel, 30% threshold, flick velocity and
  1:1 tracking are provably unaffected (`tests/card_shell_policy_driver.c`'s
  `two-axis-entry`/`two-axis-conflicts`/`direct-carousel`/
  `app-switch-swipe`/`tracked-entry`/`tracked-expansion` keep their
  pre-existing numeric assertions unchanged). Also added momentum + snap to
  the deck's own horizontal scroll (`scroll_settling`/`scroll_from_dx`,
  `select_flick_speed`) and two new cases, `overview-geometry` and
  `scroll-momentum`. Verify: `python3 -m unittest test_card_shell_state`
  (run from `tests/`) — 31/31 cases pass.
- [x] A.3 Real card-header icon + name (folding in task 1.4's C-compositor
  half): `nix/card-shell/adapter.c`'s `desktop_identity_icon` (extends the
  existing `.desktop` Name= parser to also read `Icon=` in the same file
  pass) plus new `nix/card-shell/icon.c` (freedesktop icon-theme
  resolution — `index.theme` `Directories=`/`Inherits=` scoring, hicolor
  fallback, `pixmaps/` fallback, PNG-only via Cairo's native decoder, no
  gio/gdk-pixbuf dependency — mirroring `icon.rs`'s algorithm), wired
  through `render.c`'s new `card_icon_header` (real icon, falling back to
  the existing letter badge when none resolves). Verified standalone
  against the real installed Yaru/hicolor icon paths for foot/htop/folder
  before wiring into the build. Card labels/icons stay within `render.c`'s
  existing clipping (`label_clip`, `clip_box`) at the new card width.
  Verify: `nix build .#card-shell --max-jobs 1 --cores 6 --no-link
  --print-out-paths` (succeeds) plus the headless-QEMU captures below.
- [ ] A.4 On a reserved board, confirm the webOS-fan overview (2-3 cards,
  real icons/names, scroll momentum, close, open) is actually legible and
  usable at arm's length with a real theme and real running apps, and that
  the direct bottom-edge app-switch gesture's feel is unchanged. Host/QEMU
  evidence exists (`docs/evidence/card-shell/webos-fan-switcher/`: dark +
  light headless-QEMU captures of the overview, a scroll, a close and an
  open, driven through the real `card_shell test-touch` input path) but is
  explicitly not a substitute — see that evidence's own README for what it
  does and does not show. Operator command: `python3
  tools/capture-feature.py webos-fan-switcher --provenance real-touch
  --duration 30 --description 'webOS-fan card overview: icons, names,
  scroll, close, open' --output-dir
  docs/evidence/card-shell/webos-fan-switcher`. Keep this task open until
  that capture is committed; a host/QEMU render alone does not complete it.

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
