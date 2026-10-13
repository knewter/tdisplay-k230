#!/bin/sh
# bench.sh MODE -- on board: arm card bench, run abrun gestures, dump rows
MODE=$1
M() { runuser -u shell -- env SWAYSOCK=/run/shell/sway-ipc.sock swaymsg "$@" >/dev/null; }
since=$(date '+%Y-%m-%d %H:%M:%S')
M card_shell benchmark injected
/tmp/abrun.sh $MODE
M card_shell benchmark-stop
sleep 1
journalctl -u shell --since "$since" --no-pager -o short-monotonic | grep -E "K230_CARD_(SHELL (frame-cost|repaint-cost|frame-damage)|BENCH)" > /tmp/bench-$MODE.log
wc -l < /tmp/bench-$MODE.log
