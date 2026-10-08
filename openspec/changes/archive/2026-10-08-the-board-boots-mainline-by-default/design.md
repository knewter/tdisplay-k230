## Context

See proposal.md - Why. Stage 1 loads `Image`, `initrd.uimg`,
`k230-tdisplay.dtb` (bootargs embedded under /chosen) and `bootargs.txt` from
`/boot` (`/dev/mmcblk1p1`), plus `fw_jump_add_uboot_head.bin` and the
`force_dtb`/`lcd_dtb`/`hdmi_dtb` selectors. `tools/coherent-shell-board-stage.py`
prepares a host-inspected bundle on the board with a checked backup of the
normal files; `tools/coherent-shell-board-boot.py` runs a trial boot;
`tools/coherent-shell-board-install.py` installs a touch-qualified bundle
(replacing only the four mutable files and the profile, preserving rollback GC
roots and a journal) and has a `rollback` mode. The mainline full shell
(`k230-mainline-drm-shell`) has only been booted through volatile U-Boot
selection by `tools/mainline-drm-system-trial.py`.

## Goals / Non-Goals

**Goals:** reuse the existing stage/trial/qualify/install path unchanged where
possible; prove rollback on the board before calling the switch done.

**Non-Goals:** new installer logic, stage-1 changes, removing the vendor path.

## Decisions

1. **Bundle (Nix layer).** Add `kernelMainlineDrmShellBootFiles` by calling
   `nix/coherent-shell-boot-files.nix` with `cfg = k230-mainline-drm-shell` and a
   device-tree wrapper that presents the mainline DRM DTB as `k230-tdisplay.dtb`
   (stage 1 loads that name). Rejected: changing stage 1's file names or boot
   script (touches the vendored chain and every rollback assumption).
2. **Path (board tooling).** Stage → coherent trial boot → touch qualification
   → install, using the existing tools. If a tool hard-codes vendor-only facts
   (kernel version, DTB node names), adapt it minimally with tests. Rejected:
   writing `/boot` by hand (no journal, no checked backup).
3. **Rollback drill.** After the first install and a verified mainline power-on,
   run `install.py rollback`, reboot, verify the vendor kernel and byte-identical
   backups, then reinstall mainline and verify again. Recovery of last resort is
   the U-Boot `ums` USB path.
4. **Protected normal moves.** Trial tools read a normal baseline/report; after
   install, regenerate it from the installed mainline system so future guarded
   trials protect the new default. Update tests that pin `6.6.36`.

## Risks / Trade-offs

- [A mainline-only regression appears only on cold power-on (CH342 re-enumeration,
  clock state left by a cold SPL)] → verify one reset-button power-on as well as
  warm reboots.
- [Installer assumptions about the vendor DTB or kernel] → found during the
  trial step, before `/boot` is written.
- [Features still vendor-only become unavailable by default: GPU/VGLite probes,
  NPU, second core, camera] → recorded as accepted limits; rollback stays available.
