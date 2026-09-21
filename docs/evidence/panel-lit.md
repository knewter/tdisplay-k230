# The panel lights (display/panel task 3.2)

2026-09-21. Photographs in `docs/evidence/panel-photos/`, taken with a
webcam pointed at the board while the framebuffer was driven to three
known states from a shell on the device.

| file | written to `/dev/fb0` | panel |
| --- | --- | --- |
| `01-urandom-noise.jpg` | `dd if=/dev/urandom` | bright field, visible speckle |
| `02-all-black.jpg` | `dd if=/dev/zero` | dark |
| `03-all-white.jpg` | `0xFF` bytes | bright band |

The panel emits, and what it shows tracks what is written to the
framebuffer. Driving it to three different states rather than
photographing one is deliberate: a single bright frame could be a
reflection, and a single dark frame is what a dead panel looks like. The
*change* is the evidence.

Writing a pattern at all was necessary. An all-zero framebuffer on a
working panel is indistinguishable from a panel that is off, and for most
of this investigation the framebuffer was zeroed.

## What made the difference

The device tree was sending the wrong panel's initialisation sequence.
`rm69a10.c` in LilyGO's RT-Smart tree defines two init functions:
`rm69a10_OLD_init()` at line 39, which has **no callers** and is a
byte-for-byte copy of `hx8399_v2_init()` (a Himax 1080x1920 panel), and
`rm69a10_568x1232_init()` at line 96, which the dispatcher at lines
345/347 actually calls. We transcribed the dead one.

The live sequence is 13 commands, 36 bytes, and includes three things the
Himax sequence does not:

- **`51 FE`** — `SET_DISPLAY_BRIGHTNESS`. A DCS-brightness AMOLED powers
  up at zero, so it can be fully initialised and emit nothing. This is
  almost certainly the single line that was keeping the screen dark.
- **`2A` / `2B`** — the frame memory window.
- **120 ms** after sleep-out, where the wrong sequence allowed 1 ms.

## Still wrong: the image is glitchy

The panel lights but the picture is not stable or correct. The prime
suspect is in the sequence itself:

```
31 00 03 02 34   partial columns
30 00 00 04 CF   partial rows
12 00            ENTER_PARTIAL_MODE
```

`0x12` puts the controller in partial display mode over a restricted
area. That is what the vendor firmware does, but the vendor also drives
the VO differently — see `docs/evidence/rtsmart-panel-bringup.md`, which
lists the remaining divergences in priority order: no SoC display reset
on enable, a stale reset pulse, no 3 ms settle after each DCS packet,
`vco_cntrl` 0x19 vs 0x17, and CRTC-before-encoder ordering that streams
video into a link that is not configured yet.

## Note on DCS reads

`RDDPM (0x0A)` still times out (`-110`, `CMD_PKT_STATUS 0x50015`,
`GEN_PLD_R_EMPTY` set) even now that the panel is visibly working. So a
failed DCS read is **not** proof the panel is deaf — the read path or its
timing is wrong somewhere. That is worth remembering: the read timeout
was treated earlier as strong evidence the panel received nothing, and
that inference is now known to be unsafe.
