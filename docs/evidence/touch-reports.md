# The touch controller reports (display/touch task 4.1b)

2026-09-21. The GT9895 binds, interrupts, and delivers multitouch events
to `/dev/input/event0`.

## The interrupt was the whole problem

The device tree declared `IRQ_TYPE_EDGE_FALLING`. The controller binds
either way, `goodix_berlin` probes, and `/dev/input/event0` appears -- so
every status check passed while the device reported nothing. Measured on
the board, same kernel, same everything else, only the DT `interrupts`
flag changed:

| `interrupts = <23 ...>` | `/proc/interrupts` count |
| --- | --- |
| `IRQ_TYPE_EDGE_FALLING` (0x02) | **0** |
| `IRQ_TYPE_LEVEL_LOW` (0x08) | **2173** over one 45 s capture |

`/proc/interrupts` confirms the live setting: `87: 2173 gpio-k230 23
Level goodix-berlin`.

## What it reports

`evtest /dev/input/event0`, finger dragged on the glass:

```
Event: time ..., type 3 (EV_ABS), code 57 (ABS_MT_TRACKING_ID), value 27
Event: time ..., type 3 (EV_ABS), code 53 (ABS_MT_POSITION_X), value 456
Event: time ..., type 3 (EV_ABS), code 54 (ABS_MT_POSITION_Y), value 888
Event: time ..., type 3 (EV_ABS), code 48 (ABS_MT_TOUCH_MAJOR), value 3
Event: time ..., type 1 (EV_KEY), code 330 (BTN_TOUCH), value 1
Event: time ..., type 3 (EV_ABS), code 0 (ABS_X), value 456
Event: time ..., type 3 (EV_ABS), code 1 (ABS_Y), value 888
Event: time ..., -------------- SYN_REPORT ------------
```

Tracking IDs are allocated and retired, `BTN_TOUCH` goes 1 and 0, and
`ABS_MT_TOUCH_MAJOR` ramps as the contact patch grows. Slot-0 trajectory
from a 60 s capture, decoded with `ABS_MT_SLOT` honoured, spans
X 86..728 and Y 765..1765 continuously -- both axes move, and the motion
is smooth rather than quantised to a few values.

Axis ranges as the driver advertises them, matching the
`touchscreen-size-x/y` added to the DT:

| axis | min | max |
| --- | --- | --- |
| `ABS_X`, `ABS_MT_POSITION_X` | 0 | 1023 |
| `ABS_Y`, `ABS_MT_POSITION_Y` | 0 | 2399 |

Note the digitizer grid is 1024x2400 while the panel is 568x1232, so
anything consuming these coordinates has to scale.

## Not yet established

Whether the axes are swapped or mirrored relative to the panel. That
needs a touch at a *known* screen position, and the panel is currently
sheared by the pixel-clock workaround in `dsi-burst-headroom.md`, which
would make any on-screen target land somewhere other than where it is
drawn. Deferred to task 4.3, after the corrected image is flashed.
