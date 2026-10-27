## 1. Host: broker and preference

- [ ] 1.1 Add `breakthrough` to the broker preview: true for a critical
  event, or an important event from a trusted non-delegate source; false for
  delegated apps, SMS and unknown senders. History rows do not carry it.
  Proof (host): `python3 tests/test_notification_center.py`, with cases for
  the base battery, a Timer-shaped important event, a delegated important
  event, an ordinary event and an unknown sender.
- [ ] 1.2 Parse `breakthrough` in `service_data.rs` (missing means false) and
  add the preference module (`do-not-disturb`, missing or unreadable means
  off, one-word write). Proof (host): `cargo test --offline --lib` in
  `nix/rust-shell-client`, with a test per case, including a corrupt file.
- [ ] 1.3 Filter the banner in `main.rs`: while quiet, a preview without
  `breakthrough` never reaches `banner_preview`, and a shown banner unmaps when
  the mode turns on. History and the count are untouched. Proof (host): the
  same `cargo test --offline --lib`, with a test on the filter function over a
  snapshot holding one alert and one ordinary event.

## 2. Host: tile, indicator and Settings row

- [ ] 2.1 Make the tile grid three columns (`SHADE_WIDE_TILE_COLUMNS`), add
  `ShadeTile::DoNotDisturb`, and keep every tile at least 99 px tall with the
  slider top unchanged. Proof (host): `cargo test --offline --lib`, with tests
  that every tile rect lies inside the 480 px column, tiles do not overlap,
  each is at least `SHADE_TAP_MIN` tall, and the volume slider's end is within
  568 px at every vision text step.
- [ ] 2.2 Paint the tile (stacked icon, label, one-word state, accent when
  on) and the moon glyph on the status line, and add the Settings row. Proof
  (host): `cargo test --offline --lib`, then renders of the wide shade at
  1232x568 with quiet mode off and on, with and without the modem, at 100%
  and at the largest vision step, saved under
  `docs/evidence/do-not-disturb/host/`. These are host renders, not glass.
- [ ] 2.3 The renders show every tile label and state without cutting a
  word, and both sliders fully on the panel at the largest step. If a word
  still shrinks below the caption size, shorten the copy and rerender. Proof:
  the 100% and largest-step renders above.

## 3. Board (hardware-only; one operator holds the board)

Each step needs the reserved board and an installed build. Record injected
input and glass separately, and never assume the person is touching.

- [ ] 3.1 Injected board: toggle the tile with injected touch
  (`tools/board-pointer.py`), emit an ordinary event, and capture with `grim`
  that no banner maps while history lists it; then emit a Timer-shaped
  important event from the Timer source and capture its banner. Proof
  (injected board, not glass): captures and the exact commands with
  timestamps under `docs/evidence/do-not-disturb/board/`. The base-battery
  critical event is exercised by the host test only unless the policy can be
  driven on the board; say which.
- [ ] 3.2 Injected board: `grim` captures of the shade with the tile off and
  on show the moon glyph appear and disappear, and the sliders stay on the
  panel at the largest vision step. Same directory.
- [ ] 3.3 Injected board: the Settings row and the tile agree after each is
  toggled. Same directory.
- [ ] 3.4 Injected board: turn quiet mode on, reboot, and record that it is
  still on and that `/var/lib/k230-shell-prefs/do-not-disturb` reads `on`;
  record the same after a shell restart. Console transcript under
  `docs/evidence/do-not-disturb/board/`.
- [ ] 3.5 Glass: the operator confirms on the panel that the tile is
  reachable with a thumb, that a received text produces no banner while quiet,
  and that a 10 s Timer still breaks through. Physical proof: a timestamped
  operator report tied to the installed build, in the same directory. Keep
  this task open until it exists.

## 4. Closeout

- [ ] 4.1 Archive once 3.5 is done and `the-shade-leads-with-time-and-quick-tiles`
  has archived. Proof: `openspec validate do-not-disturb-quiets-banners-and-keeps-history --strict`.
