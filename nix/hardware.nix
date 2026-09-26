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
  k230WifiDriver = pkgs.callPackage ./k230-wifi-driver.nix {
    kernel = config.boot.kernelPackages.kernel;
  };
  wifiSettingsBroker = pkgs.callPackage ./wifi-settings-broker.nix { };
  splashOwnerEnabled = !config.k230.panelConsole && config.k230.shell.enable;
  k230SpeakerTest = pkgs.callPackage ./k230-speaker-test.nix { };
in
{
  imports = [ ./panel-console.nix ./root-growth-service.nix ];
  # Build the actual board closure against the tested RVV Pixman recipe.
  # Its hwprobe gate retains scalar dispatch when the kernel omits V or
  # PIXMAN_DISABLE=rvv is set. The overlay is board-only; QEMU keeps its
  # existing userspace package graph.
  nixpkgs.overlays = [
    (final: prev: {
      # Cross builds also evaluate this overlay for native buildPackages.
      # Enabling required RVV there makes x86 Meson reject Pixman before
      # the target renderer can build.
      pixman =
        if prev.stdenv.hostPlatform.system == "riscv64-linux"
        then prev.callPackage ./pixman-rvv.nix { pixman = prev.pixman; }
        else prev.pixman;
    })
  ];
  k230.rootGrowth.enable = lib.mkDefault true;
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

  # cfg80211 is built into the Xuantie kernel and requests regulatory.db
  # before /init runs.  This board intentionally has no initrd modules, so
  # the module-closure firmware walk has no dependency through which it can
  # discover the database.  Copy the database and its signature explicitly;
  # modules-closure accepts these uncompressed names and selects the .zst
  # files supplied by wireless-regdb when it constructs the initrd.
  boot.initrd.extraFirmwarePaths = [
    "regulatory.db"
    "regulatory.db.p7s"
  ];

  # The preflight captured an enumerated RTL8189FTV SDIO function without a
  # driver. 8189fs.ko is built for this exact kernel and loaded at boot so the
  # board can attempt a bind; binding is still a physical-board check.
  boot.extraModulePackages = [ k230WifiDriver ];
  boot.kernelModules = [ "8189fs" ];
  # Keep protected-network identifiers out of verbose Realtek kernel messages.
  boot.extraModprobeConfig = "options 8189fs rtw_drv_log_level=0";

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
    # wpa_supplicant provides both wpa_supplicant and wpa_cli. dhcpcd is
    # already enabled by the base NixOS networking configuration.
    iw
    wpa_supplicant
    wireless-regdb

    # the-handheld-plays-through-its-speaker: neither the Inno codec's
    # line-out nor the optional MAX98357A route had ever been exercised by
    # any userspace tool before this change.
    #
    #   alsa-utils   amixer/aplay/speaker-test -- the actual playback and
    #                the "External I2S Output Switch" route control added
    #                by nix/patches/canaan-audio-external-i2s-switch.patch
    #   libgpiod     gpioset/gpioget/gpiodetect/gpioinfo -- GPIO34 is the
    #                MAX98357A's plain SDMODE shutdown/enable pin (not
    #                behind the XL9555 expander; see
    #                docs/evidence/max98357a-speaker.md), and this kernel
    #                has no CONFIG_GPIO_SYSFS to fall back to
    alsa-utils
    libgpiod
    k230SpeakerTest
  ];

  # A root operator may place a protected wpa_supplicant configuration at
  # /var/lib/k230/wifi/wpa_supplicant.conf after deployment.  No credential is
  # declared here: the condition makes the unit a no-op on a fresh image, and
  # LoadCredential copies the operator file into this service's private
  # credential directory instead of adding it to the Nix store.
  systemd.tmpfiles.rules = [
    "d /var/lib/k230 0700 root root -"
    "d /var/lib/k230/wifi 0700 root root -"
  ];
  systemd.services.k230-wifi = {
    description = "K230 persistent Wi-Fi supplicant";
    wantedBy = [ "multi-user.target" ];
    requires = [ "sys-subsystem-net-devices-wlan0.device" ];
    bindsTo = [ "sys-subsystem-net-devices-wlan0.device" ];
    after = [
      "local-fs.target"
      "sys-subsystem-net-devices-wlan0.device"
    ];
    before = [ "network-online.target" ];
    unitConfig.ConditionPathExists = "/var/lib/k230/wifi/wpa_supplicant.conf";
    path = [ pkgs.coreutils ];
    preStart = ''
      install -d -o root -g root -m 0700 /run/k230-wifi/wpa_supplicant/client
      install -o root -g root -m 0600 /dev/null /run/k230-wifi/wpa.log
    '';
    script = ''
      exec ${pkgs.wpa_supplicant}/bin/wpa_supplicant \
        -f /run/k230-wifi/wpa.log \
        -i wlan0 \
        -c "$CREDENTIALS_DIRECTORY/wpa_supplicant.conf"
    '';
    serviceConfig = {
      Type = "simple";
      LoadCredential = "wpa_supplicant.conf:/var/lib/k230/wifi/wpa_supplicant.conf";
      RuntimeDirectory = "k230-wifi";
      RuntimeDirectoryMode = "0700";
      UMask = "0077";
      StandardOutput = "null";
      StandardError = "null";
      Restart = "on-failure";
      RestartSec = "5s";
    };
  };

  # The shell can request scan/connect/forget only through this broker. Its
  # runtime socket is root:shell 0660 and every peer is checked against the
  # shell UID. The candidate supplicant's files live below private/ (0700).
  # A separately scheduled restore timer is armed before the broker stops
  # k230-wifi, so a broker crash cannot strand the previous service forever.
  systemd.services.k230-wifi-settings = lib.mkIf config.k230.shell.enable {
    description = "Private Wi-Fi Settings broker";
    wantedBy = [ "multi-user.target" ];
    after = [ "systemd-tmpfiles-setup.service" ];
    path = [ pkgs.systemd pkgs.iproute2 pkgs.iw pkgs.wpa_supplicant ];
    serviceConfig = {
      Type = "simple";
      User = "root";
      Group = "shell";
      ExecStart = "${wifiSettingsBroker}/bin/k230-wifi-settings-broker --socket /run/k230-wifi-settings/broker.sock";
      RuntimeDirectory = "k230-wifi-settings";
      RuntimeDirectoryMode = "0750";
      UMask = "0077";
      StandardOutput = "null";
      StandardError = "null";
      Restart = "on-failure";
      RestartSec = "2s";
      KillMode = "control-group";
    };
  };

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

  # --- the-panel-brightness-is-adjustable ---------------------------------
  # The kernel now registers a real /sys/class/backlight device (see
  # nix/kernel.nix); tools/device_settings.py already reads and writes
  # /sys/class/backlight/*/brightness generically and already runs as the
  # unprivileged `shell` user (nix/shell.nix defines that user/group; the
  # Rust shell client spawns k230-settings directly, no sudo). The only
  # remaining gap is write permission on that sysfs attribute. A udev rule
  # is the narrowest of the three options the working agreement names (a
  # udev rule, a group, or a helper-daemon broker) -- see
  # openspec/changes/the-panel-brightness-is-adjustable/design.md decision 7.
  services.udev.extraRules = ''
    SUBSYSTEM=="backlight", ACTION=="add", RUN+="${pkgs.coreutils}/bin/chgrp shell /sys/class/backlight/%k/brightness", RUN+="${pkgs.coreutils}/bin/chmod g+w /sys/class/backlight/%k/brightness"
  '';

  # --- the-handheld-talks-bluetooth ---------------------------------------
  # The kernel's Bluetooth stack and USB HCI driver are enabled in
  # nix/kernel.nix; this is the standard NixOS module that runs BlueZ on
  # top of them. No device tree change, no new package beyond what this
  # module already pulls in.
  hardware.bluetooth.enable = true;

  # --- the-clock-survives-a-reboot -----------------------------------------
  # RTC_DRV_K230 (nix/kernel.nix) makes /dev/rtc0 exist; services.timesyncd
  # is already enabled by default and writes a synced time back to a
  # present RTC on its own. This unit makes that contract explicit and
  # independently auditable (systemctl status / the journal are the
  # evidence) rather than resting solely on timesyncd's internal ~hourly
  # write-back cadence. Ordered after time-sync.target, not merely after
  # systemd-timesyncd starts, so it never writes an unsynced time -- see
  # openspec/changes/the-clock-survives-a-reboot/design.md decision 2.
  systemd.services.k230-rtc-sync = {
    description = "Write the synchronized system clock to the K230 RTC";
    after = [ "time-sync.target" ];
    wants = [ "time-sync.target" ];
    wantedBy = [ "multi-user.target" ];
    unitConfig.ConditionPathExists = "/dev/rtc0";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.util-linux}/bin/hwclock --systohc";
    };
  };
}
