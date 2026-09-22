#!/usr/bin/env bash
# Build the current SD image and flash it, so a stale /nix/store path can
# never be flashed by mistake.
#
#   ./tools/flash-latest.sh [/dev/disk/by-id/...]      build (pure) and flash
#   ./tools/flash-latest.sh --dry-run [target]         build, print the image, stop
#   K230_STAGE1=vendor ./tools/flash-latest.sh ...     the vendor-compiled stage 1
#
# The image's stage 1 -- SPL, U-Boot, environment, OpenSBI -- is built from
# source by the flake (nix/stage1.nix); a plain `nix build .#sdImage` is the
# whole recipe and this script runs exactly that. Booted on the board on
# 2026-09-22: docs/evidence/stage1-from-source.txt.
#
# K230_STAGE1=vendor is the one override, and it has to be spelled out: it
# selects the vendor-compiled binaries tools/gen-stage1.sh leaves in
# firmware/stage1/ (gitignored), via --impure and K230_STAGE1_DIR. It exists
# for bisecting a boot failure against the bytes the board booted before
# stage 1 was built here, and for nothing else. It used to be this script's
# only behaviour, which after the from-source build landed would have meant
# `nix build .#sdImage` and `./tools/flash-latest.sh` silently writing two
# different stage 1s.
set -euo pipefail
cd "$(dirname "$0")/.."

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi
TARGET="${1:-/dev/disk/by-id/usb-Generic-_USB3.0_CRW_-SD_201506301013-0:1}"

# --out-link, NOT --no-link. Every build here was previously run with
# --no-link, which creates no GC root -- so a garbage collection deleted
# every image and most of the riscv64 closure, and the next flash had to
# rebuild ~950 derivations from source because riscv64 has no binary cache.
# result-sd-image is gitignored and keeps the image and its closure alive.
#
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
case "${K230_STAGE1:-source}" in
  source)
    echo "building the image from the current tree (stage 1 from source)..." >&2
    nix build --max-jobs 8 --cores 0 \
      --out-link result-sd-image .#packages.x86_64-linux.sdImage
    ;;
  vendor)
    DIR="$PWD/firmware/stage1"
    for f in fn_u-boot-spl.bin fn_ug_u-boot.bin env.env fw_jump.bin fw_jump_add_uboot_head.bin; do
      [ -f "$DIR/$f" ] || { echo "error: K230_STAGE1=vendor but $DIR/$f is missing; run ./tools/gen-stage1.sh" >&2; exit 1; }
    done
    echo "building the image from the current tree (VENDOR-COMPILED stage 1 from $DIR)..." >&2
    K230_STAGE1_DIR="$DIR" \
      nix build --impure --max-jobs 8 --cores 0 \
        --out-link result-sd-image-vendor-stage1 .#packages.x86_64-linux.sdImage
    ;;
  *)
    echo "error: K230_STAGE1 must be 'source' (default) or 'vendor', got '${K230_STAGE1}'" >&2; exit 1 ;;
esac
if [ "${K230_STAGE1:-source}" = vendor ]; then
  IMG=$(readlink -f result-sd-image-vendor-stage1)
  WHICH=$(K230_STAGE1_DIR="$DIR" nix eval --impure --raw .#stage1.source 2>/dev/null || echo '?')
else
  IMG=$(readlink -f result-sd-image)
  WHICH=$(nix eval --raw .#stage1.source 2>/dev/null || echo '?')
fi
echo "image: $IMG" >&2
echo "stage 1: $WHICH" >&2

if [ "$DRY_RUN" = 1 ]; then
  echo "dry run: not flashing $TARGET" >&2
  exit 0
fi

for m in $(lsblk -nro MOUNTPOINT "$(readlink -f "$TARGET")" 2>/dev/null | grep -v '^$'); do
  echo "unmounting $m" >&2; udisksctl unmount -b "$(findmnt -nro SOURCE "$m")" >/dev/null 2>&1 || true
done

exec ./tools/flash.sh "$IMG" "$TARGET"
