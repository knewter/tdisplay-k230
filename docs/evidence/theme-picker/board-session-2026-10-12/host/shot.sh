#!/bin/sh
# usage: shot.sh NAME [scale]  -> NAME.png in cwd (native grim capture, pulled over ssh)
ssh -F ~/tmp/k230-coordination/ssh_config.private k230 "runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 grim -s ${2:-0.5} /run/shell/$1.png && cat /run/shell/$1.png && rm -f /run/shell/$1.png" > "$1.png"
