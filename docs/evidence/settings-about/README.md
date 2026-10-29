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

## Board captures (landscape)

Evidence class: board, native `grim`, pages opened by injected taps on the
Settings rows. Build `/nix/store/kllh24ww1vhybcdf6z9z6jz859584jsb-nixos-system-nixos-26.11.20260919.20b1ddd`,
2026-10-27 ~03:52Z.

- `board/about-landscape.png`: Device `nixos`, System `kllh24ww · nixos-system-…`,
  Kernel `7.3.0-rc5`, Uptime, Storage `8.0 GB free of 15.2 GB`, Shell
  `0.1.0 · kwwqrc8a`.
- `board/date-time-landscape.png`: Network time `Synchronized`, time zone
  `America/Chicago (UTC-05:00)` (the zone set in `nix/k230.nix`).

Over SSH at 03:53:32Z: `/run/systemd/timesync/synchronized` exists, and
`readlink /run/current-system` is the `kllh24ww…` path above. The portrait
captures and the operator's reading on glass remain open.

## Board captures (portrait, and landscape Settings)

Evidence class: board, native `grim` capture. Build `vf91pbq6…` (test-activated, then the boot default), 2026-10-28 ~23:40 local. The panel was rotated live with `swaymsg output DSI-1 transform normal` and restored to `270` afterwards. No portrait image was installed. Taps used a copy of `ui.py` without its landscape assertion, with coordinates converted from portrait. About and
Date & time were opened from the drawer search: the base-attached drawer
took injected keys "about" and "date", then Enter.

- `board/settings-portrait.png`, `board/settings-landscape.png`: the Settings
  page at each orientation.
- `board/about-portrait.png`: System `vf91pbq6 · nixos-system-nixo…`, which
  matches the running build.
- `board/date-time-portrait.png`: America/Chicago (UTC-05:00), Network time
  Synchronized, Clock format 24-hour.

The operator reading both pages on glass remains open (task 3.3).
