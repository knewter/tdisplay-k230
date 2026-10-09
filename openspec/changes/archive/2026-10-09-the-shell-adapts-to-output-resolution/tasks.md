## 1. Audit and design (host-only)

- [x] 1.1 Read `lib.rs`, `main.rs`, `render.rs`, `home_grid.rs`,
      `home_pager.rs`, `home_state.rs`, `navigation.rs`,
      `background_decode.rs` for every fixed-568/1232 dependency and record
      which already reflow with real width/height and which do not.
      Recorded in `design.md`'s audit table.

## 2. Accept whole-output configures instead of pillarboxing (host-only)

- [x] 2.1 Replace `main.rs`'s `pillarbox`/`lib.rs`'s `pillarbox_width` with
      `is_whole_output`-gated acceptance in all three
      `LayerShellHandler::configure` branches (wallpaper, Home, the shared
      overlay), keeping the keyboard-squish rejection path (a non-whole-
      output configure failing `configure_preserves_aspect`) unchanged.
      Verify: `cargo test` (`k230-shell-rust`), all 389 tests pass,
      including `lib.rs`'s `configure_preserves_aspect_accepts_uniform_
      resize_only` unchanged.
- [x] 2.2 Widen `lib.rs`'s `frame_bytes` width bound (`300..=1024` →
      `300..=2048`) and `background_decode.rs`'s `MAX_OUTPUT_WIDTH`/
      `MAX_OUTPUT_PIXELS` (1024/1024×2048 → 2048/2048×2048) so a real
      1920-wide whole-output configure and still-wallpaper decode are not
      rejected independent of the pillarbox question. Verify: `cargo test`,
      including the updated `frame_bytes_accepts_hdmi_whole_output_sizes`
      and `tests/background_decode_module.rs`'s
      `source_output_format_and_symlink_bounds_fail_closed`.

## 3. Drawer column reflow (host-only)

- [x] 3.1 Add `navigation::columns_for_width` and use it in `tile_rect`,
      `tile_at`, and `max_scroll` in place of the fixed `COLUMNS` constant;
      thread `width` through `DrawerNavigation::motion`/`tick` (and their
      `main.rs` call sites) so it reaches `max_scroll`. Verify: `cargo
      test`, including the new `columns_for_width_reflows_wider_hdmi_
      outputs_but_never_shrinks` and `wide_hdmi_output_hits_every_reflowed_
      column_of_the_first_row` (the latter taps every reflowed column of a
      1920-wide first row and confirms each hits its own launch index).
- [x] 3.2 Confirm no regression at the native 568px width: `columns_for_
      width(568) == COLUMNS` (4) by construction and test; every pre-
      existing Drawer test (`four_columns_hit_only_painted_tiles` and
      friends) passes unchanged.

## 4. Host-render evidence (host-only)

- [x] 4.1 Add `nix/rust-shell-client/src/evidence_render.rs` (rendering
      helpers shared by the example below and by task 7.3's pixel-identity
      test) and `examples/render_responsive_evidence.rs`, rendering Home,
      the Drawer, Settings, and the wallpaper background through the real
      production paint path (`render::paint_home`, `render::export_png`,
      `render::RendererCache::draw_wallpaper`) at 568x1232, 768x1024,
      1080x1920, and 1920x1080. Verify: `cargo run --example
      render_responsive_evidence -- <out-dir>` produces 16 PNGs with no
      panic.
- [x] 4.2 Commit the 16 PNGs under `docs/evidence/shell-responsive/` with
      that directory's own `README.md` recording the exact command, what
      each capture proves, and what it explicitly does not (no Wayland
      connection, no board, no QEMU). Add the `group:16-files` row to
      `docs/blob-inventory.md`. Verify: `python3 tools/blob-scan.py
      --no-vendor` reports `blob-scan: ok`. Re-rendered and re-committed
      once more after task group 7 landed (`home-*`/`settings-*` at the
      three HDMI sizes changed; all four `*-568x1232.png` did not, per
      task 7.3's own test).

## 5. Validate and hand off

- [x] 5.1 `cargo test` and `cargo clippy --all-targets --message-format=
      short` for `nix/rust-shell-client` — 406 tests pass after task group
      7 (389 at the end of task group 4), no new clippy warnings (the
      pre-existing warnings are all in files this change does not touch).
- [x] 5.2 `openspec validate the-shell-adapts-to-output-resolution --strict`
      exits 0.
- [x] 5.3 Cross-reference the output configure, reflow and hit-testing work
      from the original HDMI tasks 5.2/5.3, now preserved in
      `the-hdmi-shell-works-in-landscape`. Coordinator
      reconciliation on 2026-10-01 links the completed host work and names
      the remaining physical checks here and the density, Wi-Fi/theme
      geometry and dock decisions now owned by the landscape successor. No HDMI
      hardware or unfinished layout gate is ticked.
      Proof: `openspec validate the-shell-adapts-to-output-resolution --strict`
      and `openspec validate plugging-in-hdmi-moves-the-display --strict`
      (historical proof before archive). Current successor reference check:
      `openspec validate the-hdmi-shell-works-in-landscape --strict`.

## 6. Physical closeout checks and preserved follow-ups

2026-09-29 checkpoint: [physical HDMI trial](../../../../docs/evidence/shell-responsive/board/README.md)
records accepted 1080×1920 configures, native drawer captures and operator-confirmed
dragging. The monitor photograph and tap-to-launch proof remain missing; the
operator reports failed gestures with an app open and slow interaction. Injected
board traces identify 90° software composition as a major cost (442 ms median
frame build versus 15 ms unrotated). That dated checkpoint remains historical;
2026-10-09 acceptance below uses the normal combined hotplug runtime.

- [x] 6.1 On the physical board with an HDMI monitor attached (requires
      the accepted automatic HDMI arrangement, or its separately qualified
      HDMI-only recovery boot), confirm the compositor
      actually offers this client a whole-output configure at the
      monitor's real resolution, and that `is_whole_output` accepts it
      (board log line `configure WxH`, not `configure-rejected` or the
      no-longer-existing `pillarbox WxH -> ...`). Record the operator observation of
      a filled (not pillarboxed) Home screen with a matching native capture;
      the operator waived a monitor photograph on 2026-10-09. Commit
      under `docs/evidence/shell-responsive/board/`.
- [x] 6.2 On the same board session, confirm a real finger/stylus tap on a
      reflowed Drawer tile *and* a reflowed Home grid tile (task group 7)
      at the monitor's actual column count each launches the correct app,
      and that a Settings row tap lands correctly inside the new centered/
      scaled content column (this change's host tests prove the geometry
      math; only the board proves a real touch controller and compositor
      agree with it end to end).

Physical closeout — 2026-10-09: the operator explicitly accepts filled Home
and correct Home/All Apps/Settings targets in the accepted HDMI arrangement.
The matching native capture and numeric accepted configure records are in
[the acceptance report](../../../../docs/evidence/shell-responsive/board/acceptance-2026-10-09/README.md).
No photograph is required under the prior waiver. Exact diagnostic command:
`python3 docs/evidence/shell-responsive/board/acceptance-2026-10-09/capture-board.py
--output /protected/private-responsive-capture`. This is native/serial evidence
plus a separately recorded operator physical observation, not a camera recording.

### Scope transfer — 2026-10-09

The operator authorized moving original tasks 6.3–6.5 to
[`the-hdmi-shell-works-in-landscape`](../../the-hdmi-shell-works-in-landscape/tasks.md),
where they remain unchecked as 7.1–7.3. This preserves icon/text density,
Wi-Fi/theme reflow and the dock slot-count decision without claiming any was
performed. Tasks 6.1/6.2 are completed by the separate physical closeout above; the
transferred tasks remain open in their successor.
See [the committed scope decision](../../../../docs/evidence/shell-responsive/scope-decision-2026-10-09.md).

Scope proof: `openspec validate the-shell-adapts-to-output-resolution --strict`
and `openspec validate the-hdmi-shell-works-in-landscape --strict`.

## 7. Density scale, Home grid reflow, and a Settings content column (coordinator follow-up, host-only)

Landed on the same branch immediately after task groups 1–6 above; see
`design.md`'s two new "Decision (follow-up)" sections and its "Non-goal,
both passes" section for the full reasoning, including what was
reconsidered and rejected here.

- [x] 7.1 Rebase `feat/shell-responsive` onto `feat/hdmi-pillarbox`'s
      then-current head (`46a8e37e`, HDMI Sway output config +
      `theme_gtk.py` fix) before starting; no conflicts (disjoint files).
      Verify: `cargo test` still 389/389 immediately after the rebase, no
      code changes yet.
- [x] 7.2 Add `lib.rs`'s `density_scale`, `reflow_columns`, and
      `settings_content_transform`, each with its own unit tests
      (`density_scale_is_pixel_identical_at_native_and_bounded_above`,
      `reflow_columns_matches_base_at_design_width_and_only_grows`,
      `settings_content_transform_fills_the_panel_at_native_size`).
      Refactor `navigation::columns_for_width` to delegate to
      `reflow_columns` (behavior-preserving: every pre-existing Drawer test
      passes unchanged). Verify: `cargo test`.
- [x] 7.3 Home grid reflow: add `HomeLayout.columns` (`#[serde(default)]`),
      `HomeLayout::reflow_to`, `home_grid::columns_for_width`; give
      `home_grid::tile_rect`/`tile_content`/`spanned_tile_rect`/`slot_at`/
      `plate_top_left` an explicit `columns` parameter (sourced from
      `home.layout.columns` at every call site, never independently
      recomputed) in place of the `COLUMNS` constant; add `home_grid::
      apps_per_page`'s `width` parameter; add `HomeScreen::sync_columns`,
      called from `main.rs`'s `draw_home`. Verify: `cargo test`, including
      new tests `home_state.rs`'s `reflow_to_a_wider_column_count_never_
      loses_or_reorders_items`, `reflow_to_round_trips_4_then_8_then_back_
      to_4`, `reflow_to_is_a_no_op_when_columns_already_match`,
      `reflow_to_keeps_a_multi_span_widget_intact_as_one_item`;
      `home_grid.rs`'s `columns_for_width_matches_the_reference_at_568_and_
      grows_for_hdmi`, `wide_hdmi_grid_hits_every_reflowed_column_of_the_
      first_row`; `home_screen.rs`'s `sync_columns_reflows_to_a_wide_
      output_and_back_without_losing_items` — plus every pre-existing
      drag/rearrange/folder/widget test in `home_state.rs`/`home_screen.rs`
      passing unchanged, proving the field/parameter-shape refactor did
      not change behavior at the reference column count.
- [x] 7.4 Settings content column: add the `cr.save/translate/scale`
      transform to `render.rs::scene`'s `Route::Settings` arm (after its
      "Done" check, excluding the Wi-Fi/theme-chooser early returns and the
      unscaled header strip); make `settings_panel_h`/`panel_travel_height`
      take a `content_scale`; add the matching remap to `service_ui::
      panel_intent`'s Settings arm. Verify: `cargo test`, including new
      test `service_ui.rs`'s `settings_row_taps_follow_the_scaled_centered_
      content_column_on_hdmi` (taps the reboot row's real on-screen
      position at both a wide and a tall HDMI size, computed through the
      same shared transform function `scene` paints with, and confirms a
      miss well past the row).
- [x] 7.5 Add `nix/rust-shell-client/tests/responsive_pixel_identity.rs`:
      decodes each committed `docs/evidence/shell-responsive/*-568x1232.
      png` and asserts it is byte-for-byte identical to a fresh render
      through the (now-shared) `evidence_render` module, so "568x1232 stays
      pixel-identical" is an automated `cargo test` assertion, not a one-
      time visual check. Verify: `cargo test --test
      responsive_pixel_identity` — 4/4 pass against the evidence committed
      by task group 4, confirming the follow-up changed nothing at
      568x1232 before task 7.6 even re-rendered anything.
- [x] 7.6 Re-render all 16 evidence PNGs with `cargo run --example
      render_responsive_evidence -- <out-dir>`; confirm by direct `cmp`
      that all four `*-568x1232.png` are byte-identical to the previous
      commit and the other 12 changed (`home-*`/`settings-*` at the three
      HDMI sizes; `drawer-*`/`wallpaper-*` unchanged, as expected since
      neither's own logic changed this round). Re-commit under `docs/
      evidence/shell-responsive/` (same `group:16-files` count, no
      `docs/blob-inventory.md` row change needed) with the directory's own
      `README.md` updated to describe what changed and why.
- [x] 7.7 `cargo test` and `cargo clippy --all-targets` for
      `nix/rust-shell-client` — 406 tests pass, no new clippy warnings.
      Update this change's `proposal.md`, `design.md`, and
      `specs/runtime/shell/spec.md` to describe the follow-up (two new
      ADDED requirements: Home's grid reflow, Settings' content column).
      Verify: `openspec validate the-shell-adapts-to-output-resolution
      --strict` exits 0.
