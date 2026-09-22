# Injected confirmation executes the configured sudo reboot action.
export XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1; /tmp/inject-tap.sh /dev/input/event1 505 28; sleep 2; /tmp/inject-tap.sh /dev/input/event1 110 28; sleep 2; grim /tmp/reboot-feature-confirm.png; sleep 2; /tmp/inject-tap.sh /dev/input/event1 140 28
