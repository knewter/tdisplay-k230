#!/usr/bin/env bash
# Resolve MIME associations against a built NixOS system (host GIO, not the
# board's). Usage: tests/gio_mime_built_tree.sh <system-result-link> [type...]
# Isolates HOME so no per-user mimeapps.list leaks in. Evidence for
# files-open-in-the-right-app task 1.2.
set -u
sys=$(readlink -f "${1:?system result link}")
shift
types=("$@")
[ ${#types[@]} -gt 0 ] || types=(image/png application/pdf inode/directory text/plain)
entries=$(nix-store -qR "$sys" | grep k230-handheld-desktop-entries | head -1)
home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT
echo "# gio mime against the built tree, host GIO (not the board's)"
echo "# system: $sys"
echo "# handheld entries: $entries"
echo "# gio: $(gio version 2>&1 | head -1)"
echo "# env: PATH=<system>/sw/bin:<host PATH> (so bare Exec= names resolve; the binaries are riscv64 and are not run) HOME=<empty> XDG_CONFIG_DIRS=<system>/etc/xdg XDG_DATA_DIRS=<handheld entries>/share:<system>/sw/share"
for t in "${types[@]}"; do
  echo
  echo "\$ gio mime $t"
  PATH=$sys/sw/bin:$PATH HOME=$home XDG_CONFIG_HOME=$home/c XDG_DATA_HOME=$home/d \
    XDG_CONFIG_DIRS=$sys/etc/xdg \
    XDG_DATA_DIRS=$entries/share:$sys/sw/share \
    gio mime "$t" 2>&1
done
