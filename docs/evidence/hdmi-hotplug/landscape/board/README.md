# Landscape HDMI on the board: Home and Settings (task 5.4)

Board image: master `6e963323` (`kernelMainlineDrmShellLandscapeHdmiBootFiles`,
landscape panel + landscape HDMI profile), installed system
`/nix/store/cn5bc5bkd3xylm8c3bf8mbpwv8kba9b7-nixos-system-nixos-26.11.20260919.20b1ddd`,
boot `1212fd5d-13da-4348-9234-aed00b283490`. Monitor: HP 27wm on HDMI-A-1,
Sway reports `1280x800 @ 59.910 Hz`, transform `normal`, power on; DSI-1 absent
(one CRTC).

Native captures, 2026-10-14 (CDT), taken with
`grim -o HDMI-A-1` as the `shell` user (`XDG_RUNTIME_DIR=/run/shell`,
`WAYLAND_DISPLAY=wayland-1`):

| File | Time | How the screen was reached |
| --- | --- | --- |
| `settings-hdmi-grim.png` | 23:46:26 | `settings` written to `/run/shell/k230-shell-rust.sock` (reply `OK`) |
| `home-hdmi-grim.png` | 23:46:59 | `hide` to the same socket; the session's start-up terminal (`app_id=k230-terminal`, from the Sway config's `exec … k230-foot terminal`) moved to the scratchpad for the capture, then restored with `scratchpad show, floating disable` |

What the captures show: Settings uses the wide layout -- Wi-Fi/Brightness/Volume
and Keyboard/Motion/Key backlight in two columns with Power (Reboot…, Power
off…) in a third, Themes › and Done at the right edge, nothing clipped or
overlapping. Home shows the clock and date at the left, the one Home tile
(Video) and the four-slot dock across the bottom with the handle below it.

Limits: these are compositor captures, not a monitor photograph (waived by
the operator 2026-10-09). The routes were opened over the shell socket, not by
touch. The operator's own observation of the monitor is recorded below.

## Operator observation

2026-10-14, after Settings was reopened on the monitor over the shell socket
and the operator was asked to close it and view Home: the operator answered
"Both look right" to "Do Home and Settings look right, with nothing broken,
clipped or overlapping?". This is the operator's word on the physical monitor;
no camera recorded it.
