## 1. Host: sources and ranking

- [x] 1.1 Add `search.rs` with `SearchResult`, the Settings table (keywords,
  hardware gates) and ranking; replace `filter_app_indices` callers. Proof:
  `cargo test --offline search::` in `nix/rust-shell-client`. Host proof.
  Done 2026-10-28 (host): `src/search.rs` holds `SearchResult`, the 13-row Settings table with its hardware gates, and ranking; `filter_app_indices` is gone and the renderer and `main.rs` read `DrawerSearch::results`. `cargo test --offline --lib search::` 14 passed.
- [x] 1.2 Tests: prefix beats word start beats substring; ties keep Apps,
  Actions, Settings; "wifi" and "wi-fi" find Wi-Fi; Cellular, Location and Key
  backlight are absent without the hardware; an empty query yields no list.
  Proof: the same `cargo test --offline search::` run.
  Done 2026-10-28 (host): `search::tests` pin prefix < word start < substring, the Apps/Actions/Settings tie order, `wifi`/`wi-fi`, per-flag gating of Cellular, Location and Key backlight, and an empty or blank query giving no list; same run.
- [x] 1.3 Keep action names in `AppEntry` from `scan_apps`; no file is opened
  during a keystroke. Proof: `cargo test --offline catalog::` plus a test that
  counts zero opens after the scan.
  Done 2026-10-28 (host): `AppEntry.actions` is filled by `parse_entry` during `scan_apps`. `catalog::tests::actions_are_read_once_during_the_scan` deletes the desktop file after the scan and the names are still there; `search` takes no path or file API. `cargo test --offline --lib catalog::` 8 passed. Not a counter of opens.
- [x] 1.4 Test that no result source reads notifications, window titles or
  files, and that the query is absent from log output. Proof:
  `cargo test --offline search::privacy`.
  Done 2026-10-28 (host): `search::privacy` (3 tests): text only a notification, window title or file name could hold finds nothing; `search.rs` code uses no fs, gio, sway or notification API and no logging; no `log(` line in `main.rs` or `service_ui.rs` mentions the query. These are static source checks plus a behavioural one, not a runtime log capture.

## 2. Host: rows, outline and activation

- [x] 2.1 Paint result rows (at least 99 px, icon, label, kind detail) and the
  first-row outline; hit-test and Enter read the same vector. Proof:
  `cargo test --offline` in `nix/rust-shell-client` including a 1232x568 and a
  568x1232 render at the 200% vision step, and `cargo run --offline --example
  render_drawer_search_evidence` written under
  `docs/evidence/drawer-search/host/`. Host render with fixture catalog only.
  Done 2026-10-28 (host): Result rows (`render::paint_result_row`, `navigation::result_rect`/`result_at`, card at least 99 px) replace the grid once there is a query; the first row is outlined with the `hover-cursor` border and paint, hit-test and Enter read the same `DrawerSearch::results`. `render::tests::drawer_search_results_paint_as_rows_at_the_largest_text_step` renders 1232x568 and 568x1232 at the 200% step; `render_drawer_search_evidence` wrote `docs/evidence/drawer-search/host/`. Fixture catalog, no theme generation: the outline and the enlarged type are not visible in those images (see the README there).
- [x] 2.2 Activate a Settings result by opening that Settings page, and an
  action result through `AppAction::Desktop`. Proof:
  `cargo test --offline drawer_search_activation`.
  Done 2026-10-28 (host): `main.rs::choose_drawer_item` runs an action through `launch_home_action` with the app menu's `AppAction` forms and opens a Settings result through `panel_action`, `theme_action` or an inline scroll (`service_ui::settings_reveal_scroll`). `cargo test --offline --lib drawer_search_activation` 3 passed covers the result-to-activation mapping, that no destination maps to a toggle or request, and the inline row being in view at 1232x568 and 568x1232; the `ShellClient` wiring itself compiles but has no host test.
- [x] 2.3 Proof: `openspec validate the-drawer-search-finds-settings-and-app-actions
  --strict`.
  Done 2026-10-28 (host): `openspec validate the-drawer-search-finds-settings-and-app-actions --strict`: valid.

## 3. Board, injected input (hardware-only)

- [x] 3.1 Test-activate the build. With an app in front inject LILYGO, `wifi`,
  Enter; then LILYGO, `about`, Enter; then LILYGO, `ti`, Enter. Wi-Fi, About and
  Timer open and the app behind received no keys. Proof: `grim` captures and the
  key log under `docs/evidence/drawer-search/board/`. Injected evidence, not
  glass. Operator command: `./tools/msh.py` session per
  `docs/evidence/base-keys/` practice.
  Done 2026-10-28 (injected, build `f73q3409…`): wifi→Wi-Fi page, about→About, ti→Timer, the terminal behind kept a clean prompt. `docs/evidence/drawer-search/board/README.md`.
- [x] 3.2 Type a query with the on-screen keyboard raised and measure the rows
  that fit and the frame time. Proof: grim capture and the runtime trace file
  under `/var/tmp`, copied to the same directory.
  Done 2026-10-28 (injected): with the OSK raised, one full row plus part of a second fit; `K230_DRAWER_FRAME` 143 ms and 40 ms for the two keystrokes.

## 4. Glass (physical)

- [ ] 4.1 A person taps a Settings result and a lower result on the glass and
  presses Enter on the real base. Proof: a timestamped operator report tied to
  the installed build; keep open until it exists.
