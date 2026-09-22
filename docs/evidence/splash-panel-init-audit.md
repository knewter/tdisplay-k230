# Splash-panel initialization audit

**Scope:** source audit only, 2026-09-22.  This compares the RM69A10 DCS
sequence in the stage-1 U-Boot logo port with the device-tree sequence used
by a normal Linux panel prepare.  It does not observe DCS traffic on the
board and does not establish the panel's undocumented internal state.

## Sources inspected

| Component | Pinned source path | Relevant lines |
| --- | --- | --- |
| Stage 1 logo port | `nix/patches/uboot-k230/0004-rm69a10-logo-port.patch` | 467--505, 423--437 |
| Linux panel DT source | `nix/dts/display-rm69a10-568x1232.dtsi` | 50, 72--98, 121--129 |
| DTB derivation | `nix/device-tree.nix` | 68--71 |
| Linux panel driver after the project patch | `drivers/gpu/drm/panel/panel-canaan-universal.c` in the kernel source prepared by `nix/kernel.nix` | 126--160, 374--388, 405--412 |
| Linux DSI host | `drivers/gpu/drm/canaan/canaan_dsi.c` in that same source | 320--334, 444--475 |
| Stage-1 DSI host port | `board/canaan/common/logo/display_logo.c` after applying 0004 | 121--136 |

`nix/device-tree.nix` copies the checked-in RM69A10 include next to the
pinned kernel dtsi files before preprocessing and compiling
`k230-tdisplay.dtb`; this is the actual DT source rather than a reference
copy.

## Intended DCS payloads

The two paths have the same intended sequence and payloads:

```
FE FD                    vendor page select
80 FC
FE 00                    user page
2A 00 00 02 37           column 0..567
2B 00 00 04 CF           page 0..1231
13 00                    ENTER_NORMAL_MODE
35 00                    tearing-effect enable
51 FE                    brightness
11                       sleep out
29                       display on
3A 77                    24-bit pixel format
```

In particular, neither sends `0x36` (MADCTL).  There is therefore no source
basis for an RGB/BGR or orientation difference in panel DCS state.  The
column/page windows and `0x3A 0x77` also agree.

The original vendor sequence used a partial-area block:

```
31 00 03 02 34
30 00 00 04 CF
12
```

That block is **not** present in U-Boot patch 0004.  The port deliberately
uses `13 00`, with a source comment saying it matches the system DTS.  It is
not valid to attribute the retained-logo failure to U-Boot leaving the panel
in this vendor partial-display mode.

## Timing and link state

The packet payloads match, but their waits do not exactly match.  U-Boot
sends the early packets back-to-back, waits 120 ms after `11`, and waits 10
ms after `29`.  The DT records are `(data_type, delay_ms, payload_length,
payload...)`; the Linux driver honors `delay_ms` after each record.  The DT
therefore requests 3 ms after each early command, 5 ms after `51`, 123 ms
after `11`, and 3 ms after `29`.  The DTS comment referring to vendor waits
of 300/100 microseconds is inconsistent with U-Boot 0004's actual
`msleep(120)` and `msleep(10)` calls.

Both sources use two lanes, 49.5 MHz pixel clock, 594 MHz PHY timing, and
HS-frequency range `0x87`.  U-Boot's connector record selects
`K_DSI_2LAN`, `K_BURST_MODE`, and `K_VO_LP_MODE`; it writes
`VID_MODE_CFG = 0xbf02` and `DPI_COLOR_CODING = 0x105`.  Linux's universal
panel declares two lanes and RGB888.  Although it assigns
`MIPI_DSI_MODE_VIDEO_SYNC_PULSE`, the Canaan host does not consume that flag
and itself writes the same `VID_MODE_CFG = 0xbf02` and
`DPI_COLOR_CODING = 0x105`.  Thus the actual configured host mode is burst
in both paths; there is no identified lane, burst, or DPI color-coding
mismatch.

## What remains unproven

On a normal Linux boot, the panel driver resets the panel and sends the DT
sequence.  When `/chosen/canaan,stage1-splash` is present, the project
kernel patch requests the reset GPIO as `GPIOD_ASIS` and the first
`canaan_panel_prepare()` returns before either the reset pulse or all DT DCS
writes.  That is a real control-flow difference.

It leaves two panel-side possibilities for a physical experiment: hidden
state cleared by reset, and the different inter-command delays.  Neither is
an observed register or wire-level difference, and neither proves an
explanation for the cyclic geometry or colour change.  The audit rules out a
different intended DCS payload, vendor page, MADCTL, address window, pixel
format, lane count, burst setting, or DSI DPI coding as the explanation.
