# Read-only live card layout before CPU0 identity trial

The board operator held `/dev/ttyACM0`; the protected host capture file's
mtime is 2026-09-27T04:04:42Z (a host timestamp, not a board-clock read).
The command used only `findmnt`, `/proc/partitions`, and
`/sys/block/mmcblk*/{size,device/name}`. The operator supplied the
sanitized output in `/tmp/k230-smp-card-layout.txt`; the raw console
session remains outside the repository. No card or MMIO write occurred.

```text
findmnt -no SOURCE /boot
/dev/mmcblk1p1

cat /proc/partitions
major minor  #blocks  name
 179        0  124936192 mmcblk1
 179        1     114688 mmcblk1p1
 179        2  124805103 mmcblk1p2

/sys/block/mmcblk1/size
249872384
/sys/block/mmcblk1/device/name
SD128
```

The whole live card has 249872384 512-byte sectors. This identifies the
board's running `mmcblk1` only; a removable reader may assign a different
device name. The external reader's by-id path, model/serial comparison,
unmounted state, raw-slot backup hashes, and restore capability are still
unverified. They remain required before the experimental SPL is written.
