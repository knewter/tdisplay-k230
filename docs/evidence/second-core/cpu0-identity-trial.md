# CPU0 SPL identity trial — prepared, not run

This is a bounded diagnostic for the Linux SMP plan, **not** a second-core
application. It reads physical CPU0's `mhartid` and `misa` in the existing
SPL handoff before CPU1 is released; afterward stage 1 boots physical CPU1
as usual and CPU0 parks. The trial has not been installed or run on the
board. The coordinator owns the board and `/dev/ttyACM0` throughout.

Candidate built on 2026-09-26 from pinned U-Boot SDK revision
`1104236db4d1e47873bd68924f912747b820228c`:

```text
nix build .#stage1-cpu0-identity-probe --no-link --print-out-paths --max-jobs 1 --cores 4
  /nix/store/6y6v6vyg37r04jjj5057j8yfisxayf69-k230-stage1-packaging
candidate fn_u-boot-spl.bin: 223412 bytes
  SHA256 a4c1ae6a038bb3e7326b375f15431c498db5c185dd192cdb4391bd3b265d1cc9
candidate fn_ug_u-boot.bin: 385932 bytes
  SHA256 e0b5787f3e68267f997ca61d45afaf8945e6fe9be775cc6165f981978cf3f1bb
normal fn_ug_u-boot.bin: same SHA256 and `cmp` exit 0
normal .#uboot-k230 derivation: /nix/store/kac0dycgcny0m9yapbhmdydyhps6a75q-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10.drv
normal .#stage1-packaging derivation: /nix/store/v4dk5d7wssq0rjsvzv6rqcmvsdfrmqpk-k230-stage1-packaging.drv
probe .#stage1-cpu0-identity-probe derivation: /nix/store/16in71n35zplf9rkdcydhjv0686w6pkz-k230-stage1-packaging.drv
wrapper first four bytes: 4b 32 33 30 (ASCII K230)
```

The SPL wrapper begins with the K230 firmware magic, built by the existing
`nix/stage1.nix` packaging. Its 223412 bytes fit in either 512 KiB raw SPL
slot; the underlying SPL binary is 222880 bytes against the 524288-byte
`CONFIG_SPL_SIZE_LIMIT`. The trial package differs from normal stage 1
only in `fn_u-boot-spl.bin`; do **not** write `fn_ug_u-boot.bin`, env, DT,
OpenSBI, kernel or rootfs. `nix/stage1.nix:176-180` gives the two SPL offsets
as 1048576 and 1572864 bytes (1 MiB and 1.5 MiB).

## Operator sequence after board/card handoff

Use an external SD-card reader; U-Boot `ums` cannot recover an SPL that
prevents U-Boot from starting. Record the current card's full by-id path,
sector count, model, and serial before removal, and confirm the same device
in the reader. Preserve the current known-good boot state and external
power/serial arrangement. Substitute only the confirmed card path and its
known sector count below; stop if either identity or size differs, if any
partition is mounted, or if the backup/readback hashes differ. The card
reader is a recovery route even when no second physical card is available.

```sh
set -euo pipefail
card=/dev/disk/by-id/REPLACE_WITH_CONFIRMED_WHOLE_CARD
expected_sectors=REPLACE_WITH_CONFIRMED_SECTOR_COUNT
candidate=/nix/store/6y6v6vyg37r04jjj5057j8yfisxayf69-k230-stage1-packaging/fn_u-boot-spl.bin
test -b "$card"
test "$(lsblk -dnro TYPE "$card")" = disk
test "$(sudo blockdev --getsz "$card")" -eq "$expected_sectors"
test -z "$(lsblk -nrpo MOUNTPOINTS "$card" | tr -d '[:space:]')"
test "$(sha256sum "$candidate" | cut -d' ' -f1)" = a4c1ae6a038bb3e7326b375f15431c498db5c185dd192cdb4391bd3b265d1cc9
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,MOUNTPOINTS "$card"
sudo dd if="$card" of=cpu0-trial-original-slot-a.bin bs=512K skip=2 count=1 status=none
sudo dd if="$card" of=cpu0-trial-original-slot-b.bin bs=512K skip=3 count=1 status=none
sha256sum cpu0-trial-original-slot-a.bin cpu0-trial-original-slot-b.bin
sha256sum cpu0-trial-original-slot-a.bin cpu0-trial-original-slot-b.bin > cpu0-trial-original-SHA256SUMS
dd if="$candidate" of=cpu0-trial-slot.bin bs=512K conv=sync status=none
test "$(stat -c %s cpu0-trial-slot.bin)" -eq 524288
sha256sum cpu0-trial-slot.bin
```

