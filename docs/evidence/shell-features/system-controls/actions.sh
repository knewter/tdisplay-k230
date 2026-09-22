# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 505 28; sleep 2; grim /tmp/system-menu.png; tap 285 28; sleep 2; grim /tmp/poweroff-confirm.png; tap 425 28; sleep 2; tap 505 28; tap 110 28; sleep 2; grim /tmp/reboot-confirm.png; tap 425 28; sleep 2; grim /tmp/system-return.png
