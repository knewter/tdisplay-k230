#!/usr/bin/env bash
# Host probe for gtk-app-text-follows-the-text-size task 1.1. Starts a
# headless Sway, then runs probe_window.py once per settings variant with the
# same GSETTINGS_BACKEND=keyfile/GDK_BACKEND=wayland environment as the
# board's Files launcher (nix/shell.nix mkFilesAppLauncher).
# Usage: probe-env.sh, which builds the pinned GTK 4.22/libadwaita 1.9
# closure, sets PYTHONPATH/GI_TYPELIB_PATH/SCHEMA_DIR and runs this.
set -u
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
export XDG_RUNTIME_DIR=$work/run; mkdir -m 700 "$XDG_RUNTIME_DIR"
WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 \
  sway -c /dev/null >"$work/sway.log" 2>&1 &
sway_pid=$!
for _ in $(seq 50); do [ -S "$XDG_RUNTIME_DIR/wayland-1" ] && break; sleep 0.1; done
# The board runs no xdg-desktop-portal; the host session bus would offer
# the desktop's own portal settings, so the probe gets no session bus.
unset DBUS_SESSION_BUS_ADDRESS
export WAYLAND_DISPLAY=wayland-1 GDK_BACKEND=wayland GSK_RENDERER=cairo GSETTINGS_BACKEND=keyfile
export XDG_DATA_DIRS="$SCHEMA_DIR${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
KF_FONT=$'[org/gnome/desktop/interface]\nfont-name=\'DejaVu Sans 13\'\n'
KF_FONT_SCALE2=$'[org/gnome/desktop/interface]\nfont-name=\'DejaVu Sans 13\'\ntext-scaling-factor=2.0\n'
INI_EMPTY=$'[Settings]\n'
INI_FONT13=$'[Settings]\ngtk-font-name=DejaVu Sans 13\n'
INI_FONT26=$'[Settings]\ngtk-font-name=DejaVu Sans 26\n'
run() {
  local name=$1 keyfile=$2 ini=$3
  local home=$work/$name
  mkdir -p "$home/glib-2.0/settings" "$home/gtk-4.0"
  printf '%s' "$keyfile" >"$home/glib-2.0/settings/keyfile"
  printf '%s' "$ini" >"$home/gtk-4.0/settings.ini"
  printf '%s ' "$name"
  XDG_CONFIG_HOME=$home timeout 20 python3 "$here/probe_window.py" 2>>"$work/probe.err" \
    || echo '{"error": "probe failed"}'
}
if [ "${PROBE_GTK:-4}" = 3 ]; then
  CSS26=$'window, tooltip { font-family: "DejaVu Sans"; font-size: 26pt; }\n'
  run3() {
    local name=$1 ini=$2 css=$3
    local home=$work/gtk3-$name
    mkdir -p "$home/gtk-3.0"
    printf '%s' "$ini" >"$home/gtk-3.0/settings.ini"
    printf '%s' "$css" >"$home/gtk-3.0/gtk.css"
    printf 'gtk3-%s ' "$name"
    GSETTINGS_BACKEND=memory XDG_CONFIG_HOME=$home timeout 20 python3 "$here/probe_window_gtk3.py" \
      2>>"$work/probe.err" || echo '{"error": "probe failed"}'
  }
  run3 neither "$INI_EMPTY" ""
  run3 settings-ini-13 "$INI_FONT13" ""
  run3 settings-ini-26 "$INI_FONT26" ""
  run3 css-window-26 "$INI_FONT13" "$CSS26"
  kill "$sway_pid"
  tail -4 "$work/probe.err" >&2
  exit 0
fi
run neither "" "$INI_EMPTY"
run keyfile-font "$KF_FONT" "$INI_EMPTY"
run keyfile-font-scale2 "$KF_FONT_SCALE2" "$INI_EMPTY"
run settings-ini-font13 "" "$INI_FONT13"
run ini26-with-keyfile13 "$KF_FONT" "$INI_FONT26"
kill "$sway_pid"
tail -4 "$work/probe.err" >&2
