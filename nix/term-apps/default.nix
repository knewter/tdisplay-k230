{ runCommand, runtimeShell, python3 }:

# One Python program serves the Clock, Timer and Weather terminal apps; the
# k230-* commands only pick the app. The interpreter is the target python3
# already in the system closure (the keyboard base daemon uses it too).
runCommand "k230-term-apps" { } ''
  install -Dm644 ${./k230_term_apps.py} $out/lib/k230-term-apps/k230_term_apps.py
  mkdir -p $out/bin
  for app in clock timer weather; do
    cat > $out/bin/k230-$app <<EOF
  #!${runtimeShell}
  exec ${python3}/bin/python3 $out/lib/k230-term-apps/k230_term_apps.py $app "\$@"
  EOF
    chmod +x $out/bin/k230-$app
  done
''
