## 1. Host

- [x] 1.1 Drop the charger line's target, then its limit, when the line is wider than the widget. Proof: `cargo test --offline --lib battery` in `nix/rust-shell-client`.
- [x] 1.2 Stroke a contrasting frame inside every carousel item's outline. Proof: `cargo test --offline --lib` (582 passed).
- [x] 1.3 Build the landscape system. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel` (`qh3i7b3f`).

## 2. Board (hardware-only)

- [x] 2.1 Test-activate the build. Capture with grim (injected touch): Home with Battery – Details while on the charger, and the background and theme choosers. Record the results in `docs/evidence/design-review-leftovers/`. Done on `qh3i7b3f`: the line reads "USB power · limit 3.25 A", and the slices are framed (`docs/evidence/design-review-leftovers/README.md`).
- [x] 2.2 Tap the Timer's Start, −1 min, +1 min and Reset controls and Weather's Refresh with injected touch, and capture each result with grim. Each control acted on the board; the Weather capture shows a location and is not committed (`docs/evidence/design-review-leftovers/README.md`).
- [x] 2.3 Measure Omawrite's start-up time from the drawer tap to its first mapped window, over three runs. Measurement only. Result: 6.89 s cold, then 1.52 s and 1.50 s (`docs/evidence/design-review-leftovers/README.md`).
- [x] 2.4 The operator checks the charger line and the chooser on glass. Physical proof: a timestamped operator report tied to the installed build (`docs/evidence/design-review-leftovers/operator-report.md`: "looks good" on `qh3i7b3f`, 2026-10-26).
- [x] 2.5 Promote the build from master to the boot default and verify an ordinary boot (`qh3i7b3f`, boot `a8be57ef…`, `docs/evidence/design-review-leftovers/promotion/receipt.json`).
