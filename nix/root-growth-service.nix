{ config, lib, pkgs, ... }:
let
  package = pkgs.callPackage ./root-growth.nix { };
in {
  options.k230.rootGrowth.enable = lib.mkEnableOption "guarded expansion of the final K230 root partition";
  config = lib.mkIf config.k230.rootGrowth.enable {
    # One guard owns both phases; independent auto-resize would bypass refusal.
    assertions = [ {
      assertion = !config.boot.growPartition && !config.fileSystems."/".autoResize;
      message = "K230 root growth must exclusively guard partition and filesystem resizing";
    } ];
    environment.systemPackages = [ package ];
    systemd.services.k230-root-growth = {
      description = "Use the K230 card's trailing root capacity after layout validation";
      wantedBy = [ "multi-user.target" ];
      after = [ "local-fs.target" ];
      before = [ "shell.service" ];
      # Wanted, never Required: failure leaves the mounted root and shell usable.
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${package}/bin/k230-root-growth --apply";
        TimeoutStartSec = "180s";
        KillMode = "control-group";
        UMask = "0077";
      };
    };
  };
}
