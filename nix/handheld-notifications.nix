{ writeShellScriptBin, python3, sway }:
let swayClient = sway.override { enableXWayland = false; }; in
writeShellScriptBin "k230-notifications" ''
  export K230_SWAYMSG=${swayClient}/bin/swaymsg
  exec ${python3}/bin/python3 ${../tools/notification_center.py} "$@"
''
