## 1. Host: preference and consumers

- [x] 1.1 List every clock the shell and its own apps draw (shade, Home,
  Date & time, idle clock screen, Timer, Weather), and add the preference to
  `shell_prefs.rs` (missing or unreadable means 24-hour) with a reader for the
  Python apps. Proof (host): `cargo test --offline --lib` in
  `nix/rust-shell-client` and `python3 tests/test_term_apps.py`, with cases
  for 24-hour, 12-hour, midnight, noon and a corrupt file.
  *Host, 2026-10-29. The clocks: the shade's time (`render.rs`, via
  `home_widgets::clock::format_time`); Home's Bubble, Thin and Dot matrix
  widgets (`paint_widget_card_content`), where Analog is unaffected; Date &
  time's Time row (`device_info::format_time`); the idle clock screen
  (`k230_exhibition.clock_layout`); the Clock app (`k230_term_apps.clock_frame`);
  Weather's "Updated"/"Offline" line. The Timer shows durations, not wall time.
  `cargo test --offline` passed (682 lib tests plus every integration test,
  pixel identity included), and so did `python3 tests/test_term_apps.py`
  (39) and `python3 tests/test_exhibition.py` (31).*
- [x] 1.2 Make the Date & time "Clock format" row a switch, and make each
  listed clock follow the preference. Proof (host): the same two commands.
  *Host, 2026-10-29: the same runs. The row is a switch pill on the last
  card, and its tap region grows downward to 99 px. Where the time is drawn
  as large digits (the Home widgets, the idle clock, the Clock app), 12-hour
  puts AM/PM at the head of the date line; elsewhere the time reads
  `9:05 PM`.*

## 2. Host renders

- [x] 2.1 Render the shade, Home, Date & time and the idle clock in 12-hour
  form at 100% and 200%, in both orientations. Proof (host render, not glass):
  renders under `docs/evidence/clock-format/host/`.
  *Host render, 2026-10-29: 20 PNGs from
  `examples/render_clock_format_evidence.rs`, plus two idle-clock text frames
  from `k230_exhibition.py --render-once` with a 12-hour prefs directory. The
  portrait shade draws no clock at either step; that layout predates this
  change, so the shade's 12-hour form shows in landscape. See the README.*

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
