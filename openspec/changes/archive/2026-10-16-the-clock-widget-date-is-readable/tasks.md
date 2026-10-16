## 1. Date line

- [x] 1.1 Size the Clock widget's date line (every style) from a 26 px floor
  times the Vision text step. Fit it to the cell width with a 4% margin, and
  move the time digits up or shrink them so they never overlap it. Verify
  with `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --lib clock_date` (a new test that measures the date's size, width and
  vertical clearance at 100%, 130%, 160% and 200%) and with
  `tests/responsive_pixel_identity.rs`, which must still pass outside the
  Clock widget.
  Done 2026-10-16 (host): both passed; see
  `docs/evidence/home-widgets/clock-date/README.md`.
- [x] 1.2 Host renders of Home at all four steps, committed under
  `docs/evidence/home-widgets/clock-date/`.
  Done 2026-10-16 (host): Bubble style, both orientations.

## 2. Board

- [x] 2.1 Native `grim` captures of Home at 100% and 200% on the landscape
  panel, and the operator's judgement that the date is readable on glass.
  Progress 2026-10-16: native captures at 100%, 160% and 200% committed
  (`docs/evidence/home-widgets/clock-date/board-panel-*-home.png`). The
  operator's judgement on glass is still needed.
  Result 2026-10-16 (operator on glass): after the restyle (`bd75aad5`, a
  32 px date line), the operator said "clock lookgs good".
