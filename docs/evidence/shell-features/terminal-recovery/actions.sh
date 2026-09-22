# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 245 28; tap 245 28; tap 375 28; sleep 1; tap 143 995; tap 170 1128; tap 425 995; tap 255 995; tap 525 1195; sleep 2; grim /tmp/terminal-closed.png; tap 375 28; tap 245 28; sleep 2; grim /tmp/recovery-menu.png; tap 245 28; sleep 2; grim /tmp/terminal-recovered.png; swaymsg -t get_tree -r
