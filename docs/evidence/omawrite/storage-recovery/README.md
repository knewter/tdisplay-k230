# Storage failure after Omawrite installation

A later user report said Omawrite would not launch and application icons were missing.
The reserved physical serial console confirmed repeated SD read failures and a
read-only root filesystem. Bash and systemctl could not load from the Nix store.
This supersedes any assumption that the earlier passing trial describes the
current board state; the earlier trial remains a historical observation.

- [Filtered storage errors](storage-errors.txt)
- [Diagnosis and recovery status](diagnosis.json)

## Procedure and limits

The coordinator held `/tmp/k230-board.lock` and used `tools/console.py` on
`/dev/ttyACM0` at 115200. Ordinary external diagnostic commands failed, so the
existing console shell read `/proc/mounts` and `/dev/kmsg` with Bash builtins.
Only storage-related lines were retained above; protected raw captures remain
outside the repository. The filter omits identifiers and unrelated messages.

A normal `systemctl reboot` failed with an input/output error. The running
kernel did not provide `/proc/sysrq-trigger`, so sync/remount/reboot requests
through that interface had no effect. A physical power cycle was requested.
During that diagnosis, no filesystem repair, remount-write, image flash or
full-card readback was performed. The reason the SD stopped responding remains
undetermined; these observations do not distinguish a card, power, connection
or driver problem.

## Replacement card and preserved demo image

Power cycling and reseating did not restore boot output. The original card then
reported zero capacity through the USB reader, which could not read its medium.
A different card reported 64,088,965,120 bytes through the same reader. Its first
two FAT partitions contained readable vendor/demo files; its third FAT partition
reported an invalid cluster and was made read-only by Linux. These are separate
cards and separate failure observations.

The user authorized preserving the replacement demo card before replacing it
with our current NixOS image. All three partitions were unmounted first. The
[exact backup command](backup-demo-card.py) read every source byte without errors,
fsynced the saved image, then independently reread and hashed the saved file.
The [result](demo-backup-result.json) records matching SHA-256 and byte counts.
The full private image, checksum, source identity and restoration notes are at
`~/tmp/k230-demo-card-20260927T203725Z/`. Only reviewed metadata is committed here.
The backup preserves existing filesystem corruption; it is not a repaired image.

The [F3 capacity probe](capacity-probe.txt) passed: usable and announced sizes
both equal 125,173,760 sectors. It restored its sampled blocks; independent
samples at the beginning, middle and end then matched the verified backup.
The [probe result](capacity-probe-result.json) preserves the exact command and
completion time. This checks capacity, not every possible future failure.

## Replacement NixOS image written

The `sdImage-coherent` build completed successfully from source revision
`c985854979325057727a825294d8a0d34b26a4f1`. Changes after runtime revision
`4db47bc0117378efa120c17679a1cea8d506949e` were evidence/documentation only.
The build command was:

```sh
nix build .#sdImage-coherent --out-link result-sd-image-coherent \
  --max-jobs 4 --cores 6 \
  --option substituters https://cache.nixos.org/ --print-out-paths
```

The output is `/nix/store/ijdsbmb6mzhlsbr32yyqpzzpq0pz7rxa-k230-sd-image.img`,
4,765,401,088 bytes, SHA-256
`86bf43dd943a6208a0b253318b7fa8344defef33ac3e0236275777be2471fdd1`.
It contains system
`/nix/store/cmhsqwvzwp3bad15wv5znk4w35wx65d5-nixos-system-nixos-26.11.20260919.20b1ddd`.
A host inspection confirmed that system's `init`, Omawrite desktop entry and
profile icon exist; the entry references the expected absolute Omawrite path.
This is packaging evidence, not a successful launch on the replacement card.

The [preflight](replacement-preflight.py) checked the approved removable USB
slot, capacity, unmounted state, image partition layout and samples matching
the preserved demo backup. The [writer](flash-replacement.py) saved a separate
`nixos-replacement.img` beside `demo-card.img`, fsynced it and verified its hash
before invoking the repository's `tools/flash.sh` with the approved by-id path.
Both image hashes are in the private directory's `SHA256SUMS`.

The [flash result](flash-result.json) and [write completion](flash-write.txt)
record exit zero, the complete byte count and completion at
2026-09-27T22:59:46Z. `dd oflag=sync conv=fsync` and the writer's final `sync`
completed. The reader was then powered off successfully with `udisksctl`.
No routine full-image readback was performed, per the user's standing request.

**UNVERIFIED on this replacement card:** boot, writable root filesystem,
launcher icons and actual Omawrite launch. The operator must move the card into
the powered-off board, reconnect power, then use the reserved serial console
(`python3 tools/console.py /dev/ttyACM0 --wait=8 "readlink /run/current-system"`)
to check the system identity before the remaining runtime checks. No new
application or shell source change was made during this recovery.
