# Battery - Details widget: host renders

Evidence class: **host render** (Cairo/Pango via `render::paint_home`, no
compositor, no board, no real sysfs). Date: 2026-10-15 (UTC).
Change: `openspec/changes/home-offers-a-battery-details-widget`, task 2.1.

Command, from `nix/rust-shell-client`:

```
cargo run --example render_battery_details_evidence -- ../../docs/evidence/battery-details-widget/host
```

Source: `examples/render_battery_details_evidence.rs`, which builds each state by
running the real `home_widgets::battery::read_details` over a temporary
`power_supply` tree of fixture `uevent` files:

- `charging-*`: the BQ27220 gauge and BQ25896 charger `uevent` text read from
  the board on 2026-10-15 while charging over USB-C (55 percent, +600 mA,
  4.202 V, 1627 / 3000 mAh, 38.1 C, 8160 s to full, charge type Fast).
- `discharging-*`: an invented fixture (71 percent, -412 mA, 3.89 V,
  2025 / 2850 mAh, 37 cycles, 34.2 C, 2700 s to empty, charger offline).
  It is not a board capture.
- `no-battery-*`: only the charger supply present, so no Battery supply.
- `picker-568x1232.png`: the widget picker with the new row.

Sizes: 568x1232 (portrait panel), 1232x568 (landscape panel), 1280x800 and
1920x1080 (landscape HDMI). The wallpaper is a flat dark colour with four
sample apps and a dock; the default theme (no Omarchy theme) is used.

Limits: these prove paint and layout of fixture values only. They do not show
the board's glass, real sysfs values on the running shell, the 10 s poll, or
touch placement. The picker's preview thumbnail is a small square crop, like
the existing 4x2 clock rows. Board task 3.1 (operator places the widget and
compares against `/sys/class/power_supply`) remains open. Current is rounded to
10 mA and power to 0.1 W in the display, so `-412 mA` shows as `-410 mA`.
