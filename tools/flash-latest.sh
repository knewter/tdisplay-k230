#!/usr/bin/env bash
# Build the current SD image and flash it, so a stale /nix/store path can
# never be flashed by mistake.
#
#   ./tools/flash-latest.sh [/dev/disk/by-id/...]      build (pure) and flash a card in a reader
#   ./tools/flash-latest.sh --ums                      ...or the card IN THE BOARD, over USB
#   ./tools/flash-latest.sh --dry-run [target]         build, print the image, stop
#   K230_STAGE1=vendor ./tools/flash-latest.sh ...     the vendor-compiled stage 1
#
# --ums: the board sits at its U-Boot prompt with a cable from this host to
# J3 (the data USB-C -- not J2, the charging one that carries the console),
# and `ums 0 mmc 1` has been typed there. U-Boot then presents the TF card
# as a USB mass-storage device and it appears under /dev/disk/by-id/ like
# any other disk. This script does not guess that name: it snapshots
# /dev/disk/by-id/ first, waits for one new whole-disk usb-* entry to
# appear, and hands exactly that by-id path to tools/flash.sh -- whose
# refusal of anything that is not a by-id path, and whose print-and-confirm
# step, apply unchanged. The reader path is the same script with a by-id
# argument, and is the recovery path when the board will not boot to
# U-Boot at all. See openspec/changes/the-card-is-flashed-over-usb-from-u-boot.
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
UMS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --ums)     UMS=1; shift ;;
    *) break ;;
  esac
done
TARGET="${1:-/dev/disk/by-id/usb-Generic-_USB3.0_CRW_-SD_201506301013-0:1}"

# Which by-id entries exist before U-Boot offers the card, so the one that
# appears afterwards is unambiguous. Taken before the build so that a slow
# build does not turn into a stale snapshot.
if [ "$UMS" = 1 ]; then
  [ $# -eq 0 ] || { echo "error: --ums finds its own target; do not pass one" >&2; exit 1; }
  BEFORE=$(ls /dev/disk/by-id/ 2>/dev/null | grep '^usb-' | grep -v -- '-part' | sort)
fi

# --out-link, NOT --no-link. Every build here was previously run with
# --no-link, which creates no GC root -- so a garbage collection deleted
# every image and most of the riscv64 closure, and the next flash had to
# rebuild ~950 derivations from source because riscv64 has no binary cache.
# result-sd-image is gitignored and keeps the image and its closure alive.
#
# Keep the image build deliberately bounded.  The cross closure has enough
# independent packages to make progress in parallel, but letting every job
# claim every host core makes a concurrent build swap itself to death.  Callers
# may raise these explicitly once they know the machine is otherwise idle.
#
# The local attic cache has also been intermittently unavailable.  It must not
# turn an image build into a timeout, so select the official cache for these
# build commands only; do not change the user's global Nix configuration.
#
MAX_JOBS="${K230_MAX_JOBS:-2}"
CORES="${K230_CORES:-2}"
NIX_IMAGE_ARGS=(--option substituters https://cache.nixos.org/ --max-jobs "$MAX_JOBS" --cores "$CORES")
case "${K230_STAGE1:-source}" in
  source)
    echo "building the image from the current tree (stage 1 from source)..." >&2
    nix build "${NIX_IMAGE_ARGS[@]}" \
      --out-link result-sd-image .#packages.x86_64-linux.sdImage
    ;;
  vendor)
    DIR="$PWD/firmware/stage1"
    for f in fn_u-boot-spl.bin fn_ug_u-boot.bin env.env fw_jump.bin fw_jump_add_uboot_head.bin; do
      [ -f "$DIR/$f" ] || { echo "error: K230_STAGE1=vendor but $DIR/$f is missing; run ./tools/gen-stage1.sh" >&2; exit 1; }
    done
    echo "building the image from the current tree (VENDOR-COMPILED stage 1 from $DIR)..." >&2
    K230_STAGE1_DIR="$DIR" \
      nix build --impure "${NIX_IMAGE_ARGS[@]}" \
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

if [ "$UMS" = 1 ]; then
  cat >&2 <<EOM
waiting for the board to offer its card over USB.
  On the board, at the K230# prompt, with a cable from this host to J3:   ums 0 mmc 1
  (Ctrl-C there ends it. This waits up to 300 s for a new /dev/disk/by-id/usb-* disk.)
EOM
  NEW=""
  for _ in $(seq 1 300); do
    NOW=$(ls /dev/disk/by-id/ 2>/dev/null | grep '^usb-' | grep -v -- '-part' | sort)
    NEW=$(comm -13 <(echo "$BEFORE") <(echo "$NOW") | grep . || true)
    [ -n "$NEW" ] && break
    sleep 1
  done
  [ -n "$NEW" ] || { echo "error: no new USB disk appeared in 300 s; is the board at 'ums 0 mmc 1' and the cable in J3?" >&2; exit 1; }
  if [ "$(echo "$NEW" | wc -l)" -ne 1 ]; then
    echo "error: more than one new USB disk appeared; refusing to pick:" >&2; echo "$NEW" | sed 's/^/  /' >&2; exit 1
  fi
  TARGET="/dev/disk/by-id/$NEW"
  echo "the board's card appeared as $TARGET" >&2
  # Give udev a moment to settle the partition nodes before flash.sh lists them.
  udevadm settle 2>/dev/null || sleep 2
fi

if [ "$DRY_RUN" = 1 ]; then
  echo "dry run: not flashing $TARGET" >&2
  exit 0
fi

for m in $(lsblk -nro MOUNTPOINT "$(readlink -f "$TARGET")" 2>/dev/null | grep -v '^$'); do
  echo "unmounting $m" >&2; udisksctl unmount -b "$(findmnt -nro SOURCE "$m")" >/dev/null 2>&1 || true
done

exec ./tools/flash.sh "$IMG" "$TARGET"
