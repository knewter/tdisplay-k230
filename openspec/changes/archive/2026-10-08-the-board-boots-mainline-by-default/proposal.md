## Why

The full coherent shell now runs on the mainline kernel with display, touch,
power key, Wi-Fi, firewall, thermal and audio playback proven on the board
(`docs/evidence/mainline-shell-parity-2026-10-06/`), but every power-on still
boots the vendor 6.6 kernel. Until mainline is what the board boots by default,
people using the handheld do not get it, and each mainline result stays a trial.

## What Changes

- The daily boot (the files stage 1 loads from `/boot` plus the system profile)
  becomes the mainline full coherent shell, installed with the existing
  rollback-retaining installer (`tools/coherent-shell-board-install.py`).
- A mainline boot bundle in the coherent boot-files layout is added to the flake.
- Before the switch is trusted, a rollback drill is performed on the board:
  install mainline, roll back to the vendor kernel, reinstall mainline, each
  step verified after a reboot.
- The board-side trial tooling's notion of the "protected normal" system is
  updated so future trials guard the new default instead of the old one.

Non-goals: deleting the vendor kernel or its configuration from the repo (it
remains the rollback target and a buildable configuration), touching stage 1
(SPL/U-Boot/OpenSBI) or the DT selector files, upstreaming, and the items the
parity change left open (audible headset check, GPU, second core, NPU, camera).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `system/kernel`: the default boot runs the mainline kernel, with a proven way
  back to the vendor kernel.
- `system/nixos-config`: the installed daily system is the mainline coherent
  shell, and the trial tooling guards that system as the protected normal.

## Impact

- Nix: `flake.nix` gains a mainline coherent boot-files output (reusing
  `nix/coherent-shell-boot-files.nix`).
- Board: `/boot` mutable files (`Image`, `initrd.uimg`, `k230-tdisplay.dtb`,
  `bootargs.txt`) and `/nix/var/nix/profiles/system` change; stage 1 and
  `fw_jump_add_uboot_head.bin`/`force_dtb`/`lcd_dtb`/`hdmi_dtb` do not. Every
  step needs the physical board and the serial console; the rollback drill and
  install each need at least one reboot and possibly an operator reset.
- Tooling: normal-baseline expectations in `tools/` (vendor `6.6.36`, vendor
  system path) move to the installed mainline identities.
- Recovery beyond the installer's rollback: the USB `ums` path (`tools/ums-session.py`)
  can restore `/boot` from the host if a boot fails before userspace.
