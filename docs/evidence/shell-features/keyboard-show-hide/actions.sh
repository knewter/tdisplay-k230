# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 375 28; sleep 3; grim /tmp/keyboard-shown.png; tap 375 28; sleep 3; grim /tmp/keyboard-hidden.png; tap 375 28; sleep 2
