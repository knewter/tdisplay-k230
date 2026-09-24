# The shell stack: sway rendering on the CPU, a terminal, an on-screen
# keyboard, and seatd to hand the compositor the DRM device and the touch
# panel. See openspec/specs/runtime/shell and docs/display-environment-options.md
# for why these and not others.
#
# Off by default. The closure system/nixos-config requires is the one without
# this; switching it on is a recorded decision (docs/evidence/shell-build.txt
# measures what it costs), made in flake.nix for the board configuration.
#
# Layer: Nix and userspace only. Nothing here touches the kernel or the
# device tree; if the shell turns out to need either, that belongs to
# display/panel or display/touch and gets fixed there.
{ config, lib, pkgs, bootSplashImage, ... }:

let
  cfg = config.k230.shell;

  # Xwayland off: 55 fewer riscv64 derivations and no GTK 3 / CUPS / Avahi
  # tail, at the cost that no X11 application can ever run on this board.
  # Deliberate; see the runtime/shell build-cost requirement.
  swayBase = pkgs.sway.override { enableXWayland = false; };
  cardShell = pkgs.callPackage ./card-shell.nix { swayUnwrapped = pkgs.sway-unwrapped; };
  # Built only when frameTiming is selected. The patch measures monotonic
  # wall-clock elapsed time across wlroots scene building/Pixman submission
  # and KMS commit submission; it neither waits for nor claims panel scanout.
  swayFrameTimingUnwrapped = (pkgs.sway-unwrapped.override {
    enableXWayland = false;
  }).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/sway-k230-cpu-frame-timing.patch ];
  });
  # pkgs.sway is a wrapper around sway-unwrapped. Supplying the patched
  # unwrapped package here preserves the wrapper's DBus/session behavior while
  # applying the C-source patch to the derivation Meson actually compiles.
  swayFrameTiming = pkgs.sway.override {
    enableXWayland = false;
    sway-unwrapped = swayFrameTimingUnwrapped;
  };
  # The initial-logo variant is an opt-in handoff experiment. It reads the
  # same immutable B,G,R,X asset used by the boot owner before Sway's first
  # forced output commit; the ordinary package remains byte-for-byte the
  # unpatched swayBase selection.
  swayInitialSplashUnwrapped = (pkgs.sway-unwrapped.override {
    enableXWayland = false;
  }).overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./patches/sway-k230-initial-splash.patch ];
  });
  swayInitialSplash = pkgs.sway.override {
    enableXWayland = false;
    sway-unwrapped = swayInitialSplashUnwrapped;
  };
  sway = if cfg.coherentShell then cardShell
    else if cfg.vgliteAccessTrial then swayVgliteMainPid
    else if cfg.initialSplash then swayInitialSplash
    else if cfg.frameTiming then swayFrameTiming
    else swayBase;
  wlroots = pkgs.wlroots_0_20.override { enableXWayland = false; };
  # Opt-in diagnostic compositor only. The normal shell keeps the pinned
  # Pixman wlroots package above; only vgliteAccessTrial selects this package
  # in the system service. It is also exposed separately by the flake.
  vgliteProbe = pkgs.callPackage ./vglite-probe.nix { };
  wlrootsVglite = pkgs.callPackage ./wlroots-vglite.nix {
    wlroots_0_20 = wlroots;
    inherit vgliteProbe;
  };
  swayVgliteUnwrapped = (pkgs.sway-unwrapped.override { enableXWayland = false; }).overrideAttrs (old: {
    buildInputs = map (dep:
      if (dep.pname or "") == "wlroots" then wlrootsVglite else dep
    ) old.buildInputs;
  });
  swayVglite = pkgs.sway.override {
    enableXWayland = false;
    sway-unwrapped = swayVgliteUnwrapped;
  };

  # The ordinary wrapper may make dbus-run-session the systemd MainPID.
  # Start its bus first, then exec the exact unwrapped Sway so the
  # broker can authenticate the actual compositor PID, never any descendant.
  swayVgliteMainPid = pkgs.writeShellScriptBin "sway" ''
    set -eu
    if [ -z "''${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
      if [ -S "$XDG_RUNTIME_DIR/bus" ]; then
        export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
      else
        bus_address="$(${lib.getExe' pkgs.dbus "dbus-daemon"} --session --fork --print-address=1)"
        export DBUS_SESSION_BUS_ADDRESS="$bus_address"
      fi
    fi
    export XDG_CURRENT_DESKTOP=sway
    exec ${swayVgliteUnwrapped}/bin/sway "$@"
  '';

  # cage is the first-light probe (tasks 3.1/3.2), not the shell: it has no
  # layer-shell and so can never host the keyboard. Two variants, because
  # docs/evidence/drm-info.txt predicts the unpatched one cannot commit a
  # frame here (wlroots defaults to XRGB8888 and this plane has none), and
  # both the failure and the fix are worth observing rather than inferring.
  cage = pkgs.cage.override { wlroots_0_20 = wlroots; };
  cage-rgb565 = cage.overrideAttrs (old: {
    pname = "cage-rgb565";
    patches = (old.patches or [ ]) ++ [ ./patches/cage-render-rgb565.patch ];
    # Both variants sit in the system path; give this one its own name and
    # drop its man page so nothing collides with the unpatched cage.
    postInstall = (old.postInstall or "") + ''
      mv $out/bin/cage $out/bin/cage-rgb565
      rm -rf $out/share/man
    '';
  });

  wlfps = pkgs.callPackage ./wlfps { wlroots_0_20 = wlroots; };
  videoProbe = pkgs.callPackage ./video-probe.nix { };

  # swaybar delivers a touch tap to a status block's click handler
  # (swaybar/input.c wl_touch_up -> process_hotspots ->
  # block_hotspot_callback), but not to a `bindsym` mouse binding.  This
  # little, deliberately boring, state machine is therefore the board's
  # touch launcher. Home and Apps each expose four 128 px controls; their
  # restrained colours make the launcher page recognisable at a glance. Both
  # rows fit inside 568 px and are 56 px high. It needs no gesture daemon,
  # physical buttons, or touch-hostile launcher.
  terminalFootConfig = pkgs.writeText "k230-terminal-foot.ini" ''
    font=DejaVu Sans Mono:size=15
    app-id=k230-terminal
    login-shell=yes
  '';
  monitorHtopConfig = pkgs.writeText "k230-monitor.htoprc" (builtins.readFile ./k230-monitor.htoprc);
  monitorFootConfig = pkgs.writeText "k230-monitor-foot.ini" ''
    font=DejaVu Sans Mono:size=15
    title=Monitor
    locked-title=yes
    app-id=k230-monitor
  '';
  # Nano is already in the baseline closure; expose it through the same
  # desktop-entry bridge as other terminal apps. nnn supplies its own entry.
  editorDesktop = pkgs.makeDesktopItem {
    name = "k230-editor";
    desktopName = "Editor";
    icon = "accessories-text-editor";
    comment = "Edit a text file with nano";
    exec = "${pkgs.nano}/bin/nano";
    terminal = true;
    categories = [ "Utility" "TextEditor" ];
  };
  # The desktop item starts the bounded session wrapper. Software 270p is the
  # default; `k230-video-session run-mvx` opts into the measured MVX profile.
  # A protected /run/shell/k230-video.playlist, when present, is passed by
  # pathname so private URLs never appear in the player command line.
  videoSession = pkgs.writeShellScriptBin "k230-video-session" ''
    export PATH=${pkgs.coreutils}/bin:${pkgs.util-linux}/bin:${pkgs.procps}/bin:${pkgs.python3}/bin:$PATH
    export K230_VIDEO_PLAYER=${videoProbe.player}/bin/mpv
    export K230_VIDEO_FLOCK=${pkgs.util-linux}/bin/flock
    export K230_VIDEO_RUNTIME_DIR=/run/shell
    export K230_VIDEO_PID_FILE=/run/shell/k230-video.pid
    export K230_VIDEO_LOG=/run/shell/k230-video.log
    export K230_VIDEO_PUBLIC_URL=https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd
    exec ${pkgs.python3}/bin/python3 ${./video-session.py} "$@"
  '';
  videoDesktop = pkgs.makeDesktopItem {
    name = "k230-video";
    desktopName = "Video";
    icon = "mpv";
    comment = "Play the public network video demo";
    exec = "${videoSession}/bin/k230-video-session run";
    terminal = true;
    categories = [ "AudioVideo" "Video" ];
  };
  touchLauncherBase = pkgs.callPackage ./touch-launcher { wlroots_0_20 = wlroots; };
  rustShellBase = pkgs.callPackage ./rust-shell-client { };
  themeTools = pkgs.callPackage ./omarchy-theme-tools { };
  themeDefault = pkgs.callPackage ./handheld-theme-default { };
  themeDefaultId = (builtins.fromJSON (builtins.readFile ./handheld-theme-default/default-report.json)).generation;
  themeCommand = pkgs.callPackage ./handheld-theme-command.nix {
    omarchyThemeTools = themeTools;
    inherit themeDefault;
  };
  settingsCommand = pkgs.callPackage ./handheld-settings.nix { };
  notificationCommand = pkgs.callPackage ./handheld-notifications.nix { };
  notificationSources = pkgs.writeText "k230-notification-sources.json" (builtins.toJSON {
    "${rustShellBase}/bin/k230-shell-rust" = {
      id = "shell"; name = "Shell"; icon = "applications-system";
    };
  });
  themedFoot = pkgs.writeShellScriptBin "k230-foot" ''
    set -eu
    case "''${1:-}" in
      terminal|monitor) role="$1"; shift ;;
      *) echo "k230-foot: expected terminal or monitor" >&2; exit 2 ;;
    esac
    ${if cfg.coherentShell then ''
      # Read only the adapter's acknowledged generation. Failed preparation
      # keeps terminal recovery available with the packaged fresh-home palette.
      appearance_root="${config.users.users.shell.home}/.local/state/omarchy/current"
      foot_config="${themeDefault}/generations/${themeDefaultId}/$role-foot.ini"
      if generation="$(${themeCommand}/bin/k230-app-appearance sync --state-root "$appearance_root" 2>/dev/null)"; then
        case "$generation" in
          "$appearance_root"/app-appearance/generations/*)
            if [ -f "$generation/$role-foot.ini" ]; then
              foot_config="$generation/$role-foot.ini"
            fi
            ;;
        esac
      fi
    '' else ''
      case "$role" in
        terminal) foot_config=${terminalFootConfig} ;;
        monitor) foot_config=${monitorFootConfig} ;;
      esac
    ''}
    export HTOPRC="''${HTOPRC:-${monitorHtopConfig}}"
    exec ${pkgs.foot}/bin/foot --config "$foot_config" "$@"
  '';
  touchLauncherAction = pkgs.writeShellScriptBin "k230-launcher-action" ''
    case "$1" in
      terminal|monitor)
        if ${sway}/bin/swaymsg -t get_tree -r | ${pkgs.jq}/bin/jq -e --arg app_id "k230-$1" \
            'recurse(.nodes[]?, .floating_nodes[]?) | select(.app_id? == $app_id) | .id' >/dev/null 2>&1; then
          ${sway}/bin/swaymsg "[app_id=\"k230-$1\"] focus"
        elif [ "$1" = monitor ]; then
          ${themedFoot}/bin/k230-foot monitor -e ${pkgs.htop}/bin/htop &
        else
          ${themedFoot}/bin/k230-foot terminal &
        fi
        ;;
      new-terminal) ${themedFoot}/bin/k230-foot terminal & ;;
      *) echo "k230-launcher-action: unknown action" >&2; exit 2 ;;
    esac
  '';
  xdgTerminalExec = pkgs.writeShellScriptBin "xdg-terminal-exec" ''
    exec ${themedFoot}/bin/k230-foot terminal -e "$@"
  '';
  launcherFoot = pkgs.writeShellScriptBin "foot" ''
    exec ${themedFoot}/bin/k230-foot terminal "$@"
  '';
  windowCatalog = pkgs.writeShellScriptBin "k230-window-catalog" ''
    export K230_SWAYMSG=${sway}/bin/swaymsg
    export K230_JQ=${pkgs.jq}/bin/jq
    exec ${pkgs.bash}/bin/bash ${./window-catalog.sh}
  '';
  launcherEnvironment = ''
    export K230_LAUNCHER_ACTION=${touchLauncherAction}/bin/k230-launcher-action
    export K230_WINDOW_CATALOG=${windowCatalog}/bin/k230-window-catalog
    export K230_SWAYMSG=${sway}/bin/swaymsg
    # Include Nix profiles because the systemd session does not run a login shell.
    export HTOPRC="''${HTOPRC:-${monitorHtopConfig}}"
    export PATH=${xdgTerminalExec}/bin:${launcherFoot}/bin:$HOME/.nix-profile/bin:/nix/profile/bin:$HOME/.local/state/nix/profile/bin:/etc/profiles/per-user/shell/bin:/nix/var/nix/profiles/default/bin:/run/current-system/sw/bin:$PATH
    # Nix package icon trees are not necessarily merged into a profile's
    # share/icons tree. Keep their desktop art reachable by themed name.
    export XDG_DATA_DIRS="${pkgs.foot}/share:${pkgs.htop}/share:${videoProbe.player}/share:''${XDG_DATA_DIRS:-$HOME/.nix-profile/share:/nix/profile/share:$HOME/.local/state/nix/profile/share:/etc/profiles/per-user/shell/share:/nix/var/nix/profiles/default/share:/run/current-system/sw/share}"
    export XDG_CURRENT_DESKTOP="''${XDG_CURRENT_DESKTOP:-sway}"
  '';
  touchLauncher = pkgs.writeShellScriptBin "k230-touch-launcher" ''
    ${launcherEnvironment}
    ${lib.optionalString cfg.themeReceiverTrial "export K230_LAUNCHER_THEME_RECEIVER=1"}
    ${lib.optionalString cfg.themeReceiverTrial ''export K230_THEME_STATE_ROOT="${config.users.users.shell.home}/.local/state/omarchy/current"''}
    ${lib.optionalString cfg.themeReceiverTrial ''export K230_THEME_DEFAULT_GENERATION="${themeDefault}/generations/${themeDefaultId}"''}
    exec ${touchLauncherBase}/bin/k230-touch-launcher "$@"
  '';
  rustShell = pkgs.writeShellScriptBin "k230-shell-rust" ''
    ${launcherEnvironment}
    # The supervised UI starts after Sway's process, before its display may
    # exist. Discover one actual session socket instead of assuming wayland-0.
    if [ -z "''${WAYLAND_DISPLAY:-}" ]; then
      for attempt in $(${pkgs.coreutils}/bin/seq 1 100); do
        found=""
        for candidate in "$XDG_RUNTIME_DIR"/wayland-*; do
          if [ -S "$candidate" ]; then
            if [ -n "$found" ]; then
              echo "k230-shell-rust: ambiguous Wayland display" >&2
              exit 1
            fi
            found="$candidate"
          fi
        done
        if [ -n "$found" ]; then
          export WAYLAND_DISPLAY="''${found##*/}"
          break
        fi
        ${pkgs.coreutils}/bin/sleep 0.1
      done
      if [ -z "''${WAYLAND_DISPLAY:-}" ]; then
        echo "k230-shell-rust: session Wayland display unavailable" >&2
        exit 1
      fi
    fi
    export K230_SETTINGS=${settingsCommand}/bin/k230-settings
    export K230_THEME_COMMAND=${themeCommand}/bin/k230-theme
    export K230_SETTINGS_REDUCED_MOTION=${if cfg.reducedMotion then "1" else "0"}
    export K230_NOTIFICATION_SOCKET=/run/shell-notifications/events.sock
    export K230_THEME_STATE_ROOT="${config.users.users.shell.home}/.local/state/omarchy/current"
    export K230_THEME_DEFAULT_GENERATION="${themeDefault}/generations/${themeDefaultId}"
    exec ${rustShellBase}/bin/k230-shell-rust "$@"
  '';
  touchMenu = pkgs.writeShellScriptBin "k230-touch-menu" ''
    export K230_SWAYMSG=${sway}/bin/swaymsg
    export K230_FOOT=${pkgs.foot}/bin/foot
    export K230_HTOP=${pkgs.htop}/bin/htop
    export K230_HTOPRC=${monitorHtopConfig}
    export K230_JQ=${pkgs.jq}/bin/jq
    export K230_SED=${pkgs.gnused}/bin/sed
    export K230_PKILL=${pkgs.procps}/bin/pkill
    # NixOS makes sudo setuid only in this wrapper directory. A store path is
    # deliberately non-setuid and cannot perform the confirmed system action.
    export K230_SUDO=/run/wrappers/bin/sudo
    export K230_SYSTEMCTL=${pkgs.systemd}/bin/systemctl
    export K230_TERMINAL_CONFIG=${terminalFootConfig}
    export K230_MONITOR_CONFIG=${monitorFootConfig}
    export K230_LAUNCHER=${touchLauncher}/bin/k230-touch-launcher
    export K230_VIDEO_SESSION=${videoSession}/bin/k230-video-session
    exec ${pkgs.bash}/bin/bash ${./touch-menu.sh}
  '';

  # 568x1232 portrait, transform normal, scale 1: the panel's native mode
  # and the touch controller's native orientation, so no per-pixel rotation
  # on the CPU and no coordinate transform between finger and pixel.
  #
  # render_bit_depth 6 is the one line that makes wlroots work on this
  # device: it selects DRM_FORMAT_RGB565 (sway/config/output.c), which the
  # canaan-drm primary plane advertises, where wlroots' default XRGB8888 is
  # absent and fails at output_pick_format. docs/evidence/drm-info.txt.
  #
  # map_to_output is written explicitly rather than trusting sway's
  # built-in heuristic (sway/input/seat.c get_builtin_output_name), so the
  # mapping does not depend on the output being named DSI-* or on the touch
  # device's udev ID_PATH. Whether the heuristic would have fired is
  # recorded in docs/evidence/shell-session.txt.
  swayConfig = pkgs.writeText "k230-sway.conf" ''
    output DSI-1 mode 568x1232 transform normal scale 1 render_bit_depth 6
    input type:touch map_to_output DSI-1

    ${lib.optionalString cfg.coherentShell ''
      # Sway classifies transients as floating before for_window matching.
      # Maximize ordinary tiling apps, preserving dialog geometry and the
      # more specific video rules below. Home is the live deck, not a tab strip.
      floating_maximum_size -1 x -1
      default_floating_border none
      for_window [tiling app_id=".*"] floating enable, resize set 100 ppt 100 ppt, move position 0 0
    ''}

    # mpv's wlshm surface is explicitly floating so its profile geometry is
    # honored by Sway on the portrait panel and remains touchable.
    for_window [app_id="k230-video-software"] floating enable, resize set 480 px 270 px, move position center
    for_window [app_id="k230-video-mvx"] floating enable, resize set 568 px 320 px, move position center

    default_border none
    font pango:DejaVu Sans Mono 15
    focus_follows_mouse no
    # A 568 px panel cannot make two tiled terminals useful. New applications
    # share a tabbed workspace; the touch menu can still focus any container.
    workspace_layout ${if cfg.coherentShell then "default" else "tabbed"}

    ${lib.optionalString (!cfg.coherentShell) ''
    bar {
      position top
      height 56
      font pango:DejaVu Sans Mono 16
      # swaybar starts status_command with the Wayland display inherited from
      # sway, so foot launched by the menu joins this session rather than a
      # system service environment with no WAYLAND_DISPLAY.
      status_command ${touchMenu}/bin/k230-touch-menu
      workspace_buttons no
      colors {
        statusline #ffffff
        background #202020
      }
    }
    ''}

    # ${toString cfg.keyboardHeight} px: with ten keys across 568 px each key is
    # ~57 px (4.4 mm) wide; rows of ~80 px are what a fingertip needs.
    exec ${pkgs.wvkbd}/bin/wvkbd-mobintl -H ${toString cfg.keyboardHeight} --hidden
    exec ${themedFoot}/bin/k230-foot terminal
  '';
