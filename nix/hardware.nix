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
{ config, pkgs, lib, k230Kernel, bootSplashImage, ... }:

let
  drmSplash = pkgs.callPackage ./drm-splash { inherit bootSplashImage; };
  splashOwnerEnabled = !config.k230.panelConsole && config.k230.shell.enable;
in
{
  imports = [ ./panel-console.nix ];
  # Mainline cannot boot this SoC -- no K230 device tree, no
  # SOC_CANAAN_K230 -- so the board runs the Xuantie kernel, built from
  # source. See nix/kernel.nix.
  boot.kernelPackages = lib.mkForce k230Kernel;

  # NixOS's default initrd module list is PC hardware -- ahci, ata_piix,
  # sd_mod, usbhid and friends. None of it exists on this board, and with
  # autoModules off the kernel does not build it either, so the initrd
  # build fails outright:
  #
  #   modprobe: FATAL: Module ata_piix not found
  #
  # Turn the defaults off and name what this board actually needs. The
  # k230_defconfig builds MMC, SDHCI and ext4 in, so the initrd needs no
  # modules at all to find the root filesystem.
  boot.initrd.includeDefaultModules = false;
  boot.initrd.availableKernelModules = lib.mkForce [ ];
  boot.initrd.kernelModules = lib.mkForce [ ];

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

  # loglevel=4 (the nixpkgs default) drops KERN_INFO on the console, which
  # is every drm and panel message and every dev_info we add. That is fine
  # when a shell is reachable and `dmesg` works, and useless when the board
  # hangs during bring-up -- which is exactly when the messages are needed.
  # Observed: a soft lockup in the panel path with nothing on the console to
  # say where. Revert to 4 once the panel is up and boots are quiet again.
  # mkAfter matters: the kernel takes the LAST loglevel on the command line,
  # and nixpkgs' own "loglevel=4" is already there. Without mkAfter this
  # lands before it and is silently overridden -- caught by reading
  # bootargs.txt out of the built image rather than trusting the option.
  # Two orderings in one definition, because Nix will not let the same
  # attribute be declared twice in one attrset.
  #
  # When k230.panelConsole is selected, console=tty0 goes FIRST via
  # mkBefore. It must not be last, because the
  # LAST console= on the command line becomes /dev/console, and ttyS0 has
  # to stay primary -- losing the serial console on a board whose panel is
  # still being brought up would be a bad trade.
  #
  # loglevel=7 LAST, via mkAfter: nixpkgs contributes its own loglevel=4
  # and the kernel honours whichever comes last.
  boot.kernelParams =
    lib.mkMerge [
      # consoleblank=0: Linux blanks the console after 10 minutes idle,
      # and nothing writes to tty0 once boot finishes, so the panel goes
      # dark and looks broken. It is not.
      (lib.mkBefore (lib.optional config.k230.panelConsole "console=tty0"
        ++ [ "consoleblank=0" ]))
      (lib.mkAfter [ "loglevel=7" ])
    ];

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

  # Four tools that exist only so the display and touch tasks can be verified
  # ON the board rather than asserted from the build host. system/nixos-config
  # asks for a recorded reason per package, so:
  #
  #   fbset      the-screen-comes-up-under-linux 3.1 -- `fbset -i` is the
  #              named evidence that a 568x1232 framebuffer exists
  #   libdrm     modetest, to tell "the panel bound" apart from "a framebuffer
  #              node appeared", which task 3.2 explicitly refuses to accept
  #   evtest     task 4.3 -- the committed drag transcript, and the only way
  #              to see whether the axes are swapped or mirrored
  #   i2c-tools  task 4.1 -- probe the GT9895 at 0x5d to separate "the driver
  #              did not bind" from "the part is not answering at all"
  #
  # riscv64 has no binary cache, so each of these is compile time on every
  # clean build. They are here because the tasks name them, and they should
  # leave with the change that needed them.
  environment.systemPackages = with pkgs; [
    fbset
    libdrm
    evtest
    i2c-tools
  ];

  # The image owner only exists on splash boots.  The current daily image
  # selects panelConsole and therefore retains the verified console path.
  systemd.services.k230-drm-splash = lib.mkIf splashOwnerEnabled {
    description = "Static DRM owner for the K230 stage-1 splash";
    wantedBy = [ "multi-user.target" ];
    before = [ "shell.service" "multi-user.target" ];
    after = [ "systemd-udev-settle.service" ];

    serviceConfig = {
      Type = "simple";
      User = "shell";
      Group = "shell";
      RuntimeDirectory = "k230-drm-splash";
      RuntimeDirectoryMode = "0700";
      ExecStart = "${drmSplash}/bin/k230-drm-splash --ready-file /run/k230-drm-splash/state";
      KillSignal = "SIGTERM";
      TimeoutStopSec = "5s";
      Restart = "on-failure";
      RestartSec = 1;
    };
  };
}
