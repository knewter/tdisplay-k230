# The nRF9151 modem service (openspec/changes/
# the-nrf9151-gives-the-handheld-cellular-sms-and-location, tasks 3.1/3.2).
#
# One root service, k230-modem, is the only process that opens /dev/ttyS3 and
# the `nrf9151-enable` GPIO line. It drives the line low at startup, so the
# modem stays off until a person turns Cellular or Location on (the choice is
# persisted in /var/lib/k230/modem/settings.json). The shell reads
# /run/k230/modem/state.json and writes /run/k230/modem/control; both are
# group `k230-modem`.
#
# Location: the service writes the modem's NMEA to the pty
# /run/k230/modem/nmea. gpsd is socket-activated on 127.0.0.1:2947 and opens
# that pty only when a client connects (no `-n`).
{ config, lib, pkgs, ... }:

let
  cfg = config.k230.modem;
  modem = pkgs.callPackage ./k230-modem { };
in
{
  options.k230.modem = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Run the modem service. The modem itself stays powered off at runtime
        until a person turns Cellular or Location on.
      '';
    };
    device = lib.mkOption {
      type = lib.types.str;
      default = "/dev/ttyS3";
      description = "The modem's UART.";
    };
    enableLine = lib.mkOption {
      type = lib.types.str;
      default = "nrf9151-enable";
      description = "The GPIO line name (device tree) that powers the modem.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ modem ];

    users.groups.k230-modem = { };
    # The shell user reads the state and uses the control socket.
    users.users.shell.extraGroups = lib.mkIf (config.k230.shell.enable) [ "k230-modem" ];

    # Keep any modem manager off the nRF9151's UART.
    services.udev.extraRules = ''
      SUBSYSTEM=="tty", KERNEL=="ttyS3", ENV{ID_MM_DEVICE_IGNORE}="1"
    '';

    systemd.services.k230-modem = {
      description = "nRF9151 modem service (power, SIM, SMS, GNSS)";
      wantedBy = [ "multi-user.target" ];
      unitConfig.ConditionPathExists = cfg.device;
      serviceConfig = {
        ExecStart = lib.concatStringsSep " " [
          "${modem}/bin/k230-modem"
          "--device ${cfg.device}"
          "--enable-line ${cfg.enableLine}"
          "--run-dir /run/k230/modem"
          "--state-dir /var/lib/k230/modem"
          "--group k230-modem"
        ];
        # Root for the GPIO and tty; the group makes the runtime and state
        # directories and every file in them readable by the shell user only.
        User = "root";
        Group = "k230-modem";
        UMask = "0027";
        RuntimeDirectory = "k230/modem";
        RuntimeDirectoryMode = "0750";
        RuntimeDirectoryPreserve = false;
        StateDirectory = "k230/modem";
        StateDirectoryMode = "0750";
        Restart = "on-failure";
        RestartSec = 5;
        # The service powers the modem down itself on SIGTERM.
        TimeoutStopSec = 30;
        NoNewPrivileges = true;
        ProtectHome = true;
        PrivateTmp = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
      };
    };

    # gpsd on demand against the NMEA pty. It runs as a transient user that
    # may read the pty through the k230-modem group, and it keeps no
    # positions: no -n, no logging, no cache on disk.
    systemd.sockets.k230-gpsd = {
      description = "gpsd client socket (starts gpsd on demand)";
      wantedBy = [ "sockets.target" ];
      listenStreams = [ "127.0.0.1:2947" ];
    };
    systemd.services.k230-gpsd = {
      description = "gpsd reading the modem's NMEA pty";
      requires = [ "k230-gpsd.socket" ];
      after = [ "k230-modem.service" ];
      serviceConfig = {
        ExecStart = "${pkgs.gpsd}/sbin/gpsd -N -b /run/k230/modem/nmea";
        DynamicUser = true;
        SupplementaryGroups = [ "k230-modem" ];
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectHome = true;
        ProtectSystem = "strict";
      };
    };
  };
}
