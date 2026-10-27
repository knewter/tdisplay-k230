# Settings About and Date & time, host renders

Evidence class: host render only (production Cairo/Pango, no compositor, board
or finger). Change: `settings-has-about-and-date-time-pages`.

Command, from `nix/rust-shell-client`:

    cargo run --offline --example render_settings_about_evidence -- <repo>/docs/evidence/settings-about/host

Files are `<case>-<step>-<WxH>.png` with case `settings` (the top page with its
Date & time and About rows), `about` or `date-time`, step `100` or `200` (the
vision text step in percent), and size `1232x568` or `568x1232`.

Limits: the page rows are fixture values (a made-up store hash, kernel, uptime
and clock), not a reading of any installed build. The theme is the built-in
default with only the vision text step set. No board capture and no operator
reading on glass exist yet (change task 3).
