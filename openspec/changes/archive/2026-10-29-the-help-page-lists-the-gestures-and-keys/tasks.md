## 1. Host

- [x] 1.1 Rework Help into Touch and Keys groups: columns when wide, stacked in
  portrait, with the existing hit-testing, scroll model and 99 px floor. Proof:
  `cargo test --offline --lib` in `nix/rust-shell-client` (614 passed), with
  tests for the grouping and the column placement, and `cargo test --offline`
  for the pixel-identity tests (no reference PNG changed).
- [x] 1.2 Render Help at 1232x568 and 568x1232, at the top and scrolled to the
  end. Proof: `docs/evidence/help-refresh/host/`, from
  `cargo run --offline --example render_help_refresh`.

## 2. Board (hardware-only)

- [x] 2.1 Test-activate the build and capture Help with grim at both
  orientations, scrolled through. Proof: `docs/evidence/help-refresh/board/`.
  *Done: landscape on build `dhmp8mdi…` (2026-10-27) and portrait on `vf91pbq6…` (2026-10-28, live output rotation, not a portrait image). Native `grim` captures in `docs/evidence/help-refresh/board/`.*
- [x] 2.2 The operator reads Help on glass. Physical proof: a timestamped
  operator report tied to the installed build.
  *Operator at the glass, 2026-10-29 00:34 CDT, build `37g1magg…`: "7 good" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
