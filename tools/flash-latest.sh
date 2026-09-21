#!/usr/bin/env bash
# Build the current SD image and flash it, so a stale /nix/store path can
# never be flashed by mistake.
set -euo pipefail
cd "$(dirname "$0")/.."
TARGET="${1:-/dev/disk/by-id/usb-Generic-_USB3.0_CRW_-SD_201506301013-0:1}"

echo "building the image from the current tree..." >&2
IMG=$(K230_STAGE1_DIR="$PWD/firmware/stage1" \
  nix build --impure --no-link --print-out-paths .#packages.x86_64-linux.sdImage)
echo "image: $IMG" >&2

for m in $(lsblk -nro MOUNTPOINT "$(readlink -f "$TARGET")" 2>/dev/null | grep -v '^$'); do
  echo "unmounting $m" >&2; udisksctl unmount -b "$(findmnt -nro SOURCE "$m")" >/dev/null 2>&1 || true
done

exec ./tools/flash.sh "$IMG" "$TARGET"
