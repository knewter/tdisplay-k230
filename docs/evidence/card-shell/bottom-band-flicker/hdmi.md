# Bottom-band flicker on HDMI: same fix, `max_render_time 8` (2026-10-15)

Evidence class: **operator report on the real monitor** plus a phone video
the operator recorded of the monitor. No grim capture shows the band (see
below).

**System:** `/nix/store/d3p5n719gbhc91vyqjbgxh0zicr9c3jw-nixos-system-nixos-26.11.20260919.20b1ddd`
(landscape 7.2 test image), HDMI-A-1 at 1280x800, panel switched off.

**Symptom.** On Home, moving the mouse anywhere from the bottom edge to
about one dock height above the dock flickered a dark band across the
full width. Moving it elsewhere did not. Apps and the card overview did not
flicker.

`hdmi-dock-band-phone-frames.png` shows three frames from the operator's
3 s phone video (`video_2026-10-15_13-46-58.mp4`, sha256
`00fa2990…57ee`, not committed). Each frame is cropped to the dock and
turned so the dock runs across the image. Top: correct. Middle: starting to
darken. Bottom: the band, a dark translucent layer with the dock icons and
wallpaper still faintly visible through it.

**What didn't cause it:**
- Dumb-buffer cache maintenance. A test kernel cleaned every framebuffer
  before each plane update, and the band was unchanged.
- The hardware cursor plane running past the bottom edge. The canaan VO
  driver does program the unclipped cursor rectangle (debugfs:
  `crtc-pos=64x64+639+797` on an 800-line mode). A test kernel clipped it,
  and the band was unchanged. With `WLR_NO_HARDWARE_CURSORS=1`, the band
  was also unchanged.
- Home's own pixels. A host render of `draw_home_shm` at 1280x800 with the
  pointer at y = 300 to 790 differed from the no-pointer render in 0
  pixels. Hover only makes Home repaint and re-commit.

**Cause, as for DSI-1 (`max-render-time-fix.md`).** Every pointer motion
over Home makes the shell commit a new frame, so Sway composites
continuously. With `max_render_time` 0, Sway renders right after the
previous flip. Apps and the overview stay idle under a moving pointer,
which is why they did not flicker. HDMI frames are ARGB8888 (`AR24`,
1280x800, about 4 MiB), versus RGB565 on the panel.

**Fix.** At 15:21:14 CDT (sway journal: `Handling command 'output HDMI-A-1 max_render_time 8'`), `swaymsg output HDMI-A-1 max_render_time 8` was
applied at runtime (`get_outputs` showed `max_render_time` 0 → 8). The
operator then moved the mouse over the dock again and reported "band's
gone". It is now in `nix/shell.nix`'s `output HDMI-A-1` line.

**Limits.**
- The acceptance is the operator's look, not a frame capture after the
  fix.
- Screencopy (`grim`) cannot show this band because it reads the composed
  frame, not the scan-out.
- As on the panel, a rendered frame can add up to 8 ms of latency.

**The config line on the board.** The build carrying it, system
`/nix/store/wyxsfdsy2m835dy2fgw4f7q9ndjr7xhz-nixos-system-nixos-26.11.20260919.20b1ddd`,
was booted at 15:27 CDT. `swaymsg -t get_outputs` showed HDMI-A-1 active
with `max_render_time` 8. The sway journal for that boot has no runtime
`output HDMI-A-1 max_render_time` command, so the value comes from the
config.
