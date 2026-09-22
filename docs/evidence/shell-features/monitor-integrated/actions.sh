# Injected uinput actions on the physical board.
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }; tap 115 28; sleep 2; tap 285 28; sleep 4; swaymsg -t get_tree -r; for pid in $(pidof htop); do tr "\0" "\n" < /proc/$pid/environ | grep ^HTOPRC=; done
