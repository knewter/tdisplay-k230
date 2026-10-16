## 1. Implementation

- [x] 1.1 Add a bounded battery history (append, load, prune, rewrite) to
      `home_widgets::battery` with unit tests for parsing, pruning, gaps and
      future-dated samples. Record on the existing poll in `main.rs` and paint
      the graph in `paint_battery_details`.
      Proof (host): `cd nix/rust-shell-client && cargo test` -- 535 lib
      tests pass (2 ignored), and the other suites pass.

## 2. Host evidence

- [x] 2.1 Render the widget with a fixture history (a discharge, a gap and a
      charge) at 568x1232, 1232x568 and 1280x800 to
      `docs/evidence/battery-details-widget/history/`, with a README.
      Inspect the images and register the PNGs in `docs/blob-inventory.md`.
      Evidence class: host render.

## 3. Board

- [x] 3.1 Deploy and capture the widget's graph after the board has run unplugged
      for a while; check the history file against the graph. Evidence class:
      board grim. Done 2026-10-15 19:30 CDT:
      `docs/evidence/battery-details-widget/history/board/README.md`
      (discharge, the gauge's 88 -> 7 recalibration, a power-off gap; no
      charging span yet).
- [x] 3.2 The operator confirms the graph on the glass. Evidence class: operator
      observation. Done 2026-10-15 about 19:50 CDT: the operator, viewing
      page 2 on HDMI, said "graph looks fine".
