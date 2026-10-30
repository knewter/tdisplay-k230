# Importable NixOS module for the live boot text effect (openspec change
# the-boot-plays-terminal-text-effects).  Off by default.  With
# k230.bootTextEffects.enable the player and a systemd unit are defined, but
# the unit is NOT wanted by any target: it is started by hand
# (`systemctl start k230-textfx`) until the boot integration is reviewed
# (tasks 5.1 and 5.2: placement before the shell and the display release
# protocol shared with k230-drm-splash).  It never changes kernel, initrd,
# bootargs or stage 1.
{ config, lib, pkgs, ... }:

let
  cfg = config.k230.bootTextEffects;
  player = pkgs.callPackage ./textfx { };
  ttfx = pkgs.callPackage ./ttfx.nix { };
  banner = ./exhibition/K230.txt;
  # Continuation inputs, written by whatever reads the stage 1 record
  # (task 5.2): "skip=<frame> hash=<0x cell-grid hash>".  Absent = frame 0.
  start = pkgs.writeShellScript "k230-textfx-start" ''
    args=
    if [ -r /run/k230-textfx/continue ]; then
      . /run/k230-textfx/continue
      args="--skip $skip --expect-hash $hash"
    fi
    exec ${lib.getExe player} \
      --ttfx ${ttfx}/bin/ttfx --banner ${cfg.banner} \
      --effect ${cfg.effect} --seed ${toString cfg.seed} --fps ${toString cfg.fps} \
      --cols ${toString cfg.cols} --rows ${toString cfg.rows} --scale ${toString cfg.scale} \
      --drm --ready-file /run/k230-textfx/state --idle \
      --stats-file /run/k230-textfx/stats $args \
      ${lib.optionalString (cfg.extraArgs != [ ]) "-- ${lib.escapeShellArgs cfg.extraArgs}"}
  '';
in
{
  options.k230.bootTextEffects = {
    enable = lib.mkEnableOption "the live ttfx boot text effect (unit defined, started by hand)";
    effect = lib.mkOption { type = lib.types.str; default = "wipe"; description = "ttfx effect name."; };
    seed = lib.mkOption { type = lib.types.ints.unsigned; default = 3; description = "ttfx seed; must match the stage 1 sequence."; };
    fps = lib.mkOption { type = lib.types.ints.positive; default = 30; };
    cols = lib.mkOption { type = lib.types.ints.positive; default = 35; };
    rows = lib.mkOption { type = lib.types.ints.positive; default = 38; };
    scale = lib.mkOption { type = lib.types.ints.positive; default = 2; };
    banner = lib.mkOption { type = lib.types.path; default = banner; description = "Text the effect animates."; };
    extraArgs = lib.mkOption { type = lib.types.listOf lib.types.str; default = [ ]; description = "Extra ttfx effect arguments."; };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ player ];
    systemd.services.k230-textfx = {
      description = "Live ttfx text effect on the panel (manual start)";
      documentation = [ "https://github.com/knewter/tdisplay-k230/blob/master/openspec/changes/the-boot-plays-terminal-text-effects/design.md" ];
      # Deliberately no wantedBy and no ordering against shell.service: see header.
      serviceConfig = {
        Type = "simple";
        User = "shell";
        Group = "shell";
        RuntimeDirectory = "k230-textfx";
        RuntimeDirectoryMode = "0700";
        ExecStart = start;
        KillSignal = "SIGTERM";
        TimeoutStopSec = "5s";
        Restart = "no";
        Nice = 19;
        CPUSchedulingPolicy = "idle";
      };
    };
  };
}
