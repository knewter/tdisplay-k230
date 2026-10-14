#!/bin/sh
# Board-side 6.6 run (second, on the power-off kernel). Logs to /var/tmp/k230-policy-test/ (survives poweroff).
export PATH=/run/current-system/sw/bin:/run/wrappers/bin
D=/var/tmp/k230-policy-test; mkdir -p $D; chmod 1777 $D; L=$D/samples.log
C=/sys/class/power_supply/bq25890-charger-0; G=/sys/class/power_supply/bq27220-0
K=$(systemctl show -p ExecStart shell-ui | grep -o "/nix/store/[^ ]*k230-shell-rust" | head -1)
E="env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SWAYSOCK=/run/shell/sway-ipc.sock DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus"
s() { echo "$(date -u +%FT%TZ) $1 online=$(cat $C/online) chg=$(cat $C/status) gauge=$(cat $G/status) uA=$(cat $G/current_now) cap=$(cat $G/capacity)" >> $L; }
seen() { journalctl -u k230-battery-policy --since "$T0" --no-pager -o cat | grep -q "$1"; }
restore() { echo 1 > $C/online; rm -f /run/k230-battery-policy.json; s "$1"; }
# The charger is reconnected by this unit's ExecStopPost when shutdown stops it.
T0=$(date "+%Y-%m-%d %H:%M:%S")
echo "start T0=$T0" > $L
echo '{"warn": 100, "urgent": 99, "shutdown": 98}' > /run/k230-battery-policy.json
s before; echo 0 > $C/online; s hiz-on
phase=1
while :; do
  sleep 10; s p$phase
  cap=$(cat $G/capacity)
  if [ "$cap" -lt 95 ]; then restore abort-low; exit 1; fi
  if [ $phase = 1 ] && seen "Battery critically low"; then
    runuser -u shell -- $E $K --surface shade >/dev/null 2>&1; sleep 2
    runuser -u shell -- $E grim $D/shade-countdown.png
    sleep 10; echo 1 > $C/online; s cable-cancel; phase=2
  elif [ $phase = 2 ] && seen "Shutdown cancelled"; then
    runuser -u shell -- $E grim $D/shade-cancelled.png
    rm -f /run/k230-battery-policy.json.keep
    runuser -u shell -- $E $K --surface hide >/dev/null 2>&1
    sleep 20; echo 0 > $C/online; s hiz-again; phase=3
  fi
done
