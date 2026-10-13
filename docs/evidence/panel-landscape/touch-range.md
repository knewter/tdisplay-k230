# The GT9895's X range is 1080, not 1024 — 2026-10-13

The device tree said `touchscreen-size-x = <1024>`. That value was never
measured. `docs/evidence/touch-reports.md` added it at bring-up, when the
widest recorded contact was raw X 728.

## The observation

The landscape panel (sway `transform 270`, logical 1232x568) puts the
digitizer's X axis on the logical Y axis: `y = raw_x * 568 / 1024`.
The compositor's opt-in trace (`SWAY_K230_TOUCH_ROUTE_TRACE=1`, a runtime
systemd drop-in in `/run`) logged every touch-down, in
`touch-route-trace-2026-10-13.txt`. Columns: kernel monotonic seconds, then
the trace fields. The trace does not name the device, so lines are told
apart by time:

| Monotonic s | Source | Logical y range |
| --- | --- | --- |
| 5487-5507 | injected (`evemu-device` clone), known coordinates | as sent |
| 6315-6334 | operator's finger, no calibration | up to **598.508**, four times |
| 6430 | `swaymsg input 0:0:Goodix_Berlin_Capacitive_TouchScreen calibration_matrix 0.948148 0 0 0 1 0` | — |
| 6476-6486 | operator's finger, calibrated | up to 551.914 |

598.508 × 1024 / 568 = 1079.0. It is exact, and it repeats on four separate
touches: the controller's own ceiling is raw X 1079, so its grid is 1080
wide. With the 1024 declaration, the 30 px nearest the landscape bottom edge
(the right edge in portrait) landed outside the output. The card shell's
bottom-edge swipe starts in that band, so it never began.

The Y axis is consistent with 2400. Before calibration the operator reached
x = 0.513, which is raw Y ≈ 2399, and nothing went below zero.

LILYGO's own device tree on this board's factory card (backup
`k230-tdisplay-2-vendor-card-20261012.img.zst`, DTB at card offset
0x34a3400) uses the vendor driver with `goodix,panel-max-x = <0x424>` (1060)
and `goodix,panel-max-y = <0x960>` (2400). That confirms 1024 was not the
vendor's value either. The measured ceiling, 1079, is above the vendor's
1060, so this tree uses the measured 1080.

## The correction

`touchscreen-size-x = <1080>` in `k230-tdisplay-mainline-drm-common.dtsi`,
`k230-tdisplay.dts` and `k230-tdisplay-hdmi.dts`. For libinput this equals
the calibration the operator confirmed: both map raw X to `raw / 1080`.
`tools/inject-tap.sh` now reads the clone's advertised grid instead of
assuming 1024.

## Not yet established

- The rebuilt device tree booted on either board. The live check used the
  sway calibration matrix, not the new tree.
- The first board's range. It is the same product, but only this board was
  measured.
