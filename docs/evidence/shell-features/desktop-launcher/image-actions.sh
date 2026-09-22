# Injected touches; fresh image, no home restoration or service overrides.
export SWAYSOCK=/run/shell/sway-ipc.sock XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SYSTEMD_PAGER=cat PAGER=cat
readlink /run/current-system
systemctl show shell -p DropInPaths -p ExecStart
ls -ld /home/shell/.config /home/shell/.local/share/applications 2>/dev/null || true
/tmp/inject-tap.sh /dev/input/event1 115 28
sleep 3
grim /tmp/image-apps.png
/tmp/inject-tap.sh /dev/input/event1 460 1165
sleep 3
grim /tmp/image-entries.png
/tmp/inject-tap.sh /dev/input/event1 284 764
sleep 3
grim /tmp/image-htop.png
swaymsg -t get_tree -r | /nix/store/fy9xmga7mbqqiqp6gaj79239a98ssy9g-jq-riscv64-unknown-linux-gnu-1.8.2-bin/bin/jq -Mc '[recurse(.nodes[]?,.floating_nodes[]?)|select(.app_id? != null)|{id,app_id,focused,name}]'
/tmp/inject-tap.sh /dev/input/event1 115 28
sleep 2
echo IMAGE_LAUNCHER_DEMO_DONE
