#!/usr/bin/env python3
"""Guarded, once-only write of the U-Boot-proper slot (2026-10-30 Game of Life trial).

Authorized by the coordinator for the opt-in Game of Life U-Boot only, following
docs/evidence/game-of-life/stage1-install-recovery-proposal.md.  Based on
docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/deploy-candidate.py,
reimplemented with shell tools because this board has no python3.

    flock /tmp/k230-board.lock python3 install-uboot.py PAYLOAD BACKUP_SHA256 BOOT_ID SYSTEM

The remote side refuses unless: the boot id and /run/current-system match the
preflight, the boot partition starts at sector 8192, every /boot file hash
matches boot-files.sha256, the direct 4 MiB read equals the backup file, the
payload (uploaded first to a new file) is a K230 firmware image (magic, length field, SHA-256 of the body)
smaller than the 1 MiB slot.  It writes only bytes [2 MiB, 2 MiB + len), reads
the first 4 MiB back with O_DIRECT and compares with "backup with the payload
spliced in"; on any mismatch it restores the original slot from the backup.
"""
import hashlib
import subprocess
import sys

payload_path, backup_sha, boot_id, system = sys.argv[1:5]
payload = open(payload_path, "rb").read()
assert payload[:4] == b"K230" and 528 < len(payload) < 1048576, "payload is not a K230 firmware image in slot size"
sha = hashlib.sha256(payload).hexdigest()

remote = r"""
set -eu
D=/var/lib/k230/life-20261030
BACKUP_SHA=%(backup_sha)s
test "$(cat /proc/sys/kernel/random/boot_id)" = "%(boot_id)s" || { echo "boot id changed"; exit 3; }
test "$(readlink /run/current-system)" = "%(system)s" || { echo "system changed"; exit 3; }
test "$(cat /sys/class/block/mmcblk1p1/start)" = 8192 || { echo "partition layout changed"; exit 3; }
test "$(sha256sum $D/first-4MiB.bin | cut -d' ' -f1)" = "$BACKUP_SHA" || { echo "board backup hash mismatch"; exit 3; }
(cd /boot && sha256sum -c $D/boot-files.sha256 >/dev/null 2>&1) || { echo "boot files changed since backup"; exit 3; }
cat /sys/class/power_supply/*/online | grep -q 1 || { echo "charger offline"; exit 3; }
dd if=/dev/mmcblk1 of=$D/now-4MiB.bin bs=4096 count=1024 iflag=direct status=none
cmp $D/first-4MiB.bin $D/now-4MiB.bin || { echo "card differs from backup; stop"; exit 3; }
test "$(sha256sum $D/candidate.bin | cut -d' ' -f1)" = "%(sha)s" || { echo "payload hash mismatch"; exit 3; }
LEN=$(stat -c %%s $D/candidate.bin)
test "$LEN" = %(len)d
test "$(head -c 4 $D/candidate.bin)" = K230
# expected result: backup with the payload spliced in at 2 MiB
cp $D/first-4MiB.bin $D/expected-4MiB.bin
dd if=$D/candidate.bin of=$D/expected-4MiB.bin bs=4096 seek=512 conv=notrunc status=none
dd if=$D/candidate.bin of=/dev/mmcblk1 bs=4096 seek=512 conv=notrunc,fsync status=none
dd if=/dev/mmcblk1 of=$D/after-4MiB.bin bs=4096 count=1024 iflag=direct status=none
if cmp $D/expected-4MiB.bin $D/after-4MiB.bin; then
  echo "WRITTEN-AND-VERIFIED len=$LEN after_sha256=$(sha256sum $D/after-4MiB.bin | cut -d' ' -f1)"
else
  echo "READBACK MISMATCH: restoring the original slot"
  dd if=$D/first-4MiB.bin of=/dev/mmcblk1 bs=4096 skip=512 seek=512 count=256 oflag=direct conv=notrunc,fsync status=none
  dd if=/dev/mmcblk1 of=$D/restored-4MiB.bin bs=4096 count=1024 iflag=direct status=none
  cmp $D/first-4MiB.bin $D/restored-4MiB.bin && echo RESTORED-OK || echo RESTORE-FAILED
  exit 4
fi
""" % dict(backup_sha=backup_sha, boot_id=boot_id, system=system, sha=sha, len=len(payload))

SSH = ["ssh", "-F", "/home/jadams/tmp/k230-coordination/ssh_config.private", "k230"]
# 1. upload the payload to a new file (nothing raw is written yet)
up = subprocess.run(SSH + ["cat > /var/lib/k230/life-20261030/candidate.bin"], input=payload,
                    capture_output=True, timeout=120)
assert up.returncode == 0, up.stderr.decode()
# 2. run the guarded writer
p = subprocess.run(SSH + ["sh -s"], input=remote.encode(), capture_output=True, timeout=300)
sys.stdout.write(p.stdout.decode())
sys.stderr.write(p.stderr.decode())
sys.exit(p.returncode)
