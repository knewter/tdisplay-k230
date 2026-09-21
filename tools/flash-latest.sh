#!/usr/bin/env bash
# Build the current SD image and flash it, so a stale /nix/store path can
# never be flashed by mistake.
set -euo pipefail
cd "$(dirname "$0")/.."
TARGET="${1:-/dev/disk/by-id/usb-Generic-_USB3.0_CRW_-SD_201506301013-0:1}"

# --out-link, NOT --no-link. Every build here was previously run with
# --no-link, which creates no GC root -- so a garbage collection deleted
# every image and most of the riscv64 closure, and the next flash had to
# rebuild ~950 derivations from source because riscv64 has no binary cache.
# result-sd-image is gitignored and keeps the image and its closure alive.
echo "building the image from the current tree..." >&2
# --max-jobs, and deliberately NOT --cores.
#
# nix defaults to max-jobs = 1: one derivation at a time, each handed the
# whole machine. The kernel is big-parallel and genuinely uses all 32
# cores, but the riscv64 closure is a long tail of small packages that use
# about one core each, so a full rebuild's tail runs effectively
# single-threaded on a 32-core box. 8 concurrent jobs fixes that.
#
# cores stays 0 (= all cores per job) on purpose. Pinning it to 32/8 = 4
# would fill the machine neatly during a full rebuild, but the common case
# here is "the kernel changed, rebuild the kernel and the image" -- a
# single big-parallel derivation, which would then get make -j4 instead of
# -j32 and take roughly eight times as long. Oversubscription when several
# small packages run at once costs far less than that.
K230_STAGE1_DIR="$PWD/firmware/stage1" \
  nix build --impure --max-jobs 8 --cores 0 \
    --out-link result-sd-image .#packages.x86_64-linux.sdImage
IMG=$(readlink -f result-sd-image)
echo "image: $IMG" >&2

for m in $(lsblk -nro MOUNTPOINT "$(readlink -f "$TARGET")" 2>/dev/null | grep -v '^$'); do
  echo "unmounting $m" >&2; udisksctl unmount -b "$(findmnt -nro SOURCE "$m")" >/dev/null 2>&1 || true
done

exec ./tools/flash.sh "$IMG" "$TARGET"
