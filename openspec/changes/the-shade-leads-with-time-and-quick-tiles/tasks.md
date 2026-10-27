## 1. Host

- [x] 1.1 Lay out the wide shade: the time and date header, the status line,
  the tile grid, the sliders, and the notification heading over the list.
  The hit tests read the same layout. Proof: `cargo test --offline --lib` in
  `nix/rust-shell-client`, with tests for the tiles' hit regions and their
  99 px floor.
- [x] 1.2 Wire the tiles: Wi-Fi opens its page, Keyboard toggles, Location
  toggles through the modem worker, and Cellular opens its page. Location and
  Cellular are hidden while the modem has not answered. Proof: host tests.
- [x] 1.3 Render the shade at 1232x568 at 100% and at the largest vision step,
  with and without the modem and notifications. Proof: renders in
  `docs/evidence/shade-pass/host/`.

## 2. Board (hardware-only)

- [x] 2.1 Test-activate the build. Capture the shade with grim, and tap each
  tile with injected touch. Proof: `docs/evidence/shade-pass/board/`.
- [ ] 2.2 The operator checks the shade on glass. Physical proof: a timestamped
  operator report tied to the installed build.
- [ ] 2.3 Promote the build from master to the boot default and verify an
  ordinary boot.
