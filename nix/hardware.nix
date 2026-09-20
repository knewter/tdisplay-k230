# The T-Display-K230 as real hardware.
#
# Stage 1 is vendored U-Boot, which reads extlinux -- so writing an extlinux
# config is how our kernel gets found. GRUB is not involved anywhere.
#
# Nothing in this file is exercised by `a-riscv-nixos-closure-cross-builds`:
# QEMU's k230 machine has no block device, so this path is first proven by
# `the-board-boots-what-we-built`.
{ ... }:

{
  boot.loader.grub.enable = false;
  boot.loader.generic-extlinux-compatible.enable = true;

  fileSystems."/" = {
    device = "/dev/disk/by-label/NIXOS_SD";
    fsType = "ext4";
  };
}
