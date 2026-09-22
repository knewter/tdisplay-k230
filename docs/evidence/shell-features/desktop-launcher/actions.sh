set -e
export SWAYSOCK=/run/shell/sway-ipc.sock XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 SYSTEMD_PAGER=cat PAGER=cat
entry=/home/shell/.local/share/applications/k230-evidence-temp.desktop
[ ! -e "$entry" ]
mkdir -p /home/shell/.local/share/applications
tap() { /tmp/inject-tap.sh /dev/input/event1 "$@"; }
state() { echo "STATE:$1"; swaymsg -t get_tree -r | /nix/store/fy9xmga7mbqqiqp6gaj79239a98ssy9g-jq-riscv64-unknown-linux-gnu-1.8.2-bin/bin/jq -Mc '[recurse(.nodes[]?,.floating_nodes[]?)|select(.app_id? != null)|{id,app_id,focused,name}]'; pgrep -x k230-touch-laun || true; }
snap() { grim /tmp/desktop-"$1".png; }
tap 115 28; sleep 3; snap apps; state apps; cat /proc/$(pgrep -x k230-touch-laun)/smaps_rollup
tap 460 1165; sleep 2; snap second-page; state second_page
tap 284 764; sleep 3; snap htop; state desktop_htop
cat > "$entry" <<'ENTRY'
[Desktop Entry]
Type=Application
Name=AAA Evidence
Exec=foot --app-id=k230-discovery-proof --title=Desktop-entry-test
Terminal=false
ENTRY
tap 115 28; sleep 2; snap added; state added
tap 284 990; sleep 3; snap launched; state discovered_entry_launched
rm "$entry"
tap 115 28; sleep 2; snap removed; state removed
tap 284 1165; sleep 1
tap 388 28; sleep 2; tap 115 28; sleep 2; snap keyboard; state keyboard
tap 460 765; sleep 2; snap keyboard-page-two; state keyboard_page_two
tap 284 765; sleep 1; tap 388 28; sleep 2
cat > "$entry" <<'ENTRY'
[Desktop Entry]
Type=Application
Name=AAA Unavailable
Exec=/run/current-system/sw/bin/true
Path=/k230-evidence-directory-does-not-exist
Terminal=false
ENTRY
tap 115 28; sleep 2; tap 284 990; sleep 2; snap error; state error_retains_launcher
rm "$entry"
tap 284 1165; sleep 1; state recovered
swaymsg '[app_id="k230-discovery-proof"] kill'
tap 115 28; sleep 2; snap final; state final
echo DESKTOP_DISCOVERY_DEMO_DONE
