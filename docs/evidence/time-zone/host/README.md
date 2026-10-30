# Time zone and network time: host renders

Evidence class: **host render**. It proves paint and layout only. It is not
board or glass evidence. Task 2.2 of
`settings-sets-the-time-zone-and-network-time`.

Rendered 2026-10-30 with:

```sh
cd nix/rust-shell-client
cargo run --offline --example render_time_zone_evidence -- <out> /usr/share/zoneinfo
```

The chooser pages come from the host's tzdata 2026 `zone1970.tab`, through
the same `InfoView` (`open`, `choose`) the shell drives: 10 areas, and
Europe's 38 zones. Date & time's rows are FIXTURE values. Each case is drawn
at the landscape panel (1232x568) and the native portrait panel (568x1232),
at the 100% and 200% vision text steps.

| File | Shows |
| --- | --- |
| `date-time-{100,200}-{WxH}.png` | Date & time. `Time zone ›` links to the chooser, and Network time and Clock format are switches. Every card is at least 99 px tall. |
| `date-time-network-off-*.png` | The same page with network time switched off: the value reads `Off` and the switch is off. |
| `areas-*.png` | The first chooser page: each area with its zone count, then UTC. In portrait it pages with a `1 of 2` pager card. |
| `europe-page-1-*.png`, `europe-page-2-*.png` | Europe's zones, paged. The full zone name is the caption and the place is the value. The pager card is split: Previous on the left half and Next on the right, with the inactive end muted. Rows per page: 11 at 100% landscape, 8 at 100% portrait, 5 at 200% in either orientation. |

Limits: at 200% in landscape, the Date and Time zone values are elided. That
is the accepted 200% Date & time layout from
`settings-has-about-and-date-time-pages`. These renders show no zone being
applied. Applying one is a board check (task 3.1).
