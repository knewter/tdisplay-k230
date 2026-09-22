# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 245 28; sleep 2; grim /tmp/windows-menu.png; tap 115 28; sleep 2; grim /tmp/windows-terminal.png; tap 245 28; tap 375 28; sleep 2; grim /tmp/windows-next.png; tap 115 28; sleep 2; grim /tmp/windows-monitor.png; swaymsg -t get_tree -r