in
{
  options.k230.shell = {
    enable = lib.mkEnableOption "the sway shell on the panel";

    probes = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Also install the bring-up probes: cage (unpatched and an RGB565
        variant), drm_info, libinput's debug tool, wayland-info and wlfps.
        They exist to verify runtime/shell on the board and should leave with
        the change that needed them.
      '';
    };

    debugLog = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Run sway with -d so the journal carries wlroots' WLR_DEBUG output,
        including which renderer and allocator it selected.
      '';
    };

    themeReceiverTrial = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Opt into the legacy C launcher-only appearance receiver and install
        the pinned theme command. The coherent Rust client needs its own
        appearance receiver. This does not enable a system-wide theme or claim
        physical touch, contrast, rollback or reboot proof.
      '';
    };

    coherentShell = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Select the opt-in Rust drawer/shade and live-card session with Settings
        and notification services. The ordinary bar session remains a separate
        rollback configuration until touch acceptance is recorded.
      '';
    };

    reducedMotion = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Shorten shell settling while preserving direct touch and destinations.";
    };

    vgliteAccessTrial = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Unsupported opt-in VG-Lite service trial with a root descriptor broker.
        Requires root-private /dev/vg_lite, active Yama startup protection and
        unverified GPU/cache gates. Normal Pixman remains the default.
      '';
    };

    frameTiming = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Use the diagnostic sway build and set SWAY_K230_CPU_FRAME_TIMING=1.
        It logs CLOCK_MONOTONIC wall-clock elapsed time (including scheduling)
        from immediately before
        wlr_scene_output_build_state through wlr_output_commit_state returning.
        This includes CPU scene/Pixman work and commit submission, not vblank
        or physical panel scanout.
      '';
    };

    initialSplash = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Use the experimental Sway scene seed for the immutable 568x1232 XRGB
        boot logo. It is created before the first forced output commit and is
        removed only after a non-null toplevel plus Swaybar's mapped bottom
        panel scene state
        commits and wlroots reports the matching compositor present event. This
        does not claim physical no-black-frame
        continuity until hardware evidence exists.
      '';
    };

    keyboardHeight = lib.mkOption {
      type = lib.types.int;
      default = 400;
      description = "Height of the on-screen keyboard in pixels.";
    };

    compositor = lib.mkOption {
      type = lib.types.package;
      default = sway;
      readOnly = true;
      description = "The compositor package, exposed so it can be built alone.";
    };

    vgliteCompositor = lib.mkOption {
      type = lib.types.package;
      default = swayVglite;
      readOnly = true;
      description = "Opt-in Sway package using the guarded VG-Lite wlroots renderer.";
    };


    vgliteServiceCompositor = lib.mkOption {
      type = lib.types.package;
      default = swayVgliteMainPid;
      readOnly = true;
      description = "Opt-in compositor wrapper that preserves the systemd MainPID.";
    };

    launcher = lib.mkOption {
      type = lib.types.package;
      default = touchLauncher;
      readOnly = true;
      description = "Native portrait Apps launcher, exposed for a narrow build.";
    };

    rustFrontend = lib.mkOption {
      type = lib.types.package;
      default = rustShell;
      readOnly = true;
      description = "Supervised Rust frontend wrapper, exposed for a narrow build.";
    };

    themedTerminal = lib.mkOption {
      type = lib.types.package;
      default = themedFoot;
      readOnly = true;
      description = "Terminal launcher using the acknowledged app appearance.";
    };

    frameTimingCompositor = lib.mkOption {
      type = lib.types.package;
      default = swayFrameTiming;
      readOnly = true;
      description = "Sway with opt-in K230 CPU frame timing instrumentation.";
    };

    initialSplashCompositor = lib.mkOption {
      type = lib.types.package;
      default = swayInitialSplash;
      readOnly = true;
      description = "Sway with the opt-in immutable K230 initial-logo scene.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !cfg.coherentShell || !(cfg.initialSplash || cfg.frameTiming || cfg.vgliteAccessTrial);
        message = "The coherent shell uses its card compositor; run renderer/splash diagnostics in their separate configurations.";
      }
      {
        assertion = !(cfg.initialSplash && cfg.frameTiming);
        message = "k230.shell.initialSplash and frameTiming patch the same Sway commit path; enable one diagnostic at a time.";
      }
    ];
    # seatd owns the seat: it opens /dev/dri/card0 and /dev/input/* on the
    # compositor's behalf and puts the active VT into KD_GRAPHICS, which is
    # what stops fbcon drawing over the compositor. The shell user only needs
    # to be in the `seat` group.
    #
    # Not services.seatd: that module wraps seatd in s6-notify-socket-from-fd,
    # and s6's dependency execline refuses to cross-compile at this pin (its
    # configure needs pkg-config and the derivation does not provide one --
    # docs/evidence/shell-build.txt, task 2.4). A plain unit needs neither;
    # the compositor's unit waits for the socket instead of a notification.
    users.groups.seat = { };
    systemd.services.seatd = {
      description = "Seat management daemon";
      documentation = [ "man:seatd(1)" ];
      wantedBy = [ "multi-user.target" ];
      restartIfChanged = false;
      serviceConfig = {
        Type = "simple";
        ExecStart = "${lib.getExe' pkgs.seatd "seatd"} -g seat -l info";
        Restart = "always";
        RestartSec = 1;
      };
    };

    # Fresh homes get the same portrait defaults as menu-launched applications.
    # User configuration may still override these normal system-wide defaults.
    environment.etc."htoprc".source = monitorHtopConfig;
    environment.etc."xdg/foot/foot.ini".source = if cfg.coherentShell
      then "${themeDefault}/generations/${themeDefaultId}/terminal-foot.ini"
      else terminalFootConfig;
    environment.etc."neofetch/config.conf".source = ./neofetch.conf;

    users.groups.shell = { };
    users.users.shell = {
      isNormalUser = true;
      uid = 1000;
      group = "shell";
      extraGroups = [ "seat" "video" "input" ];
      description = "owns the panel";
    };

    # The touch menu can ask PID 1 only for these two explicit state changes.
    # A second menu page requires an affirmative tap and offers Cancel before
    # either command is run. No general root shell or passwordless command is
    # granted to the session user.
    security.sudo.extraRules = [
      {
        users = [ "shell" ];
        commands = [
          { command = "${pkgs.systemd}/bin/systemctl reboot"; options = [ "NOPASSWD" ]; }
          { command = "${pkgs.systemd}/bin/systemctl poweroff"; options = [ "NOPASSWD" ]; }
        ];
      }
    ];

    # No login prompt on the panel. The serial getty (serial-getty@ttyS0)
    # is untouched and stays the console. The VT getty is what
    # services.getty.autologinUser was landing on; masking it here means
    # tty1 never shows a prompt and never competes for the screen.
    systemd.services."getty@tty1".enable = false;
    systemd.services."autovt@tty1".enable = false;

    systemd.sockets.k230-vglite-broker = lib.mkIf cfg.vgliteAccessTrial {
      description = "Private compositor VG-Lite descriptor endpoint";
      socketConfig = {
        ListenStream = "/run/k230-vglite-broker.sock";
        SocketUser = "root";
        SocketGroup = "shell";
        SocketMode = "0660";
        RemoveOnStop = true;
      };
    };
    systemd.services.k230-vglite-broker = lib.mkIf cfg.vgliteAccessTrial {
      description = "VG-Lite descriptor grant to the exact shell compositor MainPID";
      requires = [ "k230-vglite-broker.socket" ];
      path = [ pkgs.systemd ];
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${./vglite-access/broker.py} --unit shell.service --executable ${swayVgliteUnwrapped}/bin/sway --user shell";
        User = "root";
        Group = "root";
        NoNewPrivileges = true;
        CapabilityBoundingSet = [ "CAP_SYS_PTRACE" ];
        DevicePolicy = "closed";
        DeviceAllow = [ "/dev/vg_lite rw" ];
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictNamespaces = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        SystemCallFilter = [ "~@debug" ];
        UMask = "0077";
      };
    };

    # Sway and the separately supervised Rust client share one session bus;
    # a bus created inside only Sway's wrapper cannot reach UI-launched apps.
    systemd.services.shell-session-bus = lib.mkIf cfg.coherentShell {
      description = "Handheld application session bus";
      serviceConfig = {
        User = "shell";
        Group = "shell";
        RuntimeDirectory = "shell-bus";
        RuntimeDirectoryMode = "0700";
        Type = "exec";
        ExecStart = "${pkgs.dbus}/bin/dbus-daemon --session --nofork --address=unix:path=/run/shell-bus/bus";
        ExecStartPost = pkgs.writeShellScript "wait-for-shell-bus" ''
          for attempt in $(${pkgs.coreutils}/bin/seq 1 100); do
            [ -S /run/shell-bus/bus ] && exit 0
            ${pkgs.coreutils}/bin/sleep 0.1
          done
          echo "handheld session bus did not become ready" >&2
          exit 1
        '';
        Restart = "on-failure";
        UMask = "0077";
      };
    };

    systemd.services.shell-notifications = lib.mkIf cfg.coherentShell {
      description = "Handheld notification history";
      wantedBy = [ "multi-user.target" ];
      environment.SWAYSOCK = "/run/shell/sway-ipc.sock";
      serviceConfig = {
        User = "shell";
        Group = "shell";
        RuntimeDirectory = "shell-notifications";
        RuntimeDirectoryMode = "0700";
        ExecStart = "${notificationCommand}/bin/k230-notifications serve --trusted ${notificationSources}";
        Restart = "on-failure";
        RestartSec = 1;
        UMask = "0077";
        NoNewPrivileges = true;
      };
    };

    systemd.services.shell-ui = lib.mkIf cfg.coherentShell {
      description = "Rust handheld drawer and system surfaces";
      wantedBy = [ "shell.service" ];
      bindsTo = [ "shell.service" ];
      partOf = [ "shell.service" ];
      requires = [ "shell-session-bus.service" ];
      wants = [ "shell-notifications.service" ];
      after = [ "shell.service" "shell-notifications.service" "shell-session-bus.service" ];
      environment = {
        XDG_RUNTIME_DIR = "/run/shell";
        SWAYSOCK = "/run/shell/sway-ipc.sock";
        DBUS_SESSION_BUS_ADDRESS = "unix:path=/run/shell-bus/bus";
      };
      path = [ pkgs.coreutils ];
      serviceConfig = {
        Type = "exec";
        User = "shell";
        Group = "shell";
        WorkingDirectory = config.users.users.shell.home;
        ExecStart = "${rustShell}/bin/k230-shell-rust --serve";
        Restart = "on-failure";
        RestartSec = 1;
        UMask = "0077";
      };
    };

    systemd.services.shell = {
      description = "sway on the panel";
      wantedBy = [ "multi-user.target" ];
      requires = [ "seatd.service" ] ++ lib.optional cfg.vgliteAccessTrial "k230-vglite-broker.socket"
        ++ lib.optional cfg.coherentShell "shell-session-bus.service";
      wants = lib.optional (!config.k230.panelConsole) "k230-drm-splash.service";
      after = [ "seatd.service" "systemd-udev-settle.service" ]
        ++ lib.optional cfg.coherentShell "shell-session-bus.service"
        ++ lib.optional cfg.vgliteAccessTrial "k230-vglite-broker.socket"
        ++ lib.optional (!config.k230.panelConsole) "k230-drm-splash.service";

      environment = {
        XDG_RUNTIME_DIR = "/run/shell";
        XDG_SEAT = "seat0";
        LIBSEAT_BACKEND = "seatd";
        # wlroots would choose Pixman on its own on a card with no render
        # node (render/wlr_renderer.c:268); naming it makes the choice a
        # stated intention that fails loudly if the device ever changes.
        WLR_RENDERER = if cfg.vgliteAccessTrial then "vglite" else "pixman";
        # A fixed IPC socket so `swaymsg` from the serial console needs no
        # discovery (sway/ipc-server.c honours SWAYSOCK when it is set).
        SWAYSOCK = "/run/shell/sway-ipc.sock";
      } // lib.optionalAttrs cfg.vgliteAccessTrial {
        K230_VGLITE_BROKER = "/run/k230-vglite-broker.sock";
        K230_VGLITE_ALLOW_UNPROVEN_CACHE = "1";
      } // lib.optionalAttrs cfg.frameTiming {
        SWAY_K230_CPU_FRAME_TIMING = "1";
      } // lib.optionalAttrs cfg.coherentShell {
        DBUS_SESSION_BUS_ADDRESS = "unix:path=/run/shell-bus/bus";
        SWAY_K230_CARD_SHELL = "1";
        SWAY_K230_CARD_TOUCH_FIRST = "1";
        SWAY_K230_CARD_DRAWER_HELPER = "${rustShell}/bin/k230-shell-rust";
        SWAY_K230_CARD_SURFACE_HELPER = "${rustShell}/bin/k230-shell-rust";
        SWAY_K230_CARD_SURFACE_SOCKET = "/run/shell/k230-shell-rust.sock";
        SWAY_K230_CARD_REDUCED_MOTION = if cfg.reducedMotion then "1" else "0";
        K230_SETTINGS_REDUCED_MOTION = if cfg.reducedMotion then "1" else "0";
        SWAY_K230_CARD_SCALED_CACHE = "0";
      } // lib.optionalAttrs cfg.initialSplash {
        # The derivation validates the fixed raw B,G,R,X asset before adding
        # it above layer-shell backgrounds. It is absent from the daily service.
        SWAY_K230_INITIAL_SPLASH = "${bootSplashImage}/logo.xrgb";
        SWAY_K230_INITIAL_SPLASH_OUTPUT = "DSI-1";
      };
      # systemd services do not inherit the login PATH.  Sway starts
      # dbus-daemon, swaybar and `exec` commands by bare name, so retain the
      # session's actual executables here rather than relying on
      # /run/current-system/sw/bin being present by accident.
      path = [ pkgs.dbus pkgs.bash sway pkgs.foot pkgs.wvkbd pkgs.procps pkgs.coreutils pkgs.htop pkgs.jq pkgs.gnused ];

      serviceConfig = {
        User = "shell";
        Group = "shell";
        # Sway inherits this into foot and every menu-launched client.  `/`
        # is readable but not a useful first terminal directory; the shell
        # account's home is writable and becomes the predictable session cwd.
        WorkingDirectory = config.users.users.shell.home;
        RuntimeDirectory = "shell";
        RuntimeDirectoryMode = "0700";
        # On a splash boot, an active owner writes `scanout` only after its
        # KMS set. Tell it to drop DRM master while retaining its framebuffer,
        # then wait for acknowledgement before Sway opens DRM. A completed or
        # failed optional owner cannot hold DRM master, so shell restart and
        # a splash setup failure deliberately fall through with a journal log.
        ExecStartPre = lib.optional (!config.k230.panelConsole)
          (pkgs.writeShellScript "release-k230-drm-splash" ''
            state=/run/k230-drm-splash/state
            systemctl=${pkgs.systemd}/bin/systemctl
            owner_active() {
              "$systemctl" is-active --quiet k230-drm-splash.service
            }
            state_value() {
              cat "$state" 2>/dev/null || true
            }
            for i in $(seq 100); do
              case "$(state_value)" in
                master-dropped)
                  echo "k230 DRM splash handoff was already acknowledged" >&2
                  exit 0
                  ;;
                scanout)
                  if owner_active; then
                    pkill -USR1 -x k230-drm-splash
                    for j in $(seq 100); do
                      [ "$(state_value)" = master-dropped ] && exit 0
                      if ! owner_active; then
                        echo "k230 DRM splash owner exited after handoff; proceeding" >&2
                        exit 0
                      fi
                      sleep 0.1
                    done
                    echo "active k230 DRM splash owner did not drop DRM master" >&2
                    exit 1
                  fi
                  echo "k230 DRM splash state is stale but owner is inactive; proceeding" >&2
                  exit 0
                  ;;
              esac
              if ! owner_active; then
                echo "k230 DRM splash owner is inactive; proceeding without optional splash" >&2
                exit 0
              fi
              sleep 0.1
            done
            echo "active k230 DRM splash owner never reached scanout" >&2
            exit 1
          '') ++ [
          # seatd's unit is Type=simple (see above), so "after seatd" only
          # means the process exists. Wait for its socket, up to 10 s.
          (pkgs.writeShellScript "wait-for-seatd" ''
            for i in $(seq 50); do
              [ -S /run/seatd.sock ] && exit 0
              sleep 0.2
            done
            echo "seatd socket never appeared" >&2
            exit 1
          '')
        ];
        ExecStart = "${sway}/bin/sway ${if cfg.debugLog then "-d" else "-V"} -c ${swayConfig}";
        Restart = "on-failure";
        RestartSec = 2;
      };
    };

    # foot and swaybar both go through fontconfig, and the minimal profile
    # ships no fonts at all. One family is enough.
    fonts.fontconfig.enable = true;
    fonts.packages = [ pkgs.dejavu_fonts ];

    environment.systemPackages = [
      sway
      pkgs.foot
      pkgs.foot.terminfo
      pkgs.wvkbd
      pkgs.seatd
      pkgs.htop
      pkgs.nano
      pkgs.nnn
      editorDesktop
      videoSession
      videoDesktop
      touchLauncher
    ] ++ lib.optionals cfg.themeReceiverTrial [ themeCommand ]
      ++ lib.optionals cfg.coherentShell [ rustShell themedFoot themeCommand settingsCommand notificationCommand ]
      ++ lib.optionals cfg.probes [
      cage
      cage-rgb565
      pkgs.drm_info
      pkgs.libinput
      pkgs.wayland-utils
      # A Wayland screenshot is a layout inspection aid during bring-up.  It
      # complements, rather than replaces, a photograph of the physical panel.
      pkgs.grim
      # evemu creates a uinput touchscreen and injects touches at known
      # panel coordinates (the kernel gained INPUT_UINPUT for exactly this),
      # so compositor -> keyboard -> terminal can be exercised unattended.
      # A software proxy: evidence from it is labelled "injected", and the
      # touch requirement still closes on a real tap at the bench.
      pkgs.evemu
      (pkgs.callPackage ./neofetch.nix { })
      wlfps
    ];

    # swaymsg from a root shell on the serial console reaches the session's
    # socket without
    # socket without anyone having to remember the path.
    environment.variables.SWAYSOCK = "/run/shell/sway-ipc.sock";
  };
}
