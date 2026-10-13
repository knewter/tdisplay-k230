#!/bin/sh
# abrun.sh landscape|portrait  -- runs ON the board as root
MODE=$1; DEV=/dev/input/event2
K=$(systemctl show -p ExecStart shell-ui | grep -o "/nix/store/[^ ]*k230-shell-rust" | head -1)
hide() { runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell SWAYSOCK=/run/shell/sway-ipc.sock DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus $K --surface hide >/dev/null 2>&1; }
ticks() { awk '{print $14+$15}' /proc/$1/stat; }
SW=$(pgrep -x sway | head -1); UI=$(pgrep -x k230-shell-rust | head -1)
if [ "$MODE" = landscape ]; then BOT="562 616 250 616"; TOP="6 616 380 616"; else BOT="284 1225 284 900"; TOP="284 6 284 380"; fi
s0=$(ticks $SW); u0=$(ticks $UI); t0=$(date +%s%N)
for i in 1 2 3; do
  /tmp/inject-tap.sh $DEV $BOT; sleep 1.5; hide; sleep 1.5
  /tmp/inject-tap.sh $DEV $TOP; sleep 1.5; hide; sleep 1.5
done
s1=$(ticks $SW); u1=$(ticks $UI); t1=$(date +%s%N)
echo "$MODE wall_ms=$(( (t1-t0)/1000000 )) sway_ticks=$((s1-s0)) ui_ticks=$((u1-u0)) hz=$(getconf CLK_TCK)"
