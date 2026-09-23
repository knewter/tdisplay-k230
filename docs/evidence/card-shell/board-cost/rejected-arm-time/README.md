# Rejected cost run: arm time is not deck entry

The next physical-board run used
`/nix/store/l4klcf00vsfcjh1yddg7inq1jr02nywd-k230-card-shell`, source `11ffecb`,
with the same native input-event harness and one/two-client workloads as the
accepted interaction trial. All thirteen interaction checks were observed again
(`interaction-checks.json`). The normal shell restored, and an independent
16:22:08 UTC control regression passed. No image flash occurred.

The unchanged benchmark parser rejected `telemetry.log` with exit 2:
**memory baseline follows deck entry**. `manifest.json` identifies the exact
package, source and collection time. These cost inputs are retained unmodified;
`parser-error.txt` records the command. This directory has no accepted cost
report and does not claim a new screenshot review. Earlier reviewed same-workload
interaction captures remain in `../../injected/`.

The first timestamp correction used benchmark-arm time as session entry. That
fixed inputs preceding the header, but incorrectly placed the real baseline
sampling interval after the reported deck-entry time. The producer now marks
whether it is inside a native input handler. Native entry uses that handler's
input-start timestamp; IPC entry uses current monotonic time. An earlier,
completed input cannot supply a stale entry timestamp. Baseline samples remain
before entry, and the entering input has nonnegative latency.

The regression test compiles the actual producer, runs native entry, direct IPC
entry and IPC entry after an unconsumed input, then sends each output through
the actual cost parser. All three cases passed. All eighteen existing parser
tests passed without changing its guards or budget thresholds. The corrected
cross-build passed:
`/nix/store/qh2jzzn4p5dgryfrwihimc7lad98rldl-k230-card-shell`.
The new board cost repeat remains pending at this source checkpoint.
