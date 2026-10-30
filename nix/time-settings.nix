# The root half of Settings' time zone and network time controls
# (openspec/changes/settings-sets-the-time-zone-and-network-time). The board
# has no polkit, so timedated refuses the shell user. Instead a socket owned
# by root and the shell group starts one short-lived helper per request; it
# accepts only `zone <listed name>` and `network-time on|off`
# (tools/k230_time_helper.py). Nothing is resident between requests.
{ config, lib, pkgs, ... }:

let
  cfg = config.k230.shell;
  stateDir = "k230-time";
  networkTimeOff = "/var/lib/${stateDir}/network-time-off";
in
{
  config = lib.mkIf (cfg.enable && cfg.coherentShell) {
    systemd.sockets.k230-time = {
      description = "Settings time zone and network time requests";
      wantedBy = [ "sockets.target" ];
      socketConfig = {
        ListenStream = "/run/k230-time.sock";
        SocketUser = "root";
        SocketGroup = "shell";
        SocketMode = "0660";
        Accept = true;
        MaxConnections = 2;
        RemoveOnStop = true;
      };
    };

    systemd.services."k230-time@" = {
      description = "Apply one Settings time request";
      path = [ pkgs.systemd ];
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${../tools/k230_time_helper.py} --user shell --flag ${networkTimeOff}";
        StandardInput = "socket";
        StandardOutput = "socket";
        StandardError = "journal";
        User = "root";
        Group = "root";
        StateDirectory = stateDir;
        RuntimeMaxSec = 30;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ReadWritePaths = [ "/var/lib/${stateDir}" ];
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictNamespaces = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        UMask = "0022";
      };
    };

    # Network time off is a flag, not a disabled unit: NixOS keeps unit files
    # read-only, and the flag keeps timesyncd stopped across a reboot.
    systemd.services.systemd-timesyncd.unitConfig.ConditionPathExists = "!${networkTimeOff}";
  };
}
