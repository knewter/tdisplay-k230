{ pkgs, python3 ? pkgs.python3 }:

# Python source is immutable Nix input; no network names or credentials live here.
pkgs.writeShellScriptBin "k230-wifi-settings-broker" ''
  exec ${python3}/bin/python3 ${../tools/wifi_settings_broker.py} "$@"
''
