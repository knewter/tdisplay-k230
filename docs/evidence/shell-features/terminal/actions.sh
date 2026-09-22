# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 540 995; tap 85 995; tap 170 1060; tap 525 1195; sleep 3; grim /tmp/terminal-keyboard.png; tap 375 28; sleep 3; grim /tmp/terminal-screen.png
