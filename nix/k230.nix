# Shared base for the T-Display-K230, common to hardware and QEMU.
#
# What is NOT here is the root filesystem and the bootloader, because the two
# targets genuinely differ and pretending otherwise is how the first hardware
# boot turns into a mystery:
#
#   hardware.nix  vendored U-Boot reads extlinux, root on the SD card
#   qemu.nix      QEMU loads the kernel directly, root in an initrd
#
# QEMU's k230 machine models no block device and no network -- only UARTs,
# SSI flash, DMA and a GZIP engine -- so a disk root is not available there
# at all. See docs/evidence/boot-path-differences.md.
#
# Minimal on purpose: riscv64-linux has no binary cache, so every package here
# is compiled on every clean build. See openspec/specs/system/nixos-config —
# anything added needs a recorded reason it is needed to reach or use a prompt.
{ config, lib, modulesPath, ... }:

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
  services.getty.autologinUser = lib.mkDefault "root";
  users.users.root.password = "";

  # No graphical stack. The panel is a later change
  # (the-screen-comes-up-under-linux) and nothing here should pull one in.
  documentation.enable = false;
  documentation.nixos.enable = false;

  # Keeps the closure honest: without a cache, a firmware tree we cannot use
  # is pure compile time.
  hardware.enableRedistributableFirmware = false;

  # make-ext4-fs writes this registration stream into the SD root image but,
  # unlike nixos/modules/installer/sd-card/sd-image.nix, our custom image
  # builder does not import the module that consumes it.  A fresh card can
  # therefore contain all store files yet have an empty Nix database: `nix
  # shell` cannot see packages and the system profile is absent.  Keep the
  # upstream ordering and one-shot semantics, with the marker as the guard.
  systemd.services.register-nix-paths = {
    description = "Register Nix Store Paths";
    unitConfig = {
      DefaultDependencies = false;
      ConditionPathExists = "/nix-path-registration";
    };
    wantedBy = [ "sysinit.target" ];
    before = [
      "sysinit.target"
      "shutdown.target"
      "nix-daemon.socket"
      "nix-daemon.service"
    ];
    after = [ "local-fs.target" ];
    conflicts = [ "shutdown.target" ];
    restartIfChanged = false;
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      ${lib.getExe' config.nix.package.out "nix-store"} --load-db < /nix-path-registration
      touch /etc/NIXOS
      ${lib.getExe' config.nix.package.out "nix-env"} -p /nix/var/nix/profiles/system --set /run/current-system
      rm -f /nix-path-registration
    '';
  };

  system.stateVersion = "25.05";
}
