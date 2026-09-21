#!/usr/bin/env bash
# Reproduce the SDK's gen_uboot_bin() and env generation to produce exactly
# the four files genimage.cfg places on the card. Run in the SDK container so
# the toolchain and the x86-64 helper binaries resolve.
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
sed -e "s|0x3000000 /fw_jump_add_uboot_head.bin|0x8000000 /fw_jump_add_uboot_head.bin|" -e "s|0x2200000 /\${dtb}|0x8400000 /\${dtb}|" -e "s|bootm 0x3000000 - 0x2200000|bootm 0x8000000 - 0x8400000|" "$ENVF" > tdisplay.env
echo "--- env changes:"; diff "$ENVF" tdisplay.env || true
$UB/tools/mkenvimage -s 0x2000 -o env.env tdisplay.env

rm -f *.t u-boot.bin.gz ug_u-boot.bin
echo "--- RESULT"
ls -la
echo "--- sha256"
sha256sum fn_u-boot-spl.bin fn_ug_u-boot.bin env.env swap_fn_u-boot-spl.bin
'
