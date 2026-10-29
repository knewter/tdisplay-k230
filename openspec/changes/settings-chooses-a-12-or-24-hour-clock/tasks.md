## 1. Host: preference and consumers

- [ ] 1.1 List every clock the shell and its own apps draw (shade, Home,
  Date & time, idle clock screen, Timer, Weather), and add the preference to
  `shell_prefs.rs` (missing or unreadable means 24-hour) with a reader for the
  Python apps. Proof (host): `cargo test --offline --lib` in
  `nix/rust-shell-client` and `python3 tests/test_term_apps.py`, with cases
  for 24-hour, 12-hour, midnight, noon and a corrupt file.
- [ ] 1.2 Make the Date & time "Clock format" row a switch, and make each
  listed clock follow the preference. Proof (host): the same two commands.

## 2. Host renders

- [ ] 2.1 Render the shade, Home, Date & time and the idle clock in 12-hour
  form at 100% and 200%, in both orientations. Proof (host render, not glass):
  renders under `docs/evidence/clock-format/host/`.

## 3. Board (hardware-only)

- [ ] 3.1 Test-activate a build, switch to 12-hour with injected touch, and
  grim-capture each clock in task 1.1. Then restart the shell and reboot, and
  confirm the choice holds. Proof (board, injected):
  `docs/evidence/clock-format/board/`.
- [ ] 3.2 Glass: the operator switches the format and reads the clocks.
  Physical proof: a timestamped operator report tied to the installed build.

## 4. Closeout

- [ ] 4.1 Archive once 3.2 is done. Proof:
  `openspec validate settings-chooses-a-12-or-24-hour-clock --strict`.
