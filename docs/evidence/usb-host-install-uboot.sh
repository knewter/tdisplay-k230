#!/usr/bin/env bash
# One physical-board experiment, run from Linux on the already identified card.
# The verified portrait image remains the host-side recovery artifact.
set -euo pipefail
card=/dev/mmcblk1
candidate=/tmp/k230-host-uboot.bin
backup=/root/k230-before-usb-host-uboot-slot.bin
old_slot=f8b0718c7ea2a290d8663aec44d9d4df766fe2a656d87be59de7e9db56428fd1
new_file=84241c45dce5d5531240db044005eebfbed0d467fd6eb8026c3b822167b84c0a
new_slot=ce6ed38e9c771b148b1481021f996d98e27aa418bf480d030afa24c5969e1e29
slot_hash() { dd if="$card" bs=512 skip=4096 count=2048 iflag=direct status=none | sha256sum | cut -d' ' -f1; }
[ "$(findmnt -n -o SOURCE /)" = /dev/mmcblk1p2 ]
[ "$(cat /sys/class/block/mmcblk1/size)" = 249872384 ]
[ "$(stat -c %s "$candidate")" = 380844 ]
[ "$(sha256sum "$candidate" | cut -d' ' -f1)" = "$new_file" ]
[ "$(slot_hash)" = "$old_slot" ]
[ ! -e "$backup" ] && [ ! -L "$backup" ]
umask 077
dd if="$card" of="$backup" bs=512 skip=4096 count=2048 iflag=direct conv=fsync status=none
[ "$(sha256sum "$backup" | cut -d' ' -f1)" = "$old_slot" ]
echo "GUARDS PASS: root card identity, capacity, candidate length/hash, complete old slot hash; backup saved"
rollback() {
    trap - ERR
    echo "INSTALL FAILED: restoring the complete saved U-Boot slot before any reboot"
    if ! dd if="$backup" of="$card" bs=512 seek=4096 conv=notrunc,fsync status=none; then
        echo "ROLLBACK WRITE FAILED; DO NOT REBOOT"
        exit 1
    fi
    [ "$(slot_hash)" = "$old_slot" ] && echo "ROLLBACK VERIFIED" || echo "ROLLBACK FAILED; DO NOT REBOOT"
    exit 1
}
trap rollback ERR
# Exact-length overwrite; the verified previous slot's remaining bytes are zero.
dd if="$candidate" of="$card" bs=512 seek=4096 conv=notrunc,fsync status=none
actual=$(slot_hash)
echo "Readback full 1 MiB slot SHA256: $actual"
[ "$actual" = "$new_slot" ]
trap - ERR
echo "INSTALL VERIFIED: only U-Boot at 2 MiB changed; no reboot issued"
