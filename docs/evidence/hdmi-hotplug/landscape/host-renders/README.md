# Landscape HDMI host renders (the-hdmi-shell-works-in-landscape 5.2/5.3)

Host renders only, 2026-10-14. They prove paint and layout at a monitor's
size, not the board, the monitor or touch.

```
cd nix/rust-shell-client
cargo run --example render_responsive_evidence -- <dir>   # home, drawer, help, power
cargo run --example render_landscape_surfaces -- <dir>    # Wi-Fi, themes, shade, folder
cargo run --example render_keyboard_base_evidence -- <dir> # Settings, with the 1280x800/1920x1080 sizes added locally
```

Sizes: 1280x800 (the operator's monitor turned to landscape) and 1920x1080.

Before the change, 1280x800 already took the landscape layout, but
`help::wide` also required an output under about 825 px tall, so 1920x1080
fell back to the portrait pages scaled non-uniformly: Settings was a narrow
column with Power off cut off at the bottom, and the Wi-Fi password page was
squashed until its text was unreadable. Now every output at least 1.6 times
as wide as it is tall takes the landscape layout. At 1920x1080 nothing
overlaps, is off-screen or is unreachable. Settings and Wi-Fi keep the
landscape panel's pixel sizes, which leaves empty space on a large monitor;
scaling them up is the density work in tasks 7.1–7.3.

New unit tests: Home's grid (`home_grid::wide_hdmi_grid_hits_every_reflowed_column_of_the_first_row`)
and the Drawer (`navigation::wide_hdmi_output_hits_every_reflowed_column_of_the_first_row`)
now also run at 1280x800 and 1280x720, checking every tile on-screen and
hit-testing to itself. `help::tests::aid_is_deliberate_and_routes_share_painted_geometry`
pins the rule: 1232x568, 1280x720, 1280x800 and 1920x1080 are wide; 568x1232,
1080x1920 and 1280x1024 are not.
