# Can the K230 display path rotate in scanout?

Question from the coordinator, 2026-10-30. Read-only board access (two short
lock holds, no module loaded, shell untouched) plus source reading.

## Result: only the YUV video layer rotates; the RGB planes the shell uses do not

**Board (`modetest -p`, `modetest-p.txt`; `drm-planes-readonly.txt` from
`/sys/kernel/debug/dri/0/state`; boot `0b49504f-...`, system `49mnsl2s...`):**
seven planes. Plane 47 is the only one with a `rotation` property
(`rotate-0 rotate-90 rotate-270 reflect-x reflect-y`), and its formats are
`NV12 NV21 NV16 NV61` only. The four OSD planes (`AR24 AR12 AR15 RG24 RG16 BG24`,
including the primary plane 37 that sway scans out as `RG16`) have no
`rotation` property. The two other video planes (NV12) have none either. The
live primary plane scans out `568x1232 RG16` at `0,0`.

**Source (`nix/patches/mainline/drm/canaan_vo.c`):** `canaan_vo_update_layer1()`
programs rotation (90/270/mirror) into `VO_LAYER1_CTL` bits 4-7 and swaps the
active width/height, and is the only plane with `.supported_rotations` set
(`canaan_plane_configurations[6]`, "video_3"/layer1, line ~807); the OSD update
function (`canaan_vo_update_osd`) writes format, size, address, stride only. The
format switch in the layer-1 function rejects anything but NV12/NV21/NV16/NV61.
The vendor tree (`7d4e1f44...`, `drivers/gpu/drm/canaan/`) has the same plane
table and no OSD rotation register use.

**Panel controller (RM69A10):** the vendor init sequence
(`nix/dts/display-rm69a10-568x1232.dtsi`, `docs/evidence/rm69a10-init-sequence.md`)
never writes MADCTL (0x36); it sets column/page address (0x2A/0x2B), normal mode,
tearing, brightness, pixel format. MIPI DCS defines MADCTL bits for flips and a
row/column exchange, but (1) no RM69A10 document is in the repo and a datasheet
would not be grounding anyway, (2) the VO streams the panel in DSI video mode,
line by line at 568 pixels, and a transposition inside the controller would need
the whole frame buffered, which video mode does not provide. Not tested on the
panel (no safe read-back path without driver changes); treated as **not
available, UNVERIFIED on hardware**.

## What that means

- **No rotation for RGB scanout.** The shell's frame is RGB565/ARGB8888, so the
  CPU turn (4.0 ms CPU per full frame) or a GPU turn (0.2 ms CPU, 18.9 ms wall)
  remains the only ways to turn it. I did not run the test-pattern measurement
  because there is no rotating RGB plane to measure.
- **YUV route rejected for the UI.** Feeding layer 1 would need an RGB to NV12
  conversion of every frame: more arithmetic than the turn it replaces, 4:2:0
  chroma that smears coloured text, and VG-Lite cannot write YUV
  (`gcFEATURE_VG_YUV_OUTPUT 0` in the pinned SDK `vg_lite_options.h`).
- **One real opening, for video only (UNVERIFIED, not pursued):** the video
  wallpaper's decoder output is NV12, which layer 1 can scan out rotated by the
  display hardware with no CPU turn. Making that useful would need the UI on an
  ARGB8888 OSD plane blended by the VO over the video layer instead of sway
  compositing the wallpaper itself, a compositor architecture change whose
  blending order and alpha behaviour have not been checked on this board.