Keep the two backed-up slot files and their recorded hashes outside the
card being changed. Confirm that they can be read before writing. Then,
with the operator still holding the board session, write **only** the two
SPL slots and read them back before booting:

```sh
set -euo pipefail
test -z "$(lsblk -nrpo MOUNTPOINTS "$card" | tr -d '[:space:]')"
sha256sum -c cpu0-trial-original-SHA256SUMS
sudo dd if=cpu0-trial-slot.bin of="$card" bs=512K seek=2 count=1 conv=notrunc,fsync status=progress
sudo dd if=cpu0-trial-slot.bin of="$card" bs=512K seek=3 count=1 conv=notrunc,fsync status=progress
sudo dd if="$card" of=cpu0-trial-readback-a.bin bs=512K skip=2 count=1 status=none
sudo dd if="$card" of=cpu0-trial-readback-b.bin bs=512K skip=3 count=1 status=none
cmp cpu0-trial-slot.bin cpu0-trial-readback-a.bin
cmp cpu0-trial-slot.bin cpu0-trial-readback-b.bin
```

Only after both comparisons pass, reinsert and boot while the operator
captures the entire early serial log. Acceptance for this *diagnostic*
is one `CPU0_SPL_IDENTITY mhartid=... misa=...` line, then the existing
CPU1 OpenSBI banner and normal one-CPU Linux boot. Missing marker, a hang,
or another boot difference is a failed trial and triggers restoration; it
is not a Linux SMP success. A CPU1 M-mode CSR measurement may still be
needed because OpenSBI's boot-HART ID is the firmware's logical ID.

Restore the original two 512 KiB slots through the external reader, with
the **same** verified card identity and sector count, after the capture
regardless of outcome. Then read back and compare the exact original bytes:

```sh
set -euo pipefail
test -b "$card"
test "$(lsblk -dnro TYPE "$card")" = disk
test "$(sudo blockdev --getsz "$card")" -eq "$expected_sectors"
test -z "$(lsblk -nrpo MOUNTPOINTS "$card" | tr -d '[:space:]')"
sha256sum -c cpu0-trial-original-SHA256SUMS
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,MOUNTPOINTS "$card"
sudo dd if=cpu0-trial-original-slot-a.bin of="$card" bs=512K seek=2 count=1 conv=notrunc,fsync status=progress
sudo dd if=cpu0-trial-original-slot-b.bin of="$card" bs=512K seek=3 count=1 conv=notrunc,fsync status=progress
sudo dd if="$card" of=cpu0-trial-restored-a.bin bs=512K skip=2 count=1 status=none
sudo dd if="$card" of=cpu0-trial-restored-b.bin bs=512K skip=3 count=1 status=none
cmp cpu0-trial-original-slot-a.bin cpu0-trial-restored-a.bin
cmp cpu0-trial-original-slot-b.bin cpu0-trial-restored-b.bin
```

Record UTC timestamps, current system/store path, both slot hashes before
and after, full serial output with secrets redacted, and the result in a
separate physical evidence file. The trial establishes CPU0's sampled CSR
values only. It does not establish a usable unique SBI hart ID, PLIC/ACLINT
routing, cross-core cache coherency, or two-CPU Linux scheduling.
