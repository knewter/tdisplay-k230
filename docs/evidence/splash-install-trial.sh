#!/usr/bin/env bash
# Narrow hardware trial on the identified running card; not a full-image flash.
set -euo pipefail
card=/dev/mmcblk1
candidate=/tmp/k230-splash-uboot.bin
backup=/root/k230-before-splash-uboot-slot.bin
dtb_backup=/root/k230-before-splash.dtb
old_slot=6554c22886286c8f4af2417c42007dacf46011a5c7f60b10e29c9f281b33eeb7
new_slot=f0c68fed7a6eec61576f8c8f7586a80b1aa4cf5326a56057ae12d8859110edfe
old_dtb=e0ff2bc8cf516d278a70215aff26ca3a4799baaeb28e5c0b3a9f124d660fb138
hash() { sha256sum "$1" | cut -d' ' -f1; }
slot_hash() { dd if="$card" bs=512 skip=4096 count=2048 iflag=direct status=none | sha256sum | cut -d' ' -f1; }
[ "$(findmnt -n -o SOURCE /)" = /dev/mmcblk1p2 ]
[ "$(findmnt -n -o SOURCE /boot)" = /dev/mmcblk1p1 ]
[ "$(cat /sys/class/block/mmcblk1/size)" = 249872384 ]
[ "$(stat -c %s "$candidate")" = 385766 ]
[ "$(hash "$candidate")" = fc59edb7057bd3ec7b6cda045bbad1545fb31a7bc19ade6cd8e7063e19f76d16 ]
[ "$(hash /tmp/k230-splash-logo.xrgb)" = 6c7a36086297597b359657ab53925ee0725e5201461484d543cbd950f5baa3af ]
[ "$(hash /tmp/k230-splash.dtb)" = ea95214b4bb8760f0de35c7d4126d0c98b2f9355284f7cae54812febdeb4fdb7 ]
[ "$(hash /boot/k230-tdisplay.dtb)" = "$old_dtb" ]
[ "$(slot_hash)" = "$old_slot" ]
for f in "$backup" "$dtb_backup" /boot/logo.xrgb /boot/logo.xrgb.splash-trial /boot/k230-tdisplay.dtb.splash-trial; do
    [ ! -e "$f" ] && [ ! -L "$f" ]
done
umask 077
dd if="$card" of="$backup" bs=512 skip=4096 count=2048 iflag=direct conv=fsync status=none
cp /boot/k230-tdisplay.dtb "$dtb_backup"
sync
[ "$(hash "$backup")" = "$old_slot" ]
[ "$(hash "$dtb_backup")" = "$old_dtb" ]
echo 'GUARDS PASS: identified root/boot card, full previous slot and all inputs; backups verified'
rollback() {
    trap - ERR
    echo 'INSTALL FAILED: restoring boot DTB and U-Boot slot before reboot'
    cp "$dtb_backup" /boot/k230-tdisplay.dtb
    rm -f /boot/logo.xrgb /boot/logo.xrgb.splash-trial /boot/k230-tdisplay.dtb.splash-trial
    dd if="$backup" of="$card" bs=512 seek=4096 conv=notrunc,fsync status=none
    sync
    if [ "$(slot_hash)" = "$old_slot" ] && [ "$(hash /boot/k230-tdisplay.dtb)" = "$old_dtb" ]; then
        echo 'ROLLBACK VERIFIED'
    else
        echo 'ROLLBACK FAILED; DO NOT REBOOT'
    fi
    exit 1
}
trap rollback ERR
cp /tmp/k230-splash.dtb /boot/k230-tdisplay.dtb.splash-trial
cp /tmp/k230-splash-logo.xrgb /boot/logo.xrgb.splash-trial
chmod 644 /boot/k230-tdisplay.dtb.splash-trial /boot/logo.xrgb.splash-trial
sync
mv /boot/k230-tdisplay.dtb.splash-trial /boot/k230-tdisplay.dtb
mv /boot/logo.xrgb.splash-trial /boot/logo.xrgb
# The verified previous slot has a zero tail and this candidate is larger.
dd if="$candidate" of="$card" bs=512 seek=4096 conv=notrunc,fsync status=none
sync
[ "$(slot_hash)" = "$new_slot" ]
[ "$(hash /boot/k230-tdisplay.dtb)" = ea95214b4bb8760f0de35c7d4126d0c98b2f9355284f7cae54812febdeb4fdb7 ]
[ "$(hash /boot/logo.xrgb)" = 6c7a36086297597b359657ab53925ee0725e5201461484d543cbd950f5baa3af ]
trap - ERR
echo "INSTALL VERIFIED: full U-Boot slot $new_slot, DTB and logo readback; no reboot issued"
