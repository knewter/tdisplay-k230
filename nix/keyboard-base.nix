{ writeShellScriptBin, python3 }:
writeShellScriptBin "k230-keyboard-based" ''
  exec ${python3}/bin/python3 ${./keyboard-base/keyboard_based.py} "$@"
''
