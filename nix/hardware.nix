# The T-Display-K230 as real hardware.
#
# NO BOOTLOADER IS CONFIGURED HERE, and that is deliberate.
#
# a-riscv-nixos-closure-cross-builds used
# boot.loader.generic-extlinux-compatible on the assumption that vendored
# U-Boot reads extlinux. Reading the SDK's environment showed it does not
# (docs/evidence/uboot-env.txt). Its default `bootcmd` runs a hardcoded
# command and never calls `sysboot`:
#
#   blinux = k230_set_dtb &&
#            ext4load mmc 1:1 0x3000000 /fw_jump_add_uboot_head.bin &&
#            ext4load mmc 1:1 0x200000  /Image &&
#            ext4load mmc 1:1 0x2200000 /force.dtb &&
#            bootm 0x3000000 - 0x2200000;
#
# So stage 1 wants three files at the root of an ext4 filesystem on the
# first partition of mmc 1, by exact name. The SD image derivation places
# them; there is no NixOS bootloader module that produces this shape, and
# inventing one before anything has booted would be guessing.
#
# The cost is real and worth stating: with fixed filenames there is exactly
# one kernel on the card, so NixOS generations cannot be selected at boot.
# The fix later is to rewrite the U-Boot environment -- which lives as plain
# data at 3M and 3.5M, separate from the SPL and U-Boot binaries -- to run
# `sysboot`. That is deferred until something boots at all, because a
# bringup failure and a bootloader-configuration failure look identical from
# a dark screen.
{ pkgs, lib, k230Kernel, ... }:

{
  # Mainline cannot boot this SoC -- no K230 device tree, no
  # SOC_CANAAN_K230 -- so the board runs the Xuantie kernel, built from
  # source. See nix/kernel.nix.
  boot.kernelPackages = lib.mkForce k230Kernel;

  boot.loader.grub.enable = false;
  boot.loader.generic-extlinux-compatible.enable = false;

  # Nothing installs a bootloader onto the card: stage 1 is already there,
  # vendored, and the image derivation lays our kernel where it looks. The
  # hook is a no-op so `nixos-rebuild` on the board does not fail for want
  # of a bootloader it must not touch.
  boot.loader.external = {
    enable = true;
    installHook = pkgs.writeShellScript "k230-no-bootloader-install" ''
      echo "stage 1 is vendored and already on the card; nothing to install." >&2
    '';
  };

  fileSystems."/" = {
    device = "/dev/disk/by-label/NIXOS_SD";
    fsType = "ext4";
  };

  # The boot partition stage 1 reads from: mmc 1:1, ext4, holding Image,
  # force.dtb and fw_jump_add_uboot_head.bin at its root.
  fileSystems."/boot" = {
    device = "/dev/disk/by-label/K230_BOOT";
    fsType = "ext4";
  };
}
