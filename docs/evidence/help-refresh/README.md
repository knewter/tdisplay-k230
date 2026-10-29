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

## Board captures (portrait)

Evidence class: board, native `grim` capture. Build `vf91pbq6…` (test-activated, then the boot default), 2026-10-28 ~23:40 local. The panel was rotated live with `swaymsg output DSI-1 transform normal` and restored to `270` afterwards. No portrait image was installed. Taps used a copy of `ui.py` without its landscape assertion, with coordinates converted from portrait. Help was
opened with `k230-shell-rust --surface help` and scrolled with injected
swipes.

- `board/help-portrait-1.png` to `-3.png`: Touch, then Keys, then the buttons
  (Navigation buttons, Return to All apps), stacked as in the host render.
  The guide reaches its end on the third frame.

The operator reading Help on glass remains open (task 2.2).
