#!/usr/bin/env bash
# THE VENDOR-COMPILED FALLBACK, not the way stage 1 is built.
#
# Stage 1 is built from source by the flake: `nix build .#stage1`, see
# nix/stage1.nix and firmware/stage1/PROVENANCE.txt. That is what
# `nix build .#sdImage` and ./tools/flash-latest.sh put on the card, and
# the board has booted it (docs/evidence/stage1-from-source.txt).
#
# This script builds the same five files the old way -- the SDK's own
# Docker build with the 1.9 GB Xuantie toolchain -- into firmware/stage1/,
# where they are gitignored and read by nothing unless asked for by name:
#
#     K230_STAGE1=vendor ./tools/flash-latest.sh
#     K230_STAGE1_DIR=$PWD/firmware/stage1 nix build --impure .#sdImage
#
# Keep it for bisecting: when a from-source stage 1 fails to boot, an image
# carrying the bytes the board booted before answers whether the change or
# the build is at fault. Needs the SDK checkout at .build/k230_linux_sdk
# with `make uboot` and `make opensbi` already run in it.
#
# What it does: reproduce the SDK's gen_uboot_bin() and env generation to
# produce exactly the files genimage.cfg places on the card, in the SDK
# container so the toolchain and the x86-64 helper binaries resolve.
set -euo pipefail
ROOT=/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230
docker run --rm \
  -v "$ROOT/.build/k230_linux_sdk:/sdk" \
  -v "$ROOT/.build/opt-toolchain:/opt/toolchain" \
  -w /sdk --network host ubuntu:22.04 bash -c '
set -euo pipefail
apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 xxd >/dev/null

# mkimage stamps the uImage header with the current time, which then
# changes the K230 firmware header SHA-256 over it -- so two builds of
# identical inputs produced different bytes and there was no way to tell a
# real change from a rebuild. mkimage honours SOURCE_DATE_EPOCH.
export SOURCE_DATE_EPOCH=1700000000

SDK=/sdk
CONF=k230_canmv_v3_defconfig
UB=$SDK/output/$CONF/build/uboot-2022.10
OUT=$SDK/output/$CONF/images/uboot
ENVF=$SDK/buildroot-overlay/board/canaan/k230-soc/env/default.env

BASE=$(grep CONFIG_MEM_LINUX_SYS_BASE $UB/board/canaan/common/sdk_autoconf.h | awk "{print \$3}")
echo "CONFIG_MEM_LINUX_SYS_BASE=$BASE"

rm -rf "$OUT"; mkdir -p "$OUT"; cd "$OUT"
cp $UB/u-boot.bin .
cp $UB/spl/u-boot-spl.bin .

echo "--- u-boot: gzip -> CM byte -> mkimage(uboot head) -> firmware head"
# Stock gzip, NOT the SDK tools/k230_priv_gzip binary.
#
# That binary is a stripped x86-64 ELF we would otherwise have to execute
# to produce bootable firmware. It is GNU gzip with the name filed off --
# FSF copyright, "Written by Jean-loup Gailly.", bug-gzip@gnu.org, and
# the unmodified gzip option table, in which its "-n8" parses as the
# ordinary "-n -8". Verified byte-identical to nixpkgs gzip 1.14 at every
# level the SDK falls back through (8, 9, 7, 6, 5, 4) against this very
# u-boot.bin. See docs/blob-inventory.md.
gzip -n -8 -f -k u-boot.bin
# post-image.sh line 96, inside k230_gzip(). Flips the gzip CM byte from
# 0x08 (deflate, software) to 0x09, which is how SPL is told to use the
# SoC hardware decompressor. Omitting it still boots -- SPL links both
# zunzip and k230_priv_unzip -- but takes a path the vendor does not ship
# or test.
sed -i -e "1s/\x08/\x09/" u-boot.bin.gz
$UB/tools/mkimage -A riscv -C gzip -O u-boot -T firmware -a $BASE -e $BASE -n uboot \
    -d u-boot.bin.gz ug_u-boot.bin
