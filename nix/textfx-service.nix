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
  # The player links the same no_std engine as stage 1 (design D4); `child` spawns the std ttfx
  # instead and is the test oracle, not the default.
  hosted = pkgs.callPackage ./ttfx-boot/hosted.nix { };
  player = pkgs.callPackage ./textfx { ttfxBootHosted = if cfg.engine == "lib" then hosted else null; };
  ttfx = pkgs.callPackage ./ttfx.nix { };
  banner = ./exhibition/K230.txt;
  # Continuation inputs, written by whatever reads the stage 1 record
  # (task 5.2): "skip=<frame> hash=<0x cell-grid hash>".  Absent = frame 0.
  orientationArg =
    if cfg.orientation != "auto" then cfg.orientation
    else if (config.k230.shell.panelTransform or "normal") != "normal" then "landscape"
    else null;
  start = pkgs.writeShellScript "k230-textfx-start" ''
    args=
    if [ -r /run/k230-textfx/continue ]; then
      . /run/k230-textfx/continue
      args="--skip $skip --expect-hash $hash"
    fi
    exec ${lib.getExe player} \
      --engine ${cfg.engine} ${lib.optionalString (cfg.engine == "child") "--ttfx ${ttfx}/bin/ttfx"} --banner ${cfg.banner} \
      --effect ${cfg.effect} --seed ${toString cfg.seed} --fps ${toString cfg.fps} \
      ${lib.optionalString (orientationArg != null) "--orientation ${orientationArg}"} \
      ${lib.optionalString (cfg.cols != null) "--cols ${toString cfg.cols}"} ${lib.optionalString (cfg.rows != null) "--rows ${toString cfg.rows}"} --scale ${toString cfg.scale} \
      --drm --ready-file /run/k230-textfx/state --idle \
      --stats-file /run/k230-textfx/stats $args \
      ${lib.optionalString (cfg.extraArgs != [ ]) "-- ${lib.escapeShellArgs cfg.extraArgs}"}
  '';
in
{
  options.k230.bootTextEffects = {
    enable = lib.mkEnableOption "the live ttfx boot text effect (unit defined, started by hand)";
    engine = lib.mkOption { type = lib.types.enum [ "lib" "child" ]; default = "lib"; description = "lib: the linked no_std engine; child: spawn the std ttfx (test oracle)."; };
    effect = lib.mkOption { type = lib.types.str; default = "wipe"; description = "ttfx effect name."; };
    seed = lib.mkOption { type = lib.types.ints.unsigned; default = 3; description = "ttfx seed; must match the stage 1 sequence."; };
    fps = lib.mkOption { type = lib.types.ints.positive; default = 30; };
    cols = lib.mkOption { type = lib.types.nullOr lib.types.ints.positive; default = null; description = "Canvas columns; null takes the orientation's grid (35 portrait, 77 landscape)."; };
    rows = lib.mkOption { type = lib.types.nullOr lib.types.ints.positive; default = null; description = "Canvas rows; null takes the orientation's grid (38 portrait, 17 landscape)."; };
    orientation = lib.mkOption {
      type = lib.types.enum [ "auto" "portrait" "landscape" ];
      default = "auto";
      description = ''
        The rule of design D15: portrait with no keyboard base, the shell's landscape with it. auto:
        a shell configured with a rotated panel (panelTransform 270) wins, because that is what the
        next frame will be; otherwise the stage 1 record's orientation, then portrait.
      '';
    };
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
