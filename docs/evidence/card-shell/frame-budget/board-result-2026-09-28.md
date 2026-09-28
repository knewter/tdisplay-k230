# Frame budget: board result, 2026-09-28

Evidence class: board read-only measurement over serial. The DRM vblank
probe (`nix/panel-refresh-probe.c`, `DRM_IOCTL_WAIT_VBLANK` only) and
`tools/measure-panel-refresh.sh` ran on system `9ix1cka3…`.

| Capture | Vblank samples | Vblank interval | VO IRQ rate |
| --- | ---: | --- | --- |
| Idle, nothing animating (`idle-capture.txt`) | 299 | min 19.149, p50 19.161, p95 19.162, max 19.172 ms | 0 Hz: the vblank IRQ is only enabled on demand |
| Overview animating via `swaymsg card_shell enter/next/previous/back` ×8, with foot and galculator open (`drag-capture.txt`) | 399 | min 19.129, p50 19.161, p95 19.163, max 19.192 ms | 53.4 Hz (427 events) |

Programmed mode: 49.5 MHz, htotal 748, vtotal 1268, 52.19 Hz, a period of
19.161 ms.

## Conclusion

Per the decision table in `analysis.md` §3: raw hardware vblank stays on a
clean 19.16 ms grid even while the card deck animates. The ~57.5 ms
presentation intervals in the earlier telemetry are therefore the
compositor's commit cadence missing vblank slots (H1: render or commit
overrun, rounded up to the next vblank). They are not a panel, DSI or VO
refresh limit. H4 (vblank IRQ at 1/3 rate) is refuted.

The decision this supports is (c): reduce per-frame card-deck render and
commit cost, and/or pipeline commits so an overrun costs one slot instead
of serialising the next. It does not support accepting ~57 ms as a
hardware limit.

Not measured here: presentation-feedback timing during the same run, and
real-finger drags. `swaymsg`-driven transitions stand in for gestures.
