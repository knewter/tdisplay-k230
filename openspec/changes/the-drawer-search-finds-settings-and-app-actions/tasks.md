## 1. Host: sources and ranking

- [ ] 1.1 Add `search.rs` with `SearchResult`, the Settings table (keywords,
  hardware gates) and ranking; replace `filter_app_indices` callers. Proof:
  `cargo test --offline search::` in `nix/rust-shell-client`. Host proof.
- [ ] 1.2 Tests: prefix beats word start beats substring; ties keep Apps,
  Actions, Settings; "wifi" and "wi-fi" find Wi-Fi; Cellular, Location and Key
  backlight are absent without the hardware; an empty query yields no list.
  Proof: the same `cargo test --offline search::` run.
- [ ] 1.3 Keep action names in `AppEntry` from `scan_apps`; no file is opened
  during a keystroke. Proof: `cargo test --offline catalog::` plus a test that
  counts zero opens after the scan.
- [ ] 1.4 Test that no result source reads notifications, window titles or
  files, and that the query is absent from log output. Proof:
  `cargo test --offline search::privacy`.

## 2. Host: rows, outline and activation

- [ ] 2.1 Paint result rows (at least 99 px, icon, label, kind detail) and the
  first-row outline; hit-test and Enter read the same vector. Proof:
  `cargo test --offline` in `nix/rust-shell-client` including a 1232x568 and a
  568x1232 render at the 200% vision step, and `cargo run --offline --example
  render_drawer_search_evidence` written under
  `docs/evidence/drawer-search/host/`. Host render with fixture catalog only.
- [ ] 2.2 Activate a Settings result by opening that Settings page, and an
  action result through `AppAction::Desktop`. Proof:
  `cargo test --offline drawer_search_activation`.
- [ ] 2.3 Proof: `openspec validate the-drawer-search-finds-settings-and-app-actions
  --strict`.

## 3. Board, injected input (hardware-only)

- [ ] 3.1 Test-activate the build. With an app in front inject LILYGO, `wifi`,
  Enter; then LILYGO, `about`, Enter; then LILYGO, `ti`, Enter. Wi-Fi, About and
  Timer open and the app behind received no keys. Proof: `grim` captures and the
  key log under `docs/evidence/drawer-search/board/`. Injected evidence, not
  glass. Operator command: `./tools/msh.py` session per
  `docs/evidence/base-keys/` practice.
- [ ] 3.2 Type a query with the on-screen keyboard raised and measure the rows
  that fit and the frame time. Proof: grim capture and the runtime trace file
  under `/var/tmp`, copied to the same directory.

## 4. Glass (physical)

- [ ] 4.1 A person taps a Settings result and a lower result on the glass and
  presses Enter on the real base. Proof: a timestamped operator report tied to
  the installed build; keep open until it exists.
