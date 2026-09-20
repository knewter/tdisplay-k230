# The NixOS system for the T-Display-K230.
#
# Minimal on purpose: riscv64-linux has no binary cache, so every package here
# is compiled on every clean build. See openspec/specs/system/nixos-config —
# anything added needs a recorded reason it is needed to reach or use a prompt.
{ lib, modulesPath, ... }:

{
  imports = [ "${modulesPath}/profiles/minimal.nix" ];

  # Built on x86_64, runs on the board. Cross-compilation is the default path;
  # see openspec/specs/image/cross-build.
  nixpkgs.buildPlatform = "x86_64-linux";
  nixpkgs.hostPlatform = "riscv64-linux";

  # The console is serial at 115200 8N1 in both worlds. On hardware that is the
  # CH342 bridge on the charging USB-C port (1a86:55d2, two CDC-ACM ports);
  # under QEMU it is the emulated UART. Matching the rate means one transcript
  # format serves both, and the first hardware boot differs from a known-good
  # QEMU boot in as few ways as possible.
  boot.kernelParams = [ "console=ttyS0,115200n8" ];

  # No display, no keyboard, no network needed to reach a prompt.
  # system/nixos-config requires all three to be unnecessary.
  services.getty.autologinUser = "root";
  users.users.root.password = "";

  # No graphical stack. The panel is a later change
  # (the-screen-comes-up-under-linux) and nothing here should pull one in.
  documentation.enable = false;
  documentation.nixos.enable = false;

  # Keeps the closure honest: without a cache, a firmware tree we cannot use
  # is pure compile time.
  hardware.enableRedistributableFirmware = false;

  # Stage 1 is vendored U-Boot, which reads extlinux. Writing an extlinux
  # config is therefore how our kernel gets found on hardware; GRUB is not
  # involved anywhere. Under QEMU the kernel is loaded directly and none of
  # this runs -- that difference is recorded in
  # docs/evidence/boot-path-differences.md.
  boot.loader.grub.enable = false;
  boot.loader.generic-extlinux-compatible.enable = true;

  fileSystems."/" = {
    device = "/dev/disk/by-label/NIXOS_SD";
    fsType = "ext4";
  };

  system.stateVersion = "25.05";
}
