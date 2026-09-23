# Explicit QEMU fixture only. Importing this does not select the board shell.
{ lib, pkgs, ... }:
let
  cards = pkgs.callPackage ./card-shell.nix { swayUnwrapped = pkgs.sway-unwrapped; };
  client = pkgs.callPackage ./card-composition-probe-client { };
  config = pkgs.writeText "card-shell-qemu.conf" ''
    output HEADLESS-1 mode 568x1232
    seat seat0 fallback true
    focus_follows_mouse no
    for_window [app_id="^k230.card."] floating enable, border none, resize set 520 1040, move position 24 48
  '';
  guest = pkgs.writeShellScriptBin "card-shell-guest-smoke" ''
    exec ${pkgs.util-linux}/bin/runuser -u card-smoke -- \
      ${pkgs.python3}/bin/python3 ${../tools/card-shell-guest-smoke.py} \
      --client ${client}/bin/card-composition-probe-client \
      --keyboard-helper ${../tests/card_virtual_keyboard.py} "$@"
  '';
in {
  # The observed guest reaches multi-user with /dev/console output, but its
  # ttyS0 device unit never activates, so serial-getty cannot start. Bind this
  # explicit fixture's login to the existing kernel console instead.
  systemd.services.console-getty = {
    enable = true;
    wantedBy = [ "multi-user.target" ];
  };
  systemd.services."serial-getty@ttyS0".enable = false;
  # The netboot installation profile otherwise selects the nixos login.
  # Only the supervisor needs root; compositor and fixtures remain card-smoke.
  services.getty.autologinUser = lib.mkForce "root";
  users.groups.card-smoke = { };
  users.users.card-smoke = { isSystemUser = true; group = "card-smoke"; };
  environment.systemPackages = [ guest ];
  systemd.services.card-shell-smoke = {
    description = "QEMU-only card shell userspace fixture";
    wantedBy = [ "multi-user.target" ];
    environment = {
      XDG_RUNTIME_DIR = "/run/card-shell-smoke";
      SWAYSOCK = "/run/card-shell-smoke/sway-ipc.sock";
      WLR_BACKENDS = "headless";
      WLR_HEADLESS_OUTPUTS = "1";
      SWAY_K230_CARD_TEST_INPUT = "1";
    };
    serviceConfig = {
      User = "card-smoke";
      Group = "card-smoke";
      RuntimeDirectory = "card-shell-smoke";
      RuntimeDirectoryMode = "0700";
      ExecStart = pkgs.writeShellScript "start-card-shell-smoke" ''
        exec ${cards}/bin/card-shell --sway -c ${config} -d > "$XDG_RUNTIME_DIR/sway.log" 2>&1
      '';
      TimeoutStopSec = 10;
    };
  };
}