cp ug_u-boot.bin ug_u-boot.bin.t
python3 $UB/tools/firmware_gen_no_securiy.py -i ug_u-boot.bin.t -o fn_ug_u-boot.bin -n

echo "--- spl: firmware head (+ the endian-swapped variant the SDK also makes)"
cp u-boot-spl.bin u-boot-spl.bin.t
python3 $UB/tools/firmware_gen_no_securiy.py -i u-boot-spl.bin.t -o fn_u-boot-spl.bin -n
python3 $UB/tools/endian-swap.py fn_u-boot-spl.bin swap_fn_u-boot-spl.bin

echo "--- env (load addresses that fit a NixOS kernel)"
# The vendor blinux loads Image at 0x200000, the dtb at 0x2200000 and the
# OpenSBI payload at 0x3000000, which assumes a kernel under 32 MiB. Ours
# is ~60 MB and lands on top of both; bootm then reports "Wrong Image
# Format", which reads like a corrupt header and is not. Observed on
# hardware -- see docs/evidence/hardware-boot.txt.
#
# The environment is plain data we generate, not vendor firmware, so move
# the dtb and OpenSBI above the kernel instead of constraining the kernel.
#
# blinux also gains a bootargs.txt load + "env import". Without env
# "bootargs" set, board_fdt_chosen_bootargs() (board/canaan/common/
# k230_img.c:110) substitutes a hardcoded vendor command line chosen by
# g_bootmod and overwrites /chosen/bootargs in our dtb. That line has no
# init=, which drops NixOS stage 1 into emergency mode. The file lives on
# the boot partition rather than in this env image because it names the
# NixOS closure and so changes on every rebuild -- this env must not.
# 0x7000000 is below fw_jump (0x8000000) and above the ~60 MB kernel at
# 0x200000. ${filesize} is set by the ext4load immediately before it.
sed -e "s|blinux=k230_set_dtb \&\& |blinux=k230_set_dtb \&\& ext4load mmc \${mmc_boot_dev_num}:1 0x7000000 /bootargs.txt \&\& env import -t 0x7000000 \${filesize} \&\& |" \
    -e "s|0x3000000 /fw_jump_add_uboot_head.bin|0x8000000 /fw_jump_add_uboot_head.bin|" -e "s|0x2200000 /\${dtb}|0x8400000 /\${dtb}|" -e "s|bootm 0x3000000 - 0x2200000|ext4load mmc \${mmc_boot_dev_num}:1 0x9000000 /initrd.uimg \&\& bootm 0x8000000 0x9000000 0x8400000|" "$ENVF" > tdisplay.env
echo "--- env changes:"; diff "$ENVF" tdisplay.env || true
$UB/tools/mkenvimage -s 0x2000 -o env.env tdisplay.env

rm -f *.t u-boot.bin.gz ug_u-boot.bin
echo "--- RESULT"
ls -la
echo "--- sha256"
sha256sum fn_u-boot-spl.bin fn_ug_u-boot.bin env.env swap_fn_u-boot-spl.bin
cp fn_u-boot-spl.bin fn_ug_u-boot.bin env.env /sdk/../../firmware/stage1/ 2>/dev/null || true
'
# The container wrote into the SDK's output tree; put the five files where
# the vendor override looks for them, next to this text.
OUT="$ROOT/.build/k230_linux_sdk/output/k230_canmv_v3_defconfig/images"
cp "$OUT/uboot/fn_u-boot-spl.bin" "$OUT/uboot/fn_ug_u-boot.bin" "$OUT/uboot/env.env" "$ROOT/firmware/stage1/"
cp "$OUT/fw_jump.bin" "$OUT/fw_jump_add_uboot_head.bin" "$ROOT/firmware/stage1/"
echo "--- firmware/stage1/ (gitignored; the vendor-compiled fallback)"
sha256sum "$ROOT"/firmware/stage1/*.bin "$ROOT"/firmware/stage1/env.env
