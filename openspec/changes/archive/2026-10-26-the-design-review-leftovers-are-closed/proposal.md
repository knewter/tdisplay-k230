## Why

The operator accepted `the-shell-and-its-apps-look-finished` on glass on
2026-10-26, with four limits left open
(`docs/evidence/shell-design-review/operator-report.md`):

- Battery – Details cuts its charger line short:
  "USB power · limit 3.25 A · 2.05 A …".
- In the background chooser, the slice of a pale neighbouring background
  shows as loose blue glyphs with no visible edge.
- The Timer and Weather apps' buttons have only been tapped through a pty on
  the host, never on the touchscreen.
- Omawrite's start-up time has never been measured.

## What Changes

- The charger line drops its least important parts when it is too wide:
  first the charge targets, then the input limit. The power source and any
  charger fault always stay.
- Every carousel item gets a thin frame just inside its outline, in ink that
  contrasts with the page.
- Timer's and Weather's buttons get tested with injected touch on the board.
- Omawrite's start-up time gets measured on the board. This is a measurement
  only; nothing is changed.

## Capabilities

### Modified Capabilities

- `runtime/home-screen`: the Battery – Details charger line fits its widget.
- `runtime/shell-themes`: carousel items carry a frame.

## Impact

- `nix/rust-shell-client/src/home_widgets.rs`
- `nix/rust-shell-client/src/render.rs`
- the evidence in `docs/evidence/design-review-leftovers/`
