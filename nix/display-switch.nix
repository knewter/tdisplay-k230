{ config, lib, pkgs, ... }:
let
  cfg = config.k230.displaySwitch;
  manifest = pkgs.writeText "k230-display-switch.json" (builtins.toJSON {
    kernel = "${config.boot.kernelPackages.kernel}/Image";
    panel = "${cfg.panelDeviceTree}/k230-tdisplay-mainline-drm.dtb";
    hdmi = "${cfg.hdmiDeviceTree}/k230-tdisplay-mainline-drm-hdmi.dtb";
    mount = "${pkgs.util-linuxMinimal.mount}/bin/mount";
    fdtput = "${pkgs.dtc}/bin/fdtput";
    systemctl = "${config.systemd.package}/bin/systemctl";
  });
  command = pkgs.writeShellScriptBin "k230-display-switch" ''
    exec ${pkgs.python3}/bin/python3 -I ${../tools/display_switch.py} --config ${manifest} "$@"
  '';
in {
  options.k230.displaySwitch = {
    enable = lib.mkEnableOption "one-shot HDMI boot selection from Settings";
    panelDeviceTree = lib.mkOption { type = lib.types.package; };
    hdmiDeviceTree = lib.mkOption { type = lib.types.package; };
  };
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ command ];
    systemd.services.shell-ui.environment.K230_DISPLAY_SWITCH = "${command}/bin/k230-display-switch";
    security.sudo.extraRules = [{
      users = [ "shell" ];
      commands = [{ command = "${command}/bin/k230-display-switch hdmi"; options = [ "NOPASSWD" ]; }];
    }];
    systemd.services.k230-display-restore = {
      description = "Restore the panel selection after a one-shot HDMI boot";
      wantedBy = [ "multi-user.target" ];
      after = [ "local-fs.target" ];
      before = [ "shell.service" ];
      unitConfig.RequiresMountsFor = "/boot";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${command}/bin/k230-display-switch restore";
        RemainAfterExit = true;
      };
    };
    # The relay itself selects direct touch when the panel is connected.
    # A single installed system can therefore serve either boot tree.
    k230.touchTrackpad.enable = true;
  };
}
