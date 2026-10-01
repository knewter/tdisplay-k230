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
- [x] 1.6 **Bug fix (operator report on real glass):** a cross-page
  rearrange drag (an existing icon *or* widget, long-pressed and dragged
  across the edge so Home pages over) landed correctly, but releasing the
  finger snapped the item back to its origin page/slot instead of dropping
  it on the new page. Root cause:
  `HomeScreen::drop_dragged_item`'s `DragSource::Existing` arm was the only
  drag source with no same-page fallback when the release point resolved
  to no slot at all -- every other source (`FromDrawer`/`Widget`/
  `FromFolder`) already fell back to `place_first_fit`. A release right in
  the edge margin (inside `EDGE_ZONE_PX`'s 40px trigger band but outside
  any tile's own hit rect, since `SIDE_MARGIN` is only 22px) is exactly
  where a person naturally lifts off after watching the page turn under
  their finger, and `move_existing`'s own "target occupied, can't merge or
  swap" branch had the same silent-revert gap. Fixed with a new
  `HomeScreen::move_existing_to_page`/`place_on_page_or_restore` same-page
  fallback (lands on the nearest free cell of whichever page is *currently
  on screen*, not `from`'s own page), plus a since-empty-and-pruned target
  page recreated via `HomeLayout::ensure_page` before searching it (a
  cross-page drag's own `remove_slot` on the origin cell unconditionally
  prunes a still-empty trailing page, which is exactly what a
  freshly-edge-hold-created target page is until something lands on it).
  Covered by four new regression tests reproducing the exact release
  geometry (an existing icon onto an empty new-page cell, onto an
  already-occupied new-page cell, released right in the edge margin, and a
  widget released onto an incompatible occupied cell); verify with
  `cargo test --offline -p k230-shell-rust home_screen::tests::dragging_an_existing_icon_across_the_edge_lands_on_the_new_page home_screen::tests::dragging_an_existing_icon_across_the_edge_onto_an_occupied_cell_lands_nearby_on_the_new_page home_screen::tests::releasing_right_at_the_edge_where_the_page_just_turned_still_commits_to_the_new_page home_screen::tests::dragging_a_widget_across_the_edge_onto_an_incompatible_occupied_cell_lands_nearby_on_the_new_page`.
  Full-suite re-run: `cargo test --offline -p k230-shell-rust` (386 lib +
  60 integration tests, all passing, 1 pre-existing ignored) and
  `cargo clippy --offline --all-targets` (exit 0, only the same
  pre-existing warning set this change's task 4.1 already documents).
  Evidence class: host unit test only (`cargo test`, native x86 host) plus
  a plain `cargo build`/`cargo clippy` pass -- **not** QEMU-injected touch
  and **not** real glass; the dedicated fix commit's own drag/drop logic
  was not otherwise touched by rendering or Wayland-input-path changes, so
  this is believed to close the reported behavior, but real-finger
  confirmation remains open per task 5.1 below.

## 2. Widget visual redesign

- [x] 2.1 `home_state::WidgetKind` gains `ClockMinimal`/`ClockAnalog`/
  `ClockDotMatrix` (additive to the schema-2 tag, no migration needed),
  `WidgetKind::ALL` and the picker's row list/count are derived from it
  rather than hand-typed literals; verify with
  `cargo test --offline -p k230-shell-rust home_state::tests::the_four_clock_styles_have_their_documented_spans_and_are_all_pickable`.
- [x] 2.2 `home_widgets::weather` rewritten onto wttr.in's `j1` format:
  `WeatherSnapshot` carries location, current temperature/feels-like,
  today's high/low, and up to 5 forecast entries; `parse_wttr_j1` selects
  forecast entries starting at the current hour and spilling into the next
  day; the 30-minute throttle, disk cache, and offline-keeps-last-reading
  behavior are unchanged; verify with
  `cargo test --offline -p k230-shell-rust home_widgets::weather`.
- [x] 2.3 `render.rs::paint_widget_card` redesigned per kind, in three
  passes (each documented in `design.md`, each superseding the last where
  they conflict):
  - **Pass 1:** two hero clock styles, an analog face, a battery ring, a
    weather card with a condition-tinted wash, all on a bordered
    `service_card` surface.
  - **Pass 2 (board review):** clipped the tint leak, replaced the border
    with a borderless filled surface (`paint_widget_surface`), rescaled the
    battery ring and centered its percentage, widened clock breathing room,
    enlarged the forecast strip.
  - **Pass 3 (board review, after `docs/design/clock-widget-research.md`):**
    removed `paint_widget_surface` entirely -- no card, fill, or border of
    any kind. Legibility comes from a luminance-derived halo (`glow_for`/
    `draw_layout_halo`, for text) or soft backdrop (`draw_soft_backdrop`,
    for small graphics) instead. Rebuilt all four clock styles: Bubble/Thin
    centered in `CLOCK_FONT_FAMILY` ("Inter") at real Black/Thin weights,
    Dot matrix added as a fully procedural 5x7 dot grid
    (`draw_dot_matrix_time`/`draw_dot_matrix_glyph`, digit bitmaps in
    `DOT_DIGITS`), Analog stripped of its dial fill/ring
    (`draw_analog_clock` no longer paints either). `nix/shell.nix` gained
    `clockDisplayFont` (one file, `Inter.ttc`, 13,172,948 bytes, extracted
    from `pkgs.inter`).
  Verify with `cargo build --offline -p k230-shell-rust`,
  `cargo test --offline -p k230-shell-rust home_state`, and the host
  evidence harness (task 3).
- [x] 2.4 Widget-picker previews render each widget kind's actual live
  content inline in its own row (`paint_widget_picker`'s preview
  thumbnail), not a static icon; verify with the host evidence harness
  (task 3), `dark-widget-picker.png`/`light-widget-picker.png`.

## 3. Evidence: host render harness

- [x] 3.1 `nix/rust-shell-client/examples/render_widget_evidence.rs`: calls
  the real, unmodified `render::paint_home` offscreen against two synthetic
  `AppearanceSnapshot` themes (Catppuccin Mocha-derived dark, Catppuccin
  Latte-derived light) built from `appearance.rs`'s own public fields,
  composited over a genuine Omarchy theme wallpaper image (decoded through
  the production `background_decode::BackgroundCache`, round 3's own
  addition -- passed as a command-line path, not embedded), plus two
  drag-mechanic captures driven through `HomeScreen`'s real public
  down/motion/tick/external_drag_motion API; verify with
  `cargo run --offline --example render_widget_evidence -- <dir>
  <dark-wallpaper> <light-wallpaper>` and by looking at every produced
  image.
- [x] 3.2 20 screenshots committed under `docs/evidence/home-widget-design/`
  (10 distinct captures: 4 clock styles, battery present/absent, weather,
  overview, widget picker, and 2 drag-mechanic captures -- the drag
  mechanics captured once, in the dark theme only, since they are
  theme-independent) with a README explaining the harness, the revision
  history across all three passes, what each image shows, and what this
  evidence class does and does not prove; blob-inventory rows updated for
  all 20 (replacing the 18 from the prior pass); verify with
  `python3 tools/blob-scan.py` exiting 0. Done: exit 0, "every binary is
  accounted for".
- [x] 3.3 `docs/design/clock-widget-research.md`: twelve surveyed clock-
  widget designs (Pixel bubble/thin/At-a-Glance, Nothing OS Ndot, iOS
  StandBy, Samsung One UI/Adaptive Clock, Material You, KWGT/KLWP, Braun/
  Dieter Rams, r/unixporn/Omarchy desktop rices), each with sourced links
  and a stated design principle taken from it (never a copied asset), plus
  a synthesis table mapping each of the four shipped styles to the
  principles behind it and the font-decision section `design.md`
  decision 6 cites.
- [x] 3.4 Paired production Sway/Rust injected-touch fluid-only QEMU run passes five paging/widget checks, including dwell/repeat/new page, interior fling, and actual runtime widget placement. Captures, exact artifacts and limits are committed in `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/README.md`; blob inventory passes.

## 4. Build and checks

- [x] 4.1 `cargo test --offline` (full workspace) and
  `cargo clippy --offline --all-targets`; verify their exit codes directly,
  re-run after each of the three passes described in task 2.3. Done (round
  3, final): 382 lib tests + 60 integration tests pass, 1 pre-existing
  ignored test unaffected; clippy exits 0 -- the four new multi-argument
  functions round 3 added (`draw_layout_halo`, `draw_dot_matrix_glyph`,
  `draw_dot_matrix_time`, plus `hero_glow`/`caption_glow` carried forward
  from round 2's own allow) all carry their own
  `#[allow(clippy::too_many_arguments)]`, and the pre-existing warning set
  (`overlay_brush`/`text_weight`/`service_card`/`paint_icon_plate`'s
  too-many-arguments, `theme_ui.rs`/`wifi_ui.rs`'s field-reassign-with-
  default, one pre-existing assertions-on-constants in `home_grid.rs`, one
  pre-existing manual-implementation-of-`ok` and one useless-`vec!` deeper
  in `render.rs`) is unchanged and does not originate from any line this
  change touched.
- [x] 4.2 Build the updated Rust client; verify with
  `nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done (round 1): `/nix/store/79l3ny61f523skmf06va1alpgxzcissq-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
  Re-verified (round 3, final):
  `/nix/store/yxnfzw58v1mqlc26mayn5c77y6rrrfmq-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 4.3 Confirm the coherent-shell system closure still builds, including
  the new `clockDisplayFont`/fontconfig derivations round 3 adds; verify
  with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done (round 1): `/nix/store/65w36kvr1h8i0ym6i94x0nphgcryaar4-nixos-system-nixos-26.11.20260919.20b1ddd`,
  which the coordinator deployed to the board for the user's judgment.
  Done (round 2): `/nix/store/7k1w73rjpb4b3s91d3h2sbdb5bg35cn0-nixos-system-nixos-26.11.20260919.20b1ddd`.
  Done (round 3, final, foreground): the build fetched and built
  `inter-4.1`/`inter-static-ttc`/`font-dirs`/`fc-cache`/`fontconfig-conf`/
  `fontconfig-etc` alongside the usual derivations, confirming the new font
  actually integrates into the real cross-built closure, not just `cargo
  build` on the host:
  `/nix/store/fv2gvvq6q3s3q180qxwabin41lc76cdg-nixos-system-nixos-26.11.20260919.20b1ddd`
  (a host cross-build proof only; not deployed to the board or booted this
  round).
- [x] 4.4 Validate this change; verify with
  `openspec validate the-home-screen-pages-fluidly-and-widgets-look-designed --strict`.

## 5. Board acceptance (explicitly out of scope for this pass)

- [x] 5.1 User-authorized board self-verification complete: repeated held edge turns/new page/drop, interior fling/drop, native clock/weather/no-battery captures and live disk-cached weather are recorded in `docs/evidence/home-widget-design/closeout-2026-10-01/board/README.md`. The user delegated acceptance instead of repeating the earlier manual/photo sequence. No human-finger/daylight measurement is invented; battery attachment is conditional and not applicable to the current board.
