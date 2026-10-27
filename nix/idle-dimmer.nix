{ writeShellScriptBin, python3 }:
writeShellScriptBin "k230-idle-dimmer" ''
  exec ${python3}/bin/python3 ${./idle-dimmer/idle_dimmer.py} "$@"
''
