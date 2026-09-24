{ writeShellScriptBin, python3, procps, systemd }:
writeShellScriptBin "k230-settings" ''
  export K230_PGREP=${procps}/bin/pgrep
  export K230_PKILL=${procps}/bin/pkill
  export K230_SYSTEMCTL=${systemd}/bin/systemctl
  export K230_SUDO=/run/wrappers/bin/sudo
  exec ${python3}/bin/python3 ${../tools/device_settings.py} "$@"
''
