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
