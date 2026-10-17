## 1. Host

- [x] 1.1 Enable `CMA`, `DMA_CMA` and `CMA_SIZE_MBYTES=64` in
  `nix/kernel-mainline-drm.nix`, and pin `output HDMI-A-1 mode 1280x800` in
  `nix/shell.nix`. Verify by building the board boot files
  (`nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles`) and by checking
  the built kernel's config for `CONFIG_DMA_CMA=y` and
  `CONFIG_CMA_SIZE_MBYTES=64`.
  Done 2026-10-16: `docs/evidence/hdmi-plug-cma/board-2026-10-16.md`.
- [ ] 1.2 Remove `bg #000000 solid_color` from the HDMI-A-1 output line in
  `nix/shell.nix`. On a 2026-10-16 hotplug, Sway's swaybg for HDMI-A-1
  covered the shell's wallpaper. Both are background-layer surfaces, and
  swaybg's black stacked on top; stopping that swaybg showed the vinyl
  wallpaper. Verify by building the board boot files and checking the built
  sway config has no `bg` on that line, then on the board: replug HDMI and
  capture the wallpaper with `grim`.

## 2. Board

- [x] 2.1 Install and reboot. Record the boot log's CMA reservation line and
  `CmaTotal`/`CmaFree` from `/proc/meminfo`.
  Done 2026-10-16 (board, soft reboot 15:40): `cma: Reserved 64 MiB`,
  `CmaTotal: 65536 kB`, `CmaFree: 63016 kB`; same evidence file.
- [ ] 2.2 After at least an hour of uptime that includes shell restarts and
  theme changes, the operator plugs in the monitor. Record that the
  compositor log has no dumb-buffer allocation failure for the chosen mode,
  that HDMI comes up at 1280x800, and the operator's report that the monitor
  shows the shell.
