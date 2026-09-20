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

echo "--- u-boot: k230_priv_gzip -> mkimage(uboot head) -> firmware head"
$SDK/tools/k230_priv_gzip -n8 -f -k u-boot.bin
$UB/tools/mkimage -A riscv -C gzip -O u-boot -T firmware -a $BASE -e $BASE -n uboot \
    -d u-boot.bin.gz ug_u-boot.bin
cp ug_u-boot.bin ug_u-boot.bin.t
python3 $UB/tools/firmware_gen_no_securiy.py -i ug_u-boot.bin.t -o fn_ug_u-boot.bin -n

echo "--- spl: firmware head (+ the endian-swapped variant the SDK also makes)"
cp u-boot-spl.bin u-boot-spl.bin.t
python3 $UB/tools/firmware_gen_no_securiy.py -i u-boot-spl.bin.t -o fn_u-boot-spl.bin -n
python3 $UB/tools/endian-swap.py fn_u-boot-spl.bin swap_fn_u-boot-spl.bin

echo "--- env"
$UB/tools/mkenvimage -s 0x2000 -o env.env "$ENVF"

rm -f *.t u-boot.bin.gz ug_u-boot.bin
echo "--- RESULT"
ls -la
echo "--- sha256"
sha256sum fn_u-boot-spl.bin fn_ug_u-boot.bin env.env swap_fn_u-boot-spl.bin
'
