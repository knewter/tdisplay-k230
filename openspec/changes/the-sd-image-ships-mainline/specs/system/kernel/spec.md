## ADDED Requirements

### Requirement: The flashable default image ships the mainline coherent shell
`nix build .#sdImage` SHALL produce a card image whose root holds the
`k230-mainline-drm-shell` system and whose boot partition holds that system's
mainline kernel, its initrd, and the mainline DRM device tree under the
filename stage 1 loads, with stage 1 unchanged.

#### Scenario: Host inspection of the built image
- **WHEN** someone builds `.#sdImage` and inspects its boot partition
- **THEN** `Image` is the mainline 7.3.0-rc5 kernel of `k230-mainline-drm-shell`, `k230-tdisplay.dtb` carries the mainline DRM tree with `/chosen/bootargs` selecting that system's init, and the stage-1 slots match `.#stage1`
<!-- UNVERIFIED: not yet built -->

#### Scenario: A freshly flashed card boots to the shell
- **WHEN** the image is flashed to a card and the board is powered on
- **THEN** the serial console reports kernel 7.3.0-rc5 and the shell services become active
<!-- UNVERIFIED: requires an operator-scheduled flash that erases the current card -->

## MODIFIED Requirements

### Requirement: A parallel mainline kernel build exists and does not affect the default system

The project SHALL provide a mainline-Linux kernel, device-tree, and
boot-files build (`.#kernelMainline`, `.#deviceTreeMainline`,
`.#kernelMainlineBootFiles`) pinned to the newest mainline revision carrying
basic Canaan K230 support, built entirely separately from the pinned vendor
Xuantie kernel `.#kernel` uses. No vendor package or vendor
`nixosConfigurations` output SHALL depend on or be changed by this build
existing. `.#sdImage` deliberately ships the mainline system (see "The
flashable default image ships the mainline coherent shell").

*Grounding: `nix/kernel-mainline-src.nix` pins `torvalds/linux` at the
dereferenced `v7.3-rc5` commit — the newest tag with
`arch/riscv/boot/dts/canaan/k230.dtsi` present, confirmed absent at `v7.2`
by direct tag diff. `nix/kernel-mainline.nix` and
`nix/device-tree-mainline.nix` share no code path with `nix/kernel.nix` or
`nix/device-tree.nix`; `flake.nix`'s new `kernelMainline`/
`deviceTreeMainline`/`kernelMainlineBootFiles` outputs are additive only.*

#### Scenario: Someone builds the mainline kernel

- **WHEN** someone runs `nix build .#kernelMainline`
- **THEN** it exits 0 and produces a riscv64 kernel Image, independent of
  whether `.#kernel` has ever been built

#### Scenario: Someone builds the default system

- **WHEN** someone builds `.#nixosConfigurations.k230.config.system.build.toplevel`
  or `.#sdImage-coherent`
- **THEN** the result is byte-identical to what it would be if
  `nix/kernel-mainline.nix`, `nix/kernel-mainline-src.nix`,
  `nix/device-tree-mainline.nix`, and this change's other new files did not
  exist

### Requirement: The board boots the mainline kernel by default with a proven way back
Powering on or rebooting the board SHALL boot the mainline kernel and the full
coherent shell without operator intervention, and the vendor 6.6 kernel SHALL
remain restorable as the default by a recorded, tested rollback.

#### Scenario: Power-on reaches the shell on mainline
- **WHEN** the board is reset or rebooted after installation
- **THEN** the serial console reports kernel 7.3.0-rc5, the installed mainline system is booted, and the shell services are active with no failed units
*Grounding: observed on hardware 2026-10-07/08 (`docs/evidence/mainline-default-boot/README.md`): ordinary reboot after install and after reinstall, and one reset-button power-on (`reset-button-postboot.json`), each 7.3.0-rc5, mainline system/profile, three services active, `running`, no failed units.*

#### Scenario: Rollback restores the vendor kernel
- **WHEN** the operator runs the installer's rollback and reboots
- **THEN** the board boots the vendor 6.6 kernel with the previous system and boot files byte-identical to their recorded backups
*Grounding: observed on hardware 2026-10-07 (`docs/evidence/mainline-default-boot/README.md`): `install.py rollback` PASS with every restored file re-hashed against its backup, then an ordinary boot on 6.6.36 with the vendor profile.*

This selection is board state installed from `.#kernelMainlineDrmShellBootFiles`;
`.#sdImage` ships the same mainline system for freshly flashed cards.
