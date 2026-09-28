## 1. Cross-page drag: dwell timing, fling, new-page creation

- [x] 1.1 `home_pager::HomePager::set_position` -- an external, un-animated
  position setter (clamped, clears velocity/settle) that `home_screen`'s own
  eased driver calls every tick, distinct from `set_page`'s instant integer
  jump; verify with
  `cargo test --offline -p k230-shell-rust home_pager::tests::set_position_clamps_and_clears_velocity_and_settle`.
- [x] 1.2 `home_screen`: `EDGE_ZONE_PX` narrowed to 40px;
  `EDGE_HOLD_FIRST_MS`/`EDGE_HOLD_REPEAT_MS` (380ms/260ms) replace the old
  single 550ms constant; `PageSwitchAnim` drives every edge-hold/fling page
  turn as a smooth eased slide instead of an instant jump;
  `note_drag_point`/`maybe_fling`/`advance_edge_hold` shared by both the
  internal (touch-tracked) and external (drawer-origin) drag paths; verify
  with
  `cargo test --offline -p k230-shell-rust home_screen::tests::edge_hold_does_not_switch_before_the_first_dwell_threshold home_screen::tests::edge_hold_repeats_with_a_shorter_delay_than_the_first_turn home_screen::tests::a_quick_horizontal_fling_mid_drag_pages_immediately_without_an_edge_dwell`.
- [x] 1.3 `HomeLayout::add_blank_page` plus `advance_edge_hold`'s own
  last-page-edge branch: holding at the true last page's right edge creates
  a brand-new empty page and slides onto it; verify with
  `cargo test --offline -p k230-shell-rust home_state::tests::add_blank_page_always_appends_even_when_the_last_page_has_room home_screen::tests::edge_hold_at_the_last_page_creates_a_new_page_instead_of_stalling`.
- [x] 1.4 `HomeLayout::would_fit`/`HomeScreen::drop_target_fits`: a live
  drag's drop target now distinguishes an ordinary accepting cell from one
  that cannot fit the dragged item's span; verify with
  `cargo test --offline -p k230-shell-rust home_state::tests::would_fit_matches_fits_at_for_an_existing_page_and_always_allows_a_future_one home_screen::tests::dragging_a_widget_over_another_widgets_full_span_shows_no_room`.
- [x] 1.5 `render.rs`: `paint_edge_page_indicator` (themed edge glow plus a
  growing chevron, driven by `HomeScreen::drag_edge_indicator`'s dwell
  progress), enlarged page dots while any drag is live, and
  `paint_drop_target`'s dashed "no room" style (the theme's error role);
  verify with the host evidence harness (task 3) and
  `cargo build --offline -p k230-shell-rust`.
  QEMU/board coverage: not attempted this pass -- see task 3's note on why
  (the sibling change's own QEMU driver was silently terminated on this
  same shared machine across three prior attempts); UNVERIFIED on real
  touch/panel.

## 2. Widget visual redesign

- [x] 2.1 `home_state::WidgetKind` gains `ClockMinimal`/`ClockAnalog`
  (additive to the schema-2 tag, no migration needed), `WidgetKind::ALL`
  and the picker's row list/count are derived from it rather than hand-typed
  literals; verify with
  `cargo test --offline -p k230-shell-rust home_state::tests::the_three_clock_styles_have_their_documented_spans_and_are_all_pickable`.
- [x] 2.2 `home_widgets::weather` rewritten onto wttr.in's `j1` format:
  `WeatherSnapshot` carries location, current temperature/feels-like,
  today's high/low, and up to 5 forecast entries; `parse_wttr_j1` selects
  forecast entries starting at the current hour and spilling into the next
  day; the 30-minute throttle, disk cache, and offline-keeps-last-reading
  behavior are unchanged; verify with
  `cargo test --offline -p k230-shell-rust home_widgets::weather`.
- [x] 2.3 `render.rs::paint_widget_card` redesigned per kind: two hero clock
  styles (`hero_line`/`caption_line`) plus a drawn analog face
  (`draw_analog_clock`); a battery ring with a charging badge
  (`draw_battery_ring`/`draw_bolt`/`ring_percent_label`) and a muted outline
  glyph for the absent state (`draw_battery_outline`); a weather card with a
  Cairo-drawn condition glyph per family (`draw_weather_glyph`/
  `cloud_shape`), a condition-tinted wash derived from theme colors
  (`paint_condition_tint`/`weather_tint`), and a 3-entry forecast strip.
  Every widget shares one dedicated, borderless surface treatment
  (`paint_widget_surface`, 16px radius matching `docs/design/
  shell-polish-review-2026-09.md`'s "sheet" token, a theme-derived filled
  surface, a cheap layered soft shadow, no border stroke) instead of the
  bordered `service_card` every other panel still uses; verify with
  `cargo build --offline -p k230-shell-rust` and the host evidence harness
  (task 3).
  **Board-review follow-up (same pass):** the coordinator deployed the
  first pass to the board and flagged, from the host evidence alone: the
  weather tint leaking past its rounded corners (now clipped -- see
  `design.md` decision 8), a 1px border reading as "boxed-in" (replaced by
  `paint_widget_surface` -- decision 9), an oversized battery ring with an
  external percentage caption (scaled down ~30%, percentage now centered
  inside the ring via `ring_percent_label`, charging moved to a small
  accent badge), the "Big stacked" clock cramped with equal-weight lines
  (more left inset, Normal-weight minute beneath a Bold accent hour, a
  larger date caption), and a forecast strip too small at arm's length
  (larger glyphs/temperature, more vertical room). All five re-verified via
  `cargo test --offline`/`cargo clippy --offline --all-targets` and the
  re-rendered host evidence (task 3).
