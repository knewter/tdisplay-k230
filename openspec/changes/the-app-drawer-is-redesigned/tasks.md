## 1. Fix the drag-to-close bug (landed separately, own commit)

- [x] 1.1 `navigation.rs`/`service_ui.rs`/`main.rs`: `Contact::
      scrolled_away`, `drawer_close_candidate_after_scroll`, and the
      "no fling in flight" gate at touch-down. Landed in commit
      `5bcf6ef5` ("fix(drawer): stop a mid-gesture scroll reversal from
      closing the drawer"), with no layout/visual changes, before the
      redesign work below. Proven there:
      `cargo test --lib`/`--bin` (233 lib + 20 bin passed at that
      commit), `cargo clippy` (zero new warnings).

## 2. Redesign (after the first attempt was rejected)

- [x] 2.1 Remove the per-app tile plate/card. `paint_drawer_tile`
      (`render.rs`) paints only a 64px icon and a single-line
      ellipsized 14px label directly on the sheet, no `service_card`
      call for the tile itself.
- [x] 2.2 Round, theme-tinted circle-with-initial icon fallback,
      replacing the squared icon-card fallback, with a strong (0.55
      alpha) tonal-container fill and a bright, contrasting label colour
      after coordinator review of a first, low-alpha revision ("dark and
      flat").
- [x] 2.2.1 **Follow-up from coordinator review**, after an initial
      real-icon screenshot showed nearly every real app falling back to
      the circle: investigated `Icon=` value by `Icon=` value against
      the built system closure and the real `k230-touch-launcher`
      binary's own `XDG_DATA_DIRS`. Confirmed a harness gap in this
      change's own evidence-gathering (the first screenshot's
      hand-assembled `XDG_DATA_DIRS` never included `pkgs.foot`/
      `pkgs.htop`/`videoProbe.player`'s own `share/` roots, and never set
      `K230_ICON_THEME`), not an `icon.rs` resolution defect — full
      table in `docs/evidence/app-drawer/README.md`. Re-rendered with
      the exact real `XDG_DATA_DIRS` (extracted from the built
      `k230-touch-launcher` binary) and `K230_ICON_THEME=Yaru-purple`:
      every application now resolves a real icon. Fixed anyway, as
      defense in depth: `catalog::terminal_like` (reads `Terminal=`/
      `Categories=` from the raw desktop file) plus a
      `utilities-terminal` fallback retry in `paint_drawer_tile`, for
      any future application whose icon name genuinely is not in the
      bundled theme. Proven: `catalog::tests::
      terminal_like_reads_the_terminal_flag_and_the_category` (new).
- [x] 2.3 Remove the "YOUR DEVICE / All apps / Everything installed…"
      header and the "Swipe down to return to cards" footer. `scene()`
      returns early into a dedicated `paint_drawer` for `Route::Drawer`
      that never calls the old header/footer code at all.
- [x] 2.4 Add the slim handle and pill-shaped "Search apps" field
      (`navigation::handle_rect`/`search_field_rect`,
      `paint_drawer_chrome`).
- [x] 2.5 Implement search: a new compact, lowercase-only on-screen
      keyboard (`navigation::search_keyboard_key_at`/
      `search_keyboard_hit`), live case-insensitive substring filtering
      (`service_ui::filter_app_indices`), and display-index-to-catalog
      mapping so launch/long-press resolve to the correct app while
      filtered (`ShellClient::drawer_filtered_apps`/
      `launch_drawer_app`/`pin_drawer_app`, `main.rs`).
- [x] 2.6 Opaque theme-coloured sheet with a 28px top-corner radius
      (`rounded_top`, new helper), filling from a small fixed top inset
      (`navigation::panel_top = 32px`, replacing the old ~19%-of-height
      gap); `panel_travel_height`'s Drawer case updated to match.
- [x] 2.7 Grid: `COLUMNS = 4`, `ROW_HEIGHT = 110.0`, equal 24px
      margins/gutters (dividing 568px width with no remainder), a
      subtle round press highlight in place of the old bordered square.
      `GRID_BOTTOM_INSET` shrinks from 72px to 24px now that there is
      no footer to reserve space for.
- [x] 2.8 Updated/added tests for the new geometry and search:
      `navigation.rs` (`four_columns_hit_only_painted_tiles`,
      `search_field_hit_is_bounded_to_its_own_pill_and_above_the_grid`,
      `handle_rect_is_centered_above_the_search_field`,
      `search_keyboard_key_at_resolves_letters_and_the_control_row`,
      `search_keyboard_hit_matches_its_own_top_edge`, plus the geometry
      fixes to pre-existing scroll tests now that 30 apps no longer
      overflow the redesigned viewport); `service_ui.rs`
      (`filter_app_indices_matches_case_insensitive_substrings`,
      `drawer_search_key_focus_and_clear`,
      `drawer_close_drag_zone_is_the_top_chrome_and_the_grid_only_at_top`);
      `render.rs` (`drawer_grid_cache_rebuilds_only_when_its_own_key_changes`,
      `scrolling_repaints_clipped_rows_but_keeps_chrome`,
      `pressed_grid_tile_has_a_visible_highlight_without_affecting_its_neighbor`).
- [x] 2.9 Host evidence: three before/after screenshots (the true
      original design, the redesign against a fixture catalog, and the
      redesign against a real installed-app/real-icon set assembled
      from the built system closure), committed at
      `docs/evidence/app-drawer/` with a README recording the exact
      commands, limits and blob-inventory rows. Proven: `python3
      tools/blob-scan.py --no-vendor` exits 0.

## 3. Performance: cached grid bitmap

- [x] 3.1 `DrawerGridCache` (`render.rs`): pre-renders the entire
      filtered grid into one bitmap, keyed on (filtered display list,
      theme generation, panel width, search query); rebuilt only on a
      key change. `paint_drawer` blits one viewport slice per frame
      instead of repainting every tile. Proven:
      `render::tests::drawer_grid_cache_rebuilds_only_when_its_own_key_changes`
      (new).
- [x] 3.2 Retained `IconCache::paint_label` (from the earlier, rejected
      attempt) since it still earns its keep making each real cache
      *rebuild* (e.g. one search keystroke) cheap.
- [x] 3.3 `K230_DRAWER_FRAME ms=…` rate-limited timing log
      (`DRAWER_FRAME_LOG_INTERVAL = 500ms`), gated to `Route::Drawer`,
      in `main.rs`'s `draw`.
- [x] 3.4 Committed, `#[ignore]`d host benchmark
      (`render::tests::drawer_grid_cache_host_timing`) driving the real
      `RendererCache::draw` path over 200 simulated scroll frames of a
      64-app catalog. Measured on this host (AMD Ryzen 9 5950X, `cargo
      test --lib --release drawer_grid_cache_host_timing -- --ignored
      --nocapture`): cold (fresh cache every frame) 33.60ms/frame mean,
      warm (persistent, scroll-only) 0.87ms/frame mean — a 38.8×
      reduction.
- [x] 3.5 Estimated board cost honestly: scaled by this repo's own
      established 20-40x host-to-board multiplier
      (`docs/evidence/card-shell/backdrop-blur-feasibility.md` §3),
      warm estimates to 17.3-34.6ms/frame — straddles the ~20ms target
      (clears it at the low end of the multiplier, not at the high
      end). Reported as such in `docs/design/app-drawer-review.md`
      §3.4, an honest order-of-magnitude improvement over both prior
      estimates, not claimed as a confirmed pass.

## 4. Tests and checks

- [x] 4.1 `cargo test --lib` (`nix/rust-shell-client`): 248 passed, 1
      ignored (the opt-in benchmark, §3.4), 0 failed.
- [x] 4.2 `cargo test --bin k230-shell-rust`: 22 passed, 0 failed.
- [x] 4.3 `cargo clippy --lib --bins --test appearance_module --test
      background_decode_module --test service_data_module` (excluding
      `tests/theme_catalog_module.rs`, which fails to compile on
      `master` itself for reasons unrelated to and out of scope for
      this change — confirmed via a baseline check before this change's
      first commit): zero new warnings in `navigation.rs`,
      `service_ui.rs`, `main.rs`, `icon.rs`, `catalog.rs` or
      `render.rs` (the same 6 pre-existing baseline warnings as before
      this change, unchanged in kind).
- [x] 4.4 `nix build .#handheld-shell-rust --max-jobs 1 --cores 6
      --no-link --print-out-paths`: exit 0,
      `/nix/store/6vwwhrxgxpligcijpgay34qjww2wd5ml-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 4.5 `nix build
      .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel
      --max-jobs 1 --cores 6 --no-link --print-out-paths`: exit 0,
      `/nix/store/jdcpajgdlbvhgyhhwan6rnnhc4xwjy2p-nixos-system-nixos-26.11.20260919.20b1ddd`.
- [x] 4.6 `openspec validate the-app-drawer-is-redesigned --strict`:
      valid. `python3 scripts/render_work_board.py > /dev/null`: exit
      0. `python3 tools/blob-scan.py --no-vendor`: exit 0 (see 2.9).
- [x] 4.7 Rebased onto `origin/master` twice: once past the
      `feat/brightness-slider` merge (real, concurrent edits to
      `main.rs`/`render.rs`/`service_ui.rs` — resolved by hand, import
      lists and struct field lists only, no logical overlap, since that
      work owns the Settings brightness row and the shade and this
      change owns only the Drawer), and again with `git rebase --onto
      origin/master 870135ac` after the coordinator landed this
      change's own bug-fix commit on `master` directly as `44e54e35`
      (a byte-identical cherry-pick of `870135ac`, confirmed via `git
      diff --stat 870135ac 44e54e35` producing no output) — dropping
      this branch's own now-duplicate copy rather than replaying it a
      second time. Full test suite re-run clean after each rebase.
- [x] 4.8 **Coordinator follow-up**: reviewed `redesign-real-icons.png`
      and found nearly every real app showing the fallback circle.
      Investigated and fixed — see 2.2.1 and `docs/evidence/app-drawer/
      README.md`'s own investigation table. Re-verified: `cargo test`/
      `clippy` (4.1-4.3, including the new
      `catalog::tests::terminal_like_reads_the_terminal_flag_and_the_category`),
      both `nix build`s (4.4-4.5) all re-run after this follow-up, not
      just before it.

## 5. Open: board and real-finger verification

- [x] 5.1 **Real-glass operator acceptance, 2026-09-30.** Reproduce the exact
      reported scroll-reversal gesture by real finger on glass and
      confirm the drawer does not close (the bug-fix commit's own
      gate).
- [ ] 5.2 **Hardware-only, not performed here.** Read
      `K230_DRAWER_FRAME ms=` from the board's journal while scrolling
      the drawer and compare against §3's 17.3-34.6ms/frame estimate.
      Resolves the design review's UNVERIFIED performance claim into a
      real number, and settles whether the ~20ms target is actually
      met.
- [x] 5.3 **Real-glass operator acceptance, 2026-09-30 (current compact keyboard).** Real-finger tap on the
      search field, type on the compact keyboard, and confirm live
      filtering and correct launch of a filtered result.
- [ ] 5.4 **Hardware-only, contingent on 5.2.** If the board
      measurement still shows a shortfall, open a follow-up change for
      the scroll-direction damage-limited blitting named in
      `docs/design/app-drawer-review.md` §6 (not implemented in this
      change).

The coordinator asked for the named drawer reversal and search/type/filter/launch checks; the operator replied “drawer works fine. search works fine.” Evidence: `docs/evidence/proposal-closeout/2026-09-30/operator-feedback.md`. This accepts the current interaction only; it does not claim 5.2 timing, a performance-contingent 5.4 follow-up, or the requested standard keyboard below.

## 6. Search uses the normal system keyboard

- [x] 6.1 Replace the drawer's custom compact letter/control rows with ordinary system-keyboard input and the shared wvkbd show/hide path. Show a visible insertion caret and focus indication. Keep search focus only while the field is active, handle text/Backspace/Enter/Escape, and reflow the app list above the actual keyboard reservation. Preserve filtering, scrolling, ordinary desktop-entry activation and the compositor's tap/gesture arbitration. Verify host routing, keyboard geometry and focus teardown with `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml`, then `nix build .#handheld-shell-rust`.
- [x] 6.2 Exercise the actual Rust drawer and wvkbd under the paired QEMU fixture, recording exact source/store identities: focus Search, type/correct/filter/launch, dismiss/reopen, leave Drawer and reclaim app focus. Host injection is not real-glass evidence. Record the concrete fixture invocation under `docs/evidence/app-drawer/` before ticking this task.
- [ ] 6.3 Deploy the exact matching userspace on the reserved board and prove real-finger system-keyboard search, correction, launch, dismissal and edge gestures; commit safe native/optical feature evidence and inspect the exact Pages revision. Use `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'` plus the recorded operator workload. Retain 5.2/5.4 until their separate measured evidence exists.

Task 6.2 proof: `docs/evidence/app-drawer/system-keyboard-qemu/README.md`, exact cross-built runtime identities in `result.json`. Real wvkbd correction, dismissal/reopen and app focus passed; injected host evidence only.

Task 6.1 host/build proof and 6.2 QEMU proof are recorded above. Partial 6.3 deployment and board-injected capture proof: `docs/evidence/app-drawer/system-keyboard-board/README.md`; real-finger Search/correction/dismissal/reopen/launch is accepted in `docs/evidence/app-drawer/system-keyboard-board/operator-feedback.md`; keyboard-handle/drawer-dismiss gesture acceptance and exact Pages inspection remain required.
