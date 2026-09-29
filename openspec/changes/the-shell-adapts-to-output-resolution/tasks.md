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

- [x] 4.1 Add `nix/rust-shell-client/examples/render_responsive_evidence.rs`,
      rendering Home, the Drawer, Settings, and the wallpaper background
      through the real production paint path (`render::paint_home`,
      `render::export_png`, `render::RendererCache::draw_wallpaper`) at
      568x1232, 768x1024, 1080x1920, and 1920x1080. Verify: `cargo run
      --example render_responsive_evidence -- <out-dir>` produces 16 PNGs
      with no panic.
- [x] 4.2 Commit the 16 PNGs under `docs/evidence/shell-responsive/` with
      that directory's own `README.md` recording the exact command, what
      each capture proves, and what it explicitly does not (no Wayland
      connection, no board, no QEMU; Home's grid column count intentionally
      unchanged). Add the `group:16-files` row to `docs/blob-inventory.md`.
      Verify: `python3 tools/blob-scan.py --no-vendor` reports
      `blob-scan: ok`.

## 5. Validate and hand off

- [x] 5.1 `cargo test` and `cargo clippy --message-format=short` for
      `nix/rust-shell-client` — 389 tests pass, no new clippy warnings (the
      13 pre-existing warnings are all in files this change does not
      touch).
- [x] 5.2 `openspec validate the-shell-adapts-to-output-resolution --strict`
      exits 0.
- [ ] 5.3 Cross-reference this change from
      `openspec/changes/plugging-in-hdmi-moves-the-display/tasks.md`'s own
      task 5.2/5.3 (that proposal's shell/landscape-support group), so a
      reader of either change finds the other. **Not done by this change**:
      it touches only its own worktree's files; the coordinator or that
      change's own owner should link the two to avoid duplicated scope.

## 6. Board-gated follow-up (explicitly open, out of scope for this change)

- [ ] 6.1 On the physical board with an HDMI monitor attached (requires
      `plugging-in-hdmi-moves-the-display` task group 3's manual switch, or
      whatever HDMI-enable path lands first), confirm the compositor
      actually offers this client a whole-output configure at the
      monitor's real resolution, and that `is_whole_output` accepts it
      (board log line `configure WxH`, not `configure-rejected` or the
      no-longer-existing `pillarbox WxH -> ...`). Capture a photograph of
      the monitor showing a filled (not pillarboxed) Home screen. Commit
      under `docs/evidence/shell-responsive/board/`.
- [ ] 6.2 On the same board session, confirm a real finger/stylus tap on a
      reflowed Drawer tile at the monitor's actual column count launches
      the correct app (this change's host tests prove the geometry math;
      only the board proves a real touch controller and compositor agree
      with it end to end).
- [ ] 6.3 Design and implement Home's own grid-column reflow
      (`design.md`'s "Rejected/deferred" section) as its own follow-up
      change, once 6.1/6.2 give a real device to verify drag/rearrange
      behavior against — not implementable-and-verifiable from this
      change's own host-only worktree.
- [ ] 6.4 Design and implement Settings' row-content max-width/centering
      and, separately, replace `paint_wifi`'s non-uniform `cr.scale` with a
      uniform, centered scale or a real reflow, as its own follow-up.
