# Importable NixOS module for the touchscreen-to-touchpad relay. Enabled
# by the explicit coherent-shell HDMI trial configuration after its
# standalone board safety trial; other configurations retain direct touch.
# See
# openspec/changes/the-touchscreen-becomes-an-hdmi-trackpad/ for the
# capability and tasks.md's physical trial steps for the
# operator-facing instructions this module implements.
{ config, lib, pkgs, ... }:

let
  cfg = config.k230.touchTrackpad;
  package = pkgs.callPackage ./touch-trackpad { };
in
{
  options.k230.touchTrackpad = {
    enable = lib.mkEnableOption "the HDMI-mode touchscreen-to-touchpad relay (prototype)";
  };

  config = lib.mkIf cfg.enable {
    systemd.services.k230-touch-trackpad = {
      description = "Re-emit the touchscreen as a virtual touchpad while HDMI is the active output (prototype)";
      documentation = [ "https://github.com/knewter/tdisplay-k230/blob/master/openspec/changes/the-touchscreen-becomes-an-hdmi-trackpad/proposal.md" ];
      # After the shell/seatd so /sys/class/drm reflects the booted output
      # before the first mode check, and so a crash-restart loop here can
      # never be mistaken for the shell session itself failing.
      after = [ "shell.service" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "simple";
        ExecStart = lib.getExe package;
        Restart = "always";
        RestartSec = 2;
        TimeoutStopSec = 2;
        # Root: EVIOCGRAB on the touchscreen node and creating a uinput
        # device both need it on this image (no udev "uaccess"-style seat
        # ACL is configured for /dev/uinput or /dev/input/event* here,
        # unlike the interactive host this was prototyped on -- see
        # design.md's "Permissions" decision for why narrowing this to a
        # dedicated user + udev rule is follow-on work, not done in this
        # prototype). DeviceAllow still bounds it to exactly the two
        # device classes it touches, even running as root.
        DevicePolicy = "closed";
        DeviceAllow = [
          "/dev/uinput rw"
          "char-input rw" # /dev/input/event* (major 13)
        ];
        ProtectSystem = "strict";
        ProtectHome = true;
        NoNewPrivileges = true;
      };
    };
  };
}
