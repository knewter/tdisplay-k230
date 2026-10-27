## 1. Host

- [x] 1.1 Keep `snapshot.count` from each `PreviewPoll` reply as
  `pending_count` in `main.rs`, and mark Home dirty only when it changes while
  Home is showing. Proof (host): `cargo test --offline --lib` in
  `nix/rust-shell-client`, with a test that a poll reply changing the count
  requests one Home redraw and an unchanged count requests none.
- [x] 1.2 Add the pure placement and label rule: digits, `99+` above 99,
  nothing at zero, and a rectangle in the top-right corner clamped clear of
  every occupied cell. Proof (host): `cargo test --offline --lib`, with tests
  on the default layout, a full page, and a count of 0, 1, 9, 99 and 100.
- [x] 1.3 Paint the count in `paint_home` and its callers, with no new
  surface. Proof (host): `cargo test --offline --lib`, including a test that a
  painted Home frame with a count is still non-opaque under
  `bgra_frame_is_opaque`, and that the painted count reads only the integer
  (the test builds a snapshot whose rows hold the text "SECRET" and asserts no
  such text reaches the frame or the log line).
- [x] 1.3a Host renders of Home at 1232x568 with counts 0, 3 and 100, at 100%
  and the largest vision step, under `docs/evidence/home-notification-count/host/`.
  Host render, not glass.

## 2. Board (hardware-only; one operator holds the board)

Each step needs the reserved board and an installed build. Record injected
input and glass separately.

- [x] 2.1 Injected board: with the shade closed on Home, emit three events
  (`k230-notifications emit`, one an unknown sender) and capture Home with
  `grim`: the count reads 3 within about two seconds. Dismiss one in the shade
  and capture that it reads 2, and clear all to see it disappear. Proof
  (injected board, not glass): captures and exact commands with timestamps
  under `docs/evidence/home-notification-count/board/`.
- [x] 2.2 Injected board: capture that the count shows no source or text from
  a private event, and that Home's drag between pages and the pull-down shade
  still behave with it showing (`tools/board-pointer.py` swipes). Same
  directory.
- [x] 2.3 Injected board: with Do Not Disturb on (if that change has landed),
  an ordinary event shows no banner and the count still rises. Same directory.
  Skip and say so if the other change is not installed.
  Done 2026-10-27 15:43Z (injected): with Quiet on two ordinary events showed no banner and the count rose to 3. `docs/evidence/home-notification-count/board/`.
- [ ] 2.4 Glass: the operator confirms on the panel that the count is legible
  and not mistaken for a control. Physical proof: a timestamped operator report
  tied to the installed build, in the same directory. Keep this task open until
  it exists.

## 3. Closeout

- [ ] 3.1 Archive once 2.4 is done. Proof:
  `openspec validate home-shows-how-many-notifications-wait --strict`.
