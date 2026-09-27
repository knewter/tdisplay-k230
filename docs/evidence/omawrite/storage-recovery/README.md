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
No filesystem repair, remount-write, image flash or full-card readback was
performed. The reason the SD stopped responding remains undetermined; these
observations do not distinguish a card, power, connection or driver problem.

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

A capacity probe and the current `sdImage-coherent` build are in progress.
No replacement image has been flashed yet. Actual boot, launcher and icon
behavior still require checking on the replacement card. No new application or
shell source change is justified by the available evidence.
