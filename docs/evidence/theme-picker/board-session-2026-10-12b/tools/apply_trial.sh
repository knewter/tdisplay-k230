#!/bin/sh
# Board, root. 6.6 / 10.7: cold restart, open picker, neighbour warm wait, browse to the light neighbour, tap-apply, browse back, tap-apply.
PY=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
B=/root/tmp/k230-theme-board-session-20261012
W=/nix/store/q5mizkqivyl4av7in90n59nc8fsnwh08-k230-shell-rust/bin/k230-shell-rust
SHELLENV="XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1"
OUT=/run/shell/apply-trial-b; rm -rf $OUT; mkdir -p $OUT; chown shell:shell $OUT
shot() { runuser -u shell -- env $SHELLENV grim -s 0.5 $OUT/$1.png; }
mark() { echo "MARK $1 $(date -u +%FT%T.%3NZ) mono=$(cut -d' ' -f1 /proc/uptime)"; }
ACTIVE=/home/shell/.local/state/omarchy/current/active
echo "ACTIVE_BEFORE $(readlink -f $ACTIVE | sha256sum | cut -c1-16)"
mark restart; systemctl restart theme-helper shell-ui; sleep 6
runuser -u shell -- env $SHELLENV $W --surface settings; sleep 3
mark open; $PY $B/touch.py 480 130; sleep 15
mark open-settled; shot 0-open-dark
# browse one item toward the light neighbour: 240 px drag, hold 700 ms, release (the 18.3 'hold-release' program; settles on item 1)
$PY - <<PYEOF
import importlib.util
s=importlib.util.spec_from_file_location("g","$B/gestures.py");g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
import glob,pathlib
dev=[p.parent.parent.name for p in pathlib.Path("/sys/class/input").glob("event*/device/name") if p.read_text().strip()==g.DEVICE_NAME and str(p.resolve()).startswith("/sys/devices/virtual/input/")]
g.inject("/dev/input/"+dev[0], g.program("hold-release","theme"))
PYEOF
sleep 2.5; mark browsed-light; shot 1-light-selected
mark tap-apply-light; $PY $B/touch.py 284 430; sleep 4; mark applied-light; shot 2-light-applied
echo "ACTIVE_LIGHT $(readlink -f $ACTIVE | sha256sum | cut -c1-16)"
# back toward the dark theme (index 0): a fast swipe right clamps at the first item
$PY $B/touch.py 190 430 430 430; sleep 3; mark browsed-dark; shot 3-dark-selected
mark tap-apply-dark; $PY $B/touch.py 284 430; sleep 4; mark applied-dark; shot 4-dark-applied
echo "ACTIVE_AFTER $(readlink -f $ACTIVE | sha256sum | cut -c1-16)"
