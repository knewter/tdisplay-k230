#!/bin/sh
# Alternate stock and no-toast-shadow launches; each runs until Files goes idle.
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
killf() { for p in /proc/[0-9]*; do [ "$(cat $p/comm 2>/dev/null)" = ".nautilus-wrapp" ] && kill ${p#/proc/}; done; sleep 3; }
for run in "$@"; do
  case $run in
    stock) L=/nix/store/z39jlc9wcx98wjnprp2c1gbqwdk6chdv-k230-nautilus/bin/k230-nautilus ;;
    noshadow) L=/var/tmp/k230-nautilus-noanim ;;
    gtkfix) L=/var/tmp/k230-nautilus-gtkfix ;;
  esac
  killf
  echo "== $run $(date +%T)"
  $PY /var/tmp/files_probe.py 300 $L | grep -E "pid=|IDLE|t=(10|30|60|120|200|290)\."
done
killf
