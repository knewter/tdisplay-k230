{ writeShellScriptBin, python }:
# org.freedesktop.Notifications for the session bus. `python` is the
# interpreter with jeepney (pure Python, no dependencies); shell.nix names the
# same interpreter and script in the broker's trusted-source map.
writeShellScriptBin "k230-notification-dbus" ''
  exec ${python}/bin/python3 ${../tools/notification_dbus.py} "$@"
''
