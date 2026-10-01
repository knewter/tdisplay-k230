Three independent slices (A, B, C) plus a shared evidence/spec task, plus a
fourth slice (E) added later and already implemented. Each slice touches a
disjoint file set and can be implemented, tested, and landed in parallel by
separate worktrees without coordination beyond the usual
`python3 tools/work-status.py` check, per `AGENTS.md`. Slice A's host/QEMU
tasks (A.1-A.3) and slice E's host/QEMU tasks are ticked with their
evidence. Every slice's board task (A.4, E.4) is left open per `AGENTS.md`'s
"do not tick physical tasks" and the k230-spec-change skill's QEMU-vs-board
distinction.

**Slices B and C moved 2026-09-28** (user-authorized scope split, "yes a-d
and f"): every B/C task (B.1-B.4, C.1-C.4) is now ticked
`[x] ... MOVED, NOT PERFORMED HERE` and carried forward verbatim into the
successor `the-shell-offers-quick-toggles-and-vision-options`. No B/C code
exists in this change; the tick means the task's ownership moved, not that
the work was performed here. This parent's `runtime/device-settings` and
`runtime/notification-center` spec deltas, which existed solely for slices
B/C, have been removed from this change (they now live only in the
successor).

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
- [x] A.5 Board-driven polish pass (two coordinator messages, one carrying a
  real board report from installed `w51crww9`, one a real-glass scroll
  report): (a) cards were too small (~45% of the panel's own height per
  the board, sitting flush under the title with about half the panel
  empty below) — resized to ~50% of the panel width and 60% of its height
  (55-65% requested), vertically centered between the title and the
  footer hint via a new `card_top_offset` (`cs_card_rect`'s y anchor,
  replacing a fixed `inset` there only — `inset` itself and
  `cs_entry_target_rect` are unchanged), with a new `entry_anchor_shift_y`
  term correcting the direct-switch gesture's y-tracking for the resulting
  overview/entry y-offset mismatch (previously only height was corrected).
  (b) Icon/label sizes increased (32-40px icon, a 20px label consistent
  with the chrome's own type scale, ellipsis already handled by the
  existing Pango layout). (c) The overview's own card raises to the top of
  its scene stacking order in `CS_DECK`, not just `CS_ENTERING`/
  `CS_EXPANDING`, as a defensive z-order fix. (d) The board report's real
  gap — "Monitor" showed a letter badge, not a real icon, under the real
  installed theme — was PNG-only decoding missing an SVG-only resolution
  path; `nix/card-shell/icon.c` now decodes SVG via librsvg (linked
  directly, the same two calls `icon.rs` uses, no gio/gdk-pixbuf), and
  follows the active theme's own `icon_theme` (`report.json`, via
  `appearance_apply`), not just `K230_ICON_THEME`. (e) The real-glass
  scroll report — "i can't flick to swipe through multiple cards quickly,
  it snaps to each card as i go" — was the deck's momentum coast being
  limited to ±1 card; replaced with a velocity-projected physics fling
  (`CS_SCROLL_OMEGA`) that can carry several cards, reusing the direct
  bottom-edge app-switch gesture's own recency-windowed velocity estimator
  (`touch_window_span`, factored out of `entry_release_velocity`) via a
  separate `scroll_history` buffer; a slow release still snaps to the
  nearest card; a fresh touch mid-coast catches it and continues 1:1 (no
  jump, via a new `cs_down` catch path); the ends clamp with a soft
  rubber band (a damped, shorter coast), not a hard stop. Also fixed a
  latent bug this pass's own QEMU capture caught: `adapter.c`'s runtime
  card-height recompute had its own stale copy of an old fraction that
  silently overrode the policy default. Verify: `python3 -m unittest
  test_card_shell_state` (run from `tests/`) — 34/34 cases pass, including
  four new scroll-physics cases (`scroll-fling-multi-card`,
  `scroll-slow-release-snaps-nearest`, `scroll-catch-mid-coast`,
  `scroll-end-clamp-soft`) and every direct-switch case with unchanged
  numeric assertions; `nix build .#card-shell --max-jobs 1 --cores 6`
  succeeds; recaptured headless-QEMU evidence
  (`docs/evidence/card-shell/webos-fan-switcher/`, dark+light) with an
  "ordinary maximized" app-window fixture (`card_shell ordinary`,
  `floating enable`, `resize set 100 ppt 100 ppt`, `move position 0 0`,
  matching production) that also incidentally resolved an odd-looking
  overlapping-card artifact and a broken composite "opened" frame in the
  prior capture generation, both traced to that earlier capture's smaller,
  inconsistent floating-window fixture size, not to card-shell itself.
- [x] A.4 Record the operator's 2026-10-01 acceptance that coherent shell behavior seems fine and should close. Retain earlier fan-switcher source/QEMU evidence. The user waives further camera capture; do not claim a newly recorded per-case legibility/momentum trial.

