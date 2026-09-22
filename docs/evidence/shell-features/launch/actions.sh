# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 375 28; tap 115 28; sleep 3; grim /tmp/apps-menu.png; tap 285 28; sleep 4; grim /tmp/monitor-screen.png
