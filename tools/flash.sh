#!/usr/bin/env bash
# Write an SD image to a card, with the guardrails image/sd-layout requires.
#
# Takes ONLY a /dev/disk/by-id path. Bare device nodes are refused, and that
# is not stylistic: this host carries four 8 TB RAID10 members on /dev/sda
# through /dev/sdd, and device letters were observed moving across a replug
# of the card reader during bring-up. A by-id path can only ever resolve to
# a reader slot. It still names the SLOT rather than the CARD, which is why
# the contents are printed and confirmation is required.
#
#   ./tools/flash.sh <image> /dev/disk/by-id/usb-...-0:1
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }

[ $# -eq 2 ] || die "usage: $0 <image> /dev/disk/by-id/<target>"
IMG="$1"; TARGET="$2"

[ -f "$IMG" ] || die "image not found: $IMG"

case "$TARGET" in
  /dev/disk/by-id/*) ;;
  /dev/sd*|/dev/nvme*|/dev/mmcblk*)
    die "refusing a bare device node.

  $TARGET names whatever the kernel happened to enumerate. On this host
  /dev/sda through /dev/sdd are the four 8 TB members of a RAID10 array,
  and reader letters move across a replug.

  Pass the by-id path instead. Candidates:
$(ls /dev/disk/by-id/ 2>/dev/null | grep -i -E 'usb.*(CRW|SD|Card)' | grep -v -- '-part' | sed 's|^|    /dev/disk/by-id/|' || echo '    (no card reader found)')" ;;
  *) die "target must be a /dev/disk/by-id path, got: $TARGET" ;;
esac

[ -e "$TARGET" ] || die "target does not exist: $TARGET"
REAL=$(readlink -f "$TARGET")
[ -b "$REAL" ] || die "target is not a block device: $TARGET -> $REAL"

# A partition, not a whole disk, is almost always a mistake here.
case "$REAL" in *[0-9]) 
  if [ -e "/sys/class/block/$(basename "$REAL")/partition" ]; then
    die "$TARGET resolves to a PARTITION ($REAL). Flash the whole disk."
  fi ;;
esac

SECTORS=$(cat "/sys/class/block/$(basename "$REAL")/size")
BYTES=$((SECTORS * 512))
[ "$BYTES" -gt 0 ] || die "$TARGET reports zero size — is a card actually in that slot?"

IMGBYTES=$(stat -c %s "$IMG")
[ "$IMGBYTES" -le "$BYTES" ] || die "image ($IMGBYTES bytes) is larger than the target ($BYTES bytes)"

echo "=============================================================="
echo " TARGET"
echo "   by-id : $TARGET"
echo "   device: $REAL"
echo "   size  : $BYTES bytes ($((BYTES / 1000000000)) GB)"
echo "   model : $(cat "/sys/class/block/$(basename "$REAL")/device/model" 2>/dev/null | xargs || echo '?')"
echo
echo " IMAGE"
echo "   $IMG"
echo "   $IMGBYTES bytes ($((IMGBYTES / 1000000)) MB)"
echo
echo " WHAT IS ON THE TARGET NOW — read this before answering"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$REAL" 2>/dev/null | sed 's/^/   /'
for m in $(lsblk -nro MOUNTPOINT "$REAL" 2>/dev/null | grep -v '^$'); do
  echo "   --- mounted at $m:"
  ls -A "$m" 2>/dev/null | head -12 | sed 's/^/       /'
  n=$(ls -A "$m" 2>/dev/null | wc -l); [ "$n" -gt 12 ] && echo "       ... and $((n - 12)) more"
done
echo "=============================================================="
echo
echo "This ERASES the target completely."
printf 'Type the last 12 characters of the by-id path to confirm: '
read -r answer
EXPECT="${TARGET: -12}"
[ "$answer" = "$EXPECT" ] || die "got '$answer', expected '$EXPECT' — nothing written"

for m in $(lsblk -nro MOUNTPOINT "$REAL" 2>/dev/null | grep -v '^$'); do
  echo "unmounting $m"; sudo umount "$m"
done

echo "writing..."
sudo dd if="$IMG" of="$REAL" bs=4M status=progress oflag=sync conv=fsync
sync
echo "done. $(date -Is)"
