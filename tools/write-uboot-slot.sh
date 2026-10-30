#!/usr/bin/env bash
# Write ONE raw boot slot of the card -- the U-Boot slot at 2 MiB -- and
# nothing else, with read-back verification and a before/after hash of every
# region that must not change.
#
#   ./tools/write-uboot-slot.sh <fn_ug_u-boot.bin> /dev/disk/by-id/usb-Linux_UMS_disk_0-0:0
#   ./tools/write-uboot-slot.sh --check <image>            host-only: size/magic/padding report
#   K230_SLOT_TEST_FILE=1 ./tools/write-uboot-slot.sh <image> <regular file>   host test only
#
# Layout (nix/stage1.nix `layout`, SDK genimage.cfg), byte offsets:
#   0x100000  SPL copy 1 (512 KiB window)   preserved
#   0x180000  SPL copy 2 (512 KiB window)   preserved
#   0x200000  U-Boot (1 MiB window)         WRITTEN, zero-padded to 1 MiB
#   0x300000  environment (8 KiB, 1 MiB window; 0x320000 second copy)   preserved
#   >= 0x1e00000 / partitions               preserved
#
# Guardrails, same spirit as tools/flash.sh: a /dev/disk/by-id path only; the
# target must be a whole disk that is at least 64 MiB; the image must start
# with the K230 firmware magic and be no larger than the 1 MiB window; the
# operator types the last 12 characters of the by-id path. The U-Boot slot is
# read back with O_DIRECT (the board's UMS write cache has lied before:
# memory note flashing-a-vendor-card-board) and compared byte for byte with
# the padded image. SPL and environment regions are hashed before and after
# and must be identical, or the script exits 1 and says so.
set -euo pipefail

SLOT=$((2 * 1024 * 1024))
WINDOW=$((1024 * 1024))
die() { echo "error: $*" >&2; exit 1; }

if [ "${1:-}" = "--check" ]; then
  [ $# -eq 2 ] || die "usage: $0 --check <image>"
  IMG="$2"; CHECK_ONLY=1
else
  [ $# -eq 2 ] || die "usage: $0 <image> /dev/disk/by-id/<target>"
  IMG="$1"; TARGET="$2"; CHECK_ONLY=0
fi

[ -f "$IMG" ] || die "image not found: $IMG"
SIZE=$(stat -c %s "$IMG")
[ "$SIZE" -le "$WINDOW" ] || die "image is $SIZE bytes; the U-Boot window is $WINDOW (the environment starts after it)"
[ "$(head -c 4 "$IMG")" = "K230" ] || die "image does not start with the K230 firmware magic (is this the fn_ug_u-boot.bin, not u-boot.bin?)"

PAD=$(mktemp)
trap 'rm -f "$PAD"' EXIT
cp "$IMG" "$PAD"
truncate -s "$WINDOW" "$PAD"
SHA=$(sha256sum "$PAD" | cut -d' ' -f1)
echo "image   : $IMG ($SIZE bytes, K230 magic ok)"
echo "padded  : $WINDOW bytes, sha256 $SHA"
[ "$CHECK_ONLY" = 1 ] && exit 0

if [ "${K230_SLOT_TEST_FILE:-}" = 1 ]; then
  [ -f "$TARGET" ] || die "test target must be a regular file"
  REAL="$TARGET"; DIRECT=""
else
  case "$TARGET" in
    /dev/disk/by-id/*) ;;
    *) die "target must be a /dev/disk/by-id path, got: $TARGET" ;;
  esac
  [ -e "$TARGET" ] || die "target does not exist: $TARGET"
  REAL=$(readlink -f "$TARGET")
  [ -b "$REAL" ] || die "target is not a block device: $TARGET -> $REAL"
  if [ -e "/sys/class/block/$(basename "$REAL")/partition" ]; then
    die "$TARGET resolves to a PARTITION ($REAL). Give the whole disk."
  fi
  BYTES=$(( $(cat "/sys/class/block/$(basename "$REAL")/size") * 512 ))
  [ "$BYTES" -ge $((64 * 1024 * 1024)) ] || die "target is only $BYTES bytes; no card is that small"
  DIRECT="iflag=direct"
  echo "target  : $TARGET -> $REAL ($BYTES bytes)"
  lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$REAL" | sed 's/^/          /'
  printf 'Type the last 12 characters of the by-id path to confirm: '
  read -r answer
  [ "$answer" = "${TARGET: -12}" ] || die "got '$answer' -- nothing written"
fi

SUDO=sudo; [ -w "$REAL" ] && SUDO=""
rd() { $SUDO dd if="$REAL" bs=4096 skip=$(($1 / 4096)) count=$(($2 / 4096)) $DIRECT status=none; }

# Regions that must not change: both SPL copies, the environment window, and
# the first 64 KiB after the U-Boot window as a canary for overruns.
hash_preserved() {
  for spec in "spl1 $((1024*1024)) $((512*1024))" "spl2 $((1536*1024)) $((512*1024))" \
              "env  $((3*1024*1024)) $((1024*1024))"; do
    set -- $spec
    printf '%s %s\n' "$1" "$(rd "$2" "$3" | sha256sum | cut -d' ' -f1)"
  done
}
BEFORE=$(hash_preserved)
echo "preserved regions before:"; echo "$BEFORE" | sed 's/^/  /'
echo "old slot sha256: $(rd $SLOT $WINDOW | sha256sum | cut -d' ' -f1)"

echo "writing the U-Boot slot ($WINDOW bytes at byte offset $SLOT)..."
$SUDO dd if="$PAD" of="$REAL" bs=1M seek=2 count=1 conv=notrunc,fsync oflag=sync status=none
sync

GOT=$(rd $SLOT $WINDOW | sha256sum | cut -d' ' -f1)
echo "slot read back: $GOT"
[ "$GOT" = "$SHA" ] || die "READ-BACK MISMATCH. The slot does not hold the image. Do NOT power-cycle into it; rewrite the saved slot image."
AFTER=$(hash_preserved)
if [ "$BEFORE" != "$AFTER" ]; then
  echo "preserved regions after:"; echo "$AFTER" | sed 's/^/  /'
  die "a preserved region changed. Restore it from the card backup before booting."
fi
echo "preserved regions unchanged. slot verified: $SHA"
