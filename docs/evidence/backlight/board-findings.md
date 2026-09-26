# Backlight board findings: transport bug fixed, panel still unresponsive live

Board operator session, `fix/backlight-rtc-board-findings`, base `master` @
`3d65166c`. System under test: the toplevel built from this branch's kernel
fix, deployed to `/boot` via the coordinator's export/import + bootfetch/
bootswap procedure and confirmed by a real cold reboot (not a one-shot RAM
boot) — `cat /proc/cmdline` on the post-swap boot shows
`init=/nix/store/9h5z3gk24gb3kdal037plsxqrmd7dx1y-nixos-system-nixos-26.11.20260919.20b1ddd/init`.

## Root cause of "brightness does nothing visible" (partially found)

Reading `drivers/gpu/drm/drm_mipi_dsi.c` in the pinned kernel tree directly:

```c
int mipi_dsi_dcs_set_display_brightness(struct mipi_dsi_device *dsi, u16 brightness)
{
	u8 payload[2] = { brightness & 0xff, brightness >> 8 };
	...
	err = mipi_dsi_dcs_write(dsi, MIPI_DCS_SET_DISPLAY_BRIGHTNESS, payload, sizeof(payload));
```

`mipi_dsi_dcs_set_display_brightness()` — the generic helper the first
version of this change used — unconditionally sends brightness as a
**2-byte** little-endian value (cmd + 2 data bytes, a 3-byte
`MIPI_DSI_DCS_LONG_WRITE`). But this exact panel's own proven-working
`panel-init-sequence` entry for the same `0x51` command is
`15 05 02 51 fe`: `MIPI_DSI_DCS_SHORT_WRITE_PARAM`, cmd + **one** data byte.
Sending the extra byte is exactly the shape of command a DCS parser
silently drops.

Fixed by sending exactly one byte via `mipi_dsi_dcs_write()` directly,
matching the proven command shape, and by removing the speculative
`MIPI_DCS_WRITE_CONTROL_DISPLAY` (0x53) pre-write the first version of this
change added — the working `panel-init-sequence` never sends `0x53` either,
so it was never an established requirement, only a guess.

**This fix is real and necessary**, confirmed by dmesg on every boot:

```
[    3.694602] canaan-panel-dsi 90850000.dsi.0: canaan_panel: DCS write 0x51 (brightness=254)
[    3.694610] canaan-panel-dsi 90850000.dsi.0: canaan_panel: DCS write 0x51 returned 0
```

Every subsequent live write also returns `0` (success), e.g.:

```
[  136.041190] canaan-panel-dsi 90850000.dsi.0: canaan_panel: DCS write 0x51 (brightness=128)
[  136.041215] canaan-panel-dsi 90850000.dsi.0: canaan_panel: DCS write 0x51 returned 0
```

## New finding: it is not sufficient

Writing 0, 128 and 255 via
`/sys/class/backlight/canaan-dsi-backlight/brightness` on a **freshly
rebooted** system (no DPMS/modeset interference) and photographing the
panel with the locked-exposure webcam at each value shows **no visible
change**, and the measured mean luminance over the same 600×250 crop of the
panel is statistically flat:

| Written value | dmesg return | Photo | Crop mean luminance (0-255) |
| --- | --- | --- | --- |
| 0 | `returned 0` | `brightness-0.jpg` | 200.99 |
| 128 | `returned 0` | `brightness-128.jpg` | 201.14 |
| 255 | `returned 0` | `brightness-255.jpg` | 201.33 |

This is a **stronger, cleaner negative result** than the original board
report (25/128/255 → 122.7/122.7/122.6): the corrected, byte-accurate
command still produces no visible or measurable change across the full
range, even at the extremes (0 vs. 255).

**Working hypothesis, not yet fixed:** the same exact command shape
(`MIPI_DSI_DCS_SHORT_WRITE_PARAM`, cmd + 1 byte) *does* take effect when
issued from `canaan_panel_prepare()` at boot (that is the only reason
`brightness=254` is visible at all at first light) but appears to have no
effect when issued later, from `backlight_ops.update_status()`, while the
DSI link is in continuous HS video-streaming mode. `canaan_dsi.c`'s
low-level command path has two literal `// TODO` no-op stubs —
`canaan_dsi_inst_abort()` and `canaan_dsi_inst_wait_for_completion()` — and
its packet builder (`canaan_dsi_dcs_write_long()`) always emits DSI Data ID
`0x39` regardless of the MIPI message type requested, which is consistent
with a minimal, prototype-quality command-mode implementation that was
apparently never exercised outside the boot-time command-mode window (the
same file's history already documents an "empty stub" DCS-read function
and several bounded/no-op register-wait TODOs). Sending a generic command
while continuous video streaming is active may simply not reach the panel
on this hardware, independent of the exact command bytes.

Supporting (but confounded) evidence: forcing a real `prepare()`/`enable()`
cycle via `swaymsg output DSI-1 dpms off` then `dpms on` did produce a
large, real luminance change (201 → 15) — but that experiment is
**confounded** and not offered as proof of the video-mode hypothesis on its
own: `canaan_panel_unprepare()` drives `backlight_gpio` (GPIO25, the panel
enable gate) low, while `canaan_panel_dsi_probe()` only ever drives it high
once, at `probe()` — never again on a subsequent `prepare()`. A `dpms off`
cycle may therefore be leaving the physical backlight-enable gate stuck low
regardless of any DCS command, which would produce the same dramatic
darkening for an unrelated reason. Following writes of `brightness=255`
after that cycle showed no recovery (15.03 → 15.09), consistent with the
gate being the thing that changed, not the DCS-controlled emission level.
**This GPIO-reassertion question is a separate, real finding, out of scope
for this change, and relevant to the future power-key/suspend proposal.**
The board was rebooted to a clean state before any further testing or
before landing this kernel, so it is not left in that condition.

## What this change does and does not close

- Fixes a real, confirmed transport bug (2-byte write against a panel that
  expects 1 byte) with dmesg evidence on every boot.
- Does **not** make brightness changes visible while the panel is running.
  `the-panel-brightness-is-adjustable`'s core requirement (a person can see
  the panel change brightness) remains open.
- Recommended next step, not attempted here: determine whether this DSI
  host can send generic commands during active video streaming at all
  (a real hardware/driver capability question, not a value/format
  question), and if not, find a mechanism to reapply brightness through a
  path proven to work (i.e. during `prepare()`) without a visible
  disable/enable flash on every Settings stepper tap.

## Commands used

```
# clean baseline (fresh boot, no dpms interference), then step 0/128/255
ls /sys/class/backlight/canaan-dsi-backlight
echo 0   > /sys/class/backlight/canaan-dsi-backlight/brightness
echo 128 > /sys/class/backlight/canaan-dsi-backlight/brightness
echo 255 > /sys/class/backlight/canaan-dsi-backlight/brightness
ffmpeg -hide_banner -loglevel warning -f v4l2 -input_format mjpeg \
  -video_size 1920x1080 -i /dev/video0 -update 1 -frames:v 1 -y <out>.jpg
magick <out>.jpg -crop 600x250+700+750 -colorspace Gray -format "%[fx:mean*255]\n" info:
dmesg | grep -i 'DCS write\|canaan_panel_prepare\|RDDID\|RDDPM'
```

Camera: `/dev/video0`, exposure locked to manual as set by the coordinator
(`auto_exposure=1 (Manual Mode)`, `exposure_time_absolute=99`); untouched
by this session.