## B. Shade quick toggles (host, Rust client)

- [x] B.1 MOVED, NOT PERFORMED HERE: add a quick-toggle row to `Route::Shade`'s layout
  (`render.rs`, the `Route::Shade` branch) for brightness step and keyboard
  show/hide, reusing `ControlState`/`ControlValue` exactly as Settings'
  existing rows do (`service_data.rs`). **Scope split authorized by the user
  on 2026-09-28 ("yes a-d and f")**: carried forward into the successor
  `the-shell-offers-quick-toggles-and-vision-options`'s own task B.1, which
  also records that the brightness half is superseded by the shade slider
  `the-brightness-control-is-a-slider` already added -- only the
  keyboard-toggle half remains to build there. Nothing here is implemented;
  that work is not done, only relocated.
- [x] B.2 MOVED, NOT PERFORMED HERE: extend `panel_intent`'s `Route::Shade` arm (`service_ui.rs:279-320`)
  with hit-testing for the new toggles, sending the same
  `ServiceRequest::Brightness`/`KeyboardToggle` values Settings already
  sends, gated on the same `ControlState` the Settings row already checks.
  Carried forward into the successor's own task B.2 (keyboard-toggle only,
  brightness already superseded per B.1's note).
- [x] B.3 MOVED, NOT PERFORMED HERE: confirm the shade's existing notification scroll, per-item action,
  dismiss-all, and Settings-entry hit regions are unaffected (no region
  overlap with the new toggle row). Carried forward into the successor's own
  task B.3.
- [x] B.4 MOVED, NOT PERFORMED HERE: on a reserved board, confirm the toggles are reachable and
  correctly reflect live capability state (including an unavailable
  capability). Carried forward into the successor's own task B.4.

## C. Vision accessibility option (host, Rust client + shared theme tokens)

- [x] C.1 MOVED, NOT PERFORMED HERE: add a text-scale/high-contrast preference to Settings' state
  (`service_data.rs`) and persistence (following the existing theme-choice
  persistence mechanism). **Scope split authorized by the user on 2026-09-28
  ("yes a-d and f")**: carried forward verbatim into the successor
  `the-shell-offers-quick-toggles-and-vision-options`'s own task C.1.
- [x] C.2 MOVED, NOT PERFORMED HERE: thread the chosen scale/contrast through the shared theme-token
  pipeline so both `render.rs` (Home/drawer/shade/Settings) and
  `nix/card-shell/render.c` (card headers) apply it consistently; this is
  the same cross-renderer boundary `webos-polish-review.md` P1-1 already
  names for fonts, so reuse rather than duplicate whatever token-passing
  mechanism that finding's eventual fix establishes if it lands first.
  Carried forward into the successor's own task C.2.
- [x] C.3 MOVED, NOT PERFORMED HERE: add a Settings UI control to choose the scale/contrast, with a
  host render comparison (default vs. larger text vs. high contrast)
  committed to `docs/evidence/coherent-shell/accessibility-scale/`. Carried
  forward into the successor's own task C.3.
- [x] C.4 MOVED, NOT PERFORMED HERE: on a reserved board, confirm the choice persists across a reboot
  and is legibly larger/higher-contrast on the real panel. Carried forward
  into the successor's own task C.4. No part of slices B or C has been
  implemented by this change; that work is not done, only relocated.

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
- [x] E.4 Record the same physical operator acceptance for coherent shell behavior, retaining overlay-bottom-escape source/QEMU evidence. Additional Settings-subpage gesture captures are waived; no fresh per-subpage latency trial is claimed.

## D. Shared spec/evidence

- [x] D.1 Validate this change: `openspec validate
  the-shell-behaves-as-one-coherent-system --strict`.
- [x] D.2 Run `nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link --print-out-paths --max-jobs 2 --cores 8`: passed, producing `/nix/store/p0gzcaa6bfqblzzqdcfpqznmq8x2wd28-nixos-system-nixos-26.11.20260919.20b1ddd`. Cross-build only, not deployment or boot proof. Source base `ea40ee5d` contains the accepted implementation.

- [x] D.3 Close A/E using the committed operator acceptance and capture waiver. Preserve the previously authorized B/C successor `the-shell-offers-quick-toggles-and-vision-options`; this archive makes no claim that its quick-toggle/accessibility work is finished.


## Accepted closeout, 2026-10-01

The updated completed tasks describe actual acceptance, waivers and scope
transfer, not execution of the superseded protocols. See `docs/evidence/proposal-closeout/2026-10-01/coherent.md`.
Historical checkpoint notes above that say physical gates remain open are
superseded by this record. Quantitative or individually unreported results
are not promoted to physical proof.

Proof: `openspec validate the-shell-behaves-as-one-coherent-system --strict`; committed operator report;
`python3 scripts/render_work_board.py --working-tree --output <snapshot.json>`.
