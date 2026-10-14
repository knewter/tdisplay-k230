#!/bin/sh
N=$(ls -d /nix/store/*-k230-notifications/bin/k230-notifications|head -1)
K=$(systemctl show -p ExecStart shell-ui | grep -o "/nix/store/[^ ]*k230-shell-rust" | head -1)
E="env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SWAYSOCK=/run/shell/sway-ipc.sock DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus"
mkdir -p /tmp/tt; chmod 1777 /tmp/tt
$N emit --summary "Battery critically low" --body "Shutting down in 60 seconds." --tag battery --priority critical
runuser -u shell -- $E $K --surface shade >/dev/null 2>&1; sleep 3
$N emit --summary "Charging" --body "Shutdown cancelled." --tag battery --priority ordinary
sleep 3; runuser -u shell -- $E grim /tmp/tt/a3.png
sleep 10; runuser -u shell -- $E grim /tmp/tt/a13.png
runuser -u shell -- $E $K --surface hide >/dev/null 2>&1
$N history | head -c 600; echo
