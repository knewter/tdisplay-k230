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
{ config, lib, pkgs, ... }:

let
  cfg = config.k230.shell;

  # Xwayland off: 55 fewer riscv64 derivations and no GTK 3 / CUPS / Avahi
  # tail, at the cost that no X11 application can ever run on this board.
  # Deliberate; see the runtime/shell build-cost requirement.
  sway = pkgs.sway.override { enableXWayland = false; };
  wlroots = pkgs.wlroots_0_20.override { enableXWayland = false; };

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

  # The on-screen keyboard toggle. swaybar delivers a touch tap to a status
  # block's click handler (swaybar/input.c wl_touch_up -> process_hotspots ->
  # block_hotspot_callback) but never to a `bindsym` mouse binding, which
  # only pointer buttons reach. So the summon/dismiss control is an i3bar
  # status block, and this is the status command: it prints one block and
  # then turns each click on it into SIGRTMIN, which wvkbd treats as toggle
  # (wvkbd main.c: SIGUSR1 hide, SIGUSR2 show, SIGRTMIN toggle_visibility).
  keyboardToggle = pkgs.writeShellScript "k230-keyboard-toggle" ''
    printf '{"version":1,"click_events":true}\n[\n'
    printf '[{"name":"kbd","full_text":"  [ keyboard ]  ","separator":false}],\n'
    while IFS= read -r line; do
      case "$line" in
        *'"name":"kbd"'*) ${pkgs.procps}/bin/pkill -RTMIN -x wvkbd-mobintl ;;
      esac
    done
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

    default_border none
    font pango:DejaVu Sans Mono 11
    focus_follows_mouse no

    bar {
      position top
      height 44
      font pango:DejaVu Sans Mono 13
      status_command ${keyboardToggle}
      workspace_buttons yes
      colors {
        statusline #ffffff
        background #202020
      }
    }

    # ${toString cfg.keyboardHeight} px: with ten keys across 568 px each key is
    # ~57 px (4.4 mm) wide; rows of ~80 px are what a fingertip needs.
    exec ${pkgs.wvkbd}/bin/wvkbd-mobintl -H ${toString cfg.keyboardHeight} --hidden
    exec ${pkgs.foot}/bin/foot
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
  };

  config = lib.mkIf cfg.enable {
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

    users.groups.shell = { };
    users.users.shell = {
      isNormalUser = true;
      uid = 1000;
      group = "shell";
      extraGroups = [ "seat" "video" "input" ];
      description = "owns the panel";
    };

    # No login prompt on the panel. The serial getty (serial-getty@ttyS0)
    # is untouched and stays the console. The VT getty is what
    # services.getty.autologinUser was landing on; masking it here means
    # tty1 never shows a prompt and never competes for the screen.
    systemd.services."getty@tty1".enable = false;
    systemd.services."autovt@tty1".enable = false;

    systemd.services.shell = {
      description = "sway on the panel";
      wantedBy = [ "multi-user.target" ];
      requires = [ "seatd.service" ];
      after = [ "seatd.service" "systemd-udev-settle.service" ];

      environment = {
        XDG_RUNTIME_DIR = "/run/shell";
        XDG_SEAT = "seat0";
        LIBSEAT_BACKEND = "seatd";
        # wlroots would choose Pixman on its own on a card with no render
        # node (render/wlr_renderer.c:268); naming it makes the choice a
        # stated intention that fails loudly if the device ever changes.
        WLR_RENDERER = "pixman";
        # A fixed IPC socket so `swaymsg` from the serial console needs no
        # discovery (sway/ipc-server.c honours SWAYSOCK when it is set).
        SWAYSOCK = "/run/shell/sway-ipc.sock";
      };
      path = [ pkgs.foot pkgs.wvkbd pkgs.procps pkgs.coreutils ];

      serviceConfig = {
        User = "shell";
        Group = "shell";
        RuntimeDirectory = "shell";
        RuntimeDirectoryMode = "0700";
        # seatd's unit is Type=simple (see above), so "after seatd" only
        # means the process exists. Wait for its socket, up to 10 s.
        ExecStartPre = pkgs.writeShellScript "wait-for-seatd" ''
          for i in $(seq 50); do
            [ -S /run/seatd.sock ] && exit 0
            sleep 0.2
          done
          echo "seatd socket never appeared" >&2
          exit 1
        '';
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
    ] ++ lib.optionals cfg.probes [
      cage
      cage-rgb565
      pkgs.drm_info
      pkgs.libinput
      pkgs.wayland-utils
      # evemu creates a uinput touchscreen and injects touches at known
      # panel coordinates (the kernel gained INPUT_UINPUT for exactly this),
      # so compositor -> keyboard -> terminal can be exercised unattended.
      # A software proxy: evidence from it is labelled "injected", and the
      # touch requirement still closes on a real tap at the bench.
      pkgs.evemu
      wlfps
    ];

    # swaymsg from a root shell on the serial console reaches the session's
    # socket without anyone having to remember the path.
    environment.variables.SWAYSOCK = "/run/shell/sway-ipc.sock";
  };
}
