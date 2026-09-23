# Injected input on the freshly flashed board.
export XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SWAYSOCK=/run/shell/sway-ipc.sock
pkill -x k230-touch-laun || true
pkill -RTMIN+2 -x wvkbd-mobintl || true
tap() { /run/inject-tap.sh /dev/input/event1 "$@"; }
tap 115 28
sleep 1
tap 284 990
sleep 1
grim /run/fresh-help.png
tap 460 1165
sleep 1
grim /run/fresh-help-2.png
tap 284 1165
tap 460 1165
sleep 1
grim /run/fresh-editor-card.png
date +%s.%N
tap 284 295
sleep 0.2
date +%s.%N
ps -C nano -o comm,rss
sleep 1
grim /run/fresh-editor.png
tap 115 28
sleep 1
tap 460 1165
tap 460 1165
sleep 1
grim /run/fresh-nnn-card.png
date +%s.%N
tap 284 520
sleep 0.2
date +%s.%N
ps -C .nnn-wrapped -o comm,rss
sleep 1
grim /run/fresh-nnn.png
echo FRESH_APP_CHECK_DONE
