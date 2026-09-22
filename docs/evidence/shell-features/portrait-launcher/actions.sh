# Software-injected touches on physical board; no finger accuracy claim.
export SWAYSOCK=/run/shell/sway-ipc.sock XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SYSTEMD_PAGER=cat PAGER=cat
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }
state() { echo "STATE:$1"; swaymsg -t get_tree -r | jq -c '[recurse(.nodes[]?, .floating_nodes[]?) | select(.app_id? != null) | {id,app_id,focused,name}]'; pgrep -x k230-touch-laun || true; }
tap 115 28; sleep 2; grim /tmp/launcher-menu.png; state apps
tap 115 28; sleep 1; state repeated_apps
tap 284 295; sleep 2; state terminal
tap 115 28; sleep 1; tap 284 491; sleep 3; grim /tmp/launcher-monitor.png; state monitor
tap 115 28; sleep 1; tap 284 687; sleep 2; grim /tmp/launcher-new-terminal.png; state new_terminal
tap 115 28; sleep 1; tap 284 1146; sleep 1; state back
tap 388 28; sleep 2; tap 115 28; sleep 2; grim /tmp/launcher-keyboard.png; state with_keyboard
tap 284 765; sleep 1; tap 388 28; sleep 2; state keyboard_closed
tap 115 28; sleep 1; tap 284 295 284 491; sleep 1; state drag_cancelled; grim /tmp/launcher-drag-cancelled.png
tap 284 1146; sleep 1; state final
echo LAUNCHER_DEMO_DONE