- [x] 2.4 Widget-picker previews render each widget kind's actual live
  content inline in its own row (`paint_widget_picker`'s preview
  thumbnail), not a static icon; verify with the host evidence harness
  (task 3), `dark-widget-picker.png`/`light-widget-picker.png`.

## 3. Evidence: host render harness

- [x] 3.1 `nix/rust-shell-client/examples/render_widget_evidence.rs`: calls
  the real, unmodified `render::paint_home` offscreen against two synthetic
  `AppearanceSnapshot` themes (Catppuccin Mocha-derived dark, Catppuccin
  Latte-derived light) built from `appearance.rs`'s own public fields, plus
  two drag-mechanic captures driven through `HomeScreen`'s real public
  down/motion/tick/external_drag_motion API; verify with
  `cargo run --offline --example render_widget_evidence -- <dir>` and by
  looking at every produced image.
- [x] 3.2 18 screenshots committed under `docs/evidence/home-widget-design/`
  (10 distinct captures: 3 clock styles, battery present/absent, weather,
  overview, widget picker, and 2 drag-mechanic captures -- the drag
  mechanics captured once, in the dark theme only, since they are
  theme-independent) with a README explaining the harness, what each image
  shows, and what this evidence class does and does not prove; blob-inventory
  rows added for all 18; verify with `python3 tools/blob-scan.py` exiting 0.
  Done: exit 0, "every binary is accounted for".
- [ ] 3.3 A paired Sway/Rust QEMU injected-touch trial of the redesigned
  widgets and the live cross-page drag (edge dwell, fling, new-page
  creation) against a real compositor frame. **Not attempted this pass**:
  the sibling change's own `docs/evidence/home-widgets-folders/README.md`
  documents this exact harness being silently terminated at a reproducible
  point across three attempts on this same shared build machine; re-running
  it blind, with no new evidence that the underlying contention is
  resolved, would not have produced a trustworthy result. Left
  **UNVERIFIED** rather than guessed at. Re-attempting this on a less
  contended run is the next step, not a code change.

## 4. Build and checks

- [x] 4.1 `cargo test --offline` (full workspace) and
  `cargo clippy --offline --all-targets`; verify their exit codes directly.
  Done: 382 lib tests + 60 integration tests pass, 1 pre-existing ignored
  test unaffected; clippy exits 0 with no new warnings (checked by file/line
  against the pre-existing warning set: `overlay_brush`/`text_weight`/
  `service_card`/`paint_icon_plate`/`video_wallpaper.rs`'s existing
  too-many-arguments warnings, `theme_ui.rs`/`wifi_ui.rs`'s existing
  field-reassign-with-default warnings, and one pre-existing
  assertions-on-constants warning in `home_grid.rs` -- none of these
  originate from a line this change touched).
- [x] 4.2 Build the updated Rust client; verify with
  `nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done: `/nix/store/79l3ny61f523skmf06va1alpgxzcissq-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 4.3 Confirm the coherent-shell system closure still builds; verify
  with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done (first pass): `/nix/store/65w36kvr1h8i0ym6i94x0nphgcryaar4-nixos-system-nixos-26.11.20260919.20b1ddd`,
  which the coordinator deployed to the board for the user's judgment.
  Re-verified after the board-review visual-polish follow-up (task 2.3):
  `/nix/store/7k1w73rjpb4b3s91d3h2sbdb5bg35cn0-nixos-system-nixos-26.11.20260919.20b1ddd`
  (both host cross-build proofs only; the second has not itself been
  deployed or booted).
- [x] 4.4 Validate this change; verify with
  `openspec validate the-home-screen-pages-fluidly-and-widgets-look-designed --strict`.

## 5. Board acceptance (explicitly out of scope for this pass)

- [ ] 5.1 **Hardware, not claimed by this change.** Real-finger cross-page
  drag (edge dwell feel, fling, new-page creation) and the redesigned
  widgets (daylight readability, real weather data over the board's own
  network, a real battery device if the keyboard base is connected),
  photographed on the physical AMOLED. Left open per the coordinator's
  explicit instruction that this implementation does not touch the board or
  `/dev/ttyACM0`.
