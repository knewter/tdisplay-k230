# Help refresh, host renders

Evidence class: host render only (production Cairo/Pango, no compositor, board
or finger). Change: `the-help-page-lists-the-gestures-and-keys`.

Command, from `nix/rust-shell-client`:

    cargo run --offline --example render_help_refresh -- <repo>/docs/evidence/help-refresh/host

Each size has a `top` frame and an `end` frame (Help scrolled to its maximum),
because the guide is longer than one screen.

- `help-landscape-1232x568-{top,end}.png`: Touch on the left; Keys under the
  buttons on the right.
- `help-portrait-568x1232-{top,end}.png`: Touch, Keys, then the buttons.

Limits: default theme, 100% text step, no board capture, no operator reading
on glass. Those remain open (change task 2).

## Board captures (landscape)

Evidence class: board, native `grim` capture, with Help opened by
`k230-shell-rust --surface help` and scrolled by injected touch swipes on
the text (`/var/tmp/ui.py`, copy at `docs/evidence/base-keys/ui.py.txt`).
Build: `/nix/store/dhmp8mdiii13xynd0cqyhjr5mkad0mah-nixos-system-nixos-26.11.20260919.20b1ddd`,
test-activated, 2026-10-27 ~03:36Z.

- `board/help-landscape-1.png` to `-4.png`: top, then each swipe, to the end
  (Power key). The text matches the host render.

The portrait capture needs a portrait image on the board and is still open,
as is the operator reading Help on glass.
