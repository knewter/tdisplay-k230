{ writeShellScriptBin, python3 }:
writeShellScriptBin "k230-power-keyd" ''
  exec ${python3}/bin/python3 ${./power-keyd/power_keyd.py} "$@"
''
