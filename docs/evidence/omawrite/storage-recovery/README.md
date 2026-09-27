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

Recovery and actual launcher/icon behavior still require checking after power
returns. No new application or shell source change is justified by this evidence.
