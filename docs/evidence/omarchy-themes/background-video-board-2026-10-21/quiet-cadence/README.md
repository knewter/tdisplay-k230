# The quieter 12 ms arm passes the three-card tracking target

The guarded installed-board comparison ran **2026-10-21
16:23:51Z–16:26:15Z**. With file logging held constant, the same tested
compositor and three-card still-background workload ran at **8/12/8 ms**
render allowances. The 12 ms arm passes every frozen numeric metric; both
8 ms arms still fail tracking. This is a promising candidate, not complete
paired static/video acceptance or a permanent default change.

## Results

| Metric | 8 ms before | 12 ms | 8 ms return |
| --- | ---: | ---: | ---: |
| Correlated rendered frames | 204 | 209 | 204 |
| Frame-update CPU p95 | 6.696 ms | 6.726 ms | 6.801 ms |
| Render elapsed p95 | 7.661 ms | 8.195 ms | 6.989 ms |
| Render elapsed maximum | 10.659 ms | 13.932 ms | 11.938 ms |
| Render-start lateness p95 | 0.159 ms | 0.107 ms | 0.119 ms |
| Motion-to-submit p95 | 21.927 ms | 19.616 ms | 20.507 ms |
| Motion-to-present p95 | 30.307 ms | 26.356 ms | 30.837 ms |
| Frozen tracking interval p95 | **38.323 ms FAIL** | **19.170 ms PASS** | **38.321 ms FAIL** |
| Frozen tracking interval maximum | 57.484 ms | 38.333 ms | 38.325 ms |
| Above-33.334 ms tracking intervals | 17 / 198 | 8 / 203 | 12 / 198 |
| Above-target intervals containing another actual presentation | 10 | 7 | 6 |
| All-present interval p95 during motion | 19.188 ms | 19.164 ms | 19.168 ms |
| Actual two-vblank intervals during motion | 8 / 196 | 1 / 203 | 6 / 204 |
| Global journal-service mean active CPU, cores | 0.000919 | 0.000982 | 0.001100 |

The unchanged frozen tracking target is **33.334 ms p95 / 100 ms maximum**.
All numeric CPU/input/release/session-memory checks pass in the 12 ms arm,
with zero excluded input pauses. Other numeric metrics also pass in both
8 ms arms; tracking is their remaining numeric failure. Every correlated
frame has one render attempt. The original logs and full parser results
remain in [budget-analysis.json](budget-analysis.json) and
[quiet-analysis.json](quiet-analysis.json).

This does not show a faster renderer at 12 ms: its elapsed p95 is higher
than either 8 ms arm. The observation supports allowing more time before
the presentation deadline once the large journal observer cost is removed.
It does not prove a scheduler/kernel cause or a causal improvement beyond
this one sequence. The 13.932 ms maximum also exceeds 12 ms; this is not
proof that every render meets its allowance. Backend feedback is not optical
visibility, and all-present intervals never replace the frozen metric.

The [earlier journal-logged 8/12/8 comparison](../tracking-cadence/README.md)
and its failed/input-stalled arms remain valid observations under that
different observer load. The [logging comparison](../log-destination/README.md)
then measured that load. Here every arm writes stderr to its own file,
formats/emits the same telemetry, and restarts the session before setup.
Order/cache/observer effects remain; no outcome was selected by dropping a run.

The next gate is a complete paired still/video, one/multiple-card workload
at the candidate setting, including the existing cover/reduced-motion and
restoration requirements. These three-card still-only reports retain their
portrait-geometry and missing one-card-companion warnings. Task 3.3 and
archive 4.2 remain unchecked; the normal board remains at 8 ms and video
remains disabled by default.

## Exact source and method

[descriptor.json](descriptor.json), [result.json](result.json), and
[quiet-cadence-staged-sha256.json](quiet-cadence-staged-sha256.json) record
source `7b318de0cf4785799498d615d571c67cfff94e17`, all five staged inputs,
and installed identities. The reused compositor is
`/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`,
actual ELF SHA256
`2778ed3cdac48b83806117a8d96accba0163dae21ba12b7a1104f1c1289fa3be`.
Its build source is `1a8e72ac52df5c80540bdeedc22edfcc4e5c167a`; Nix/runtime
inputs are unchanged through `7b318de0`. The prior
[build receipt](../tracking-elapsed/build-receipt.json) applies. There is no
new build, full system image, ordinary-boot claim, or Nix/default change.

The workload stays at six alternating 35-motion, 700 ms native-uinput drags,
three Foot cards, original still theme, 1232×568 logical landscape, and the
same selected app. File logging and journal-service sampling are identical
in all arms. Normalized telemetry is unchanged; the separate global journal
CPU samples are not added to frozen shell/shell-ui session resources.

[run-board.py](run-board.py) is staged as `run.py`, with
[collect-board.py](collect-board.py) as `collect.py`,
[cadence_audit.py](cadence_audit.py), the descriptor, and the tested revision's
`card-shell-board-session.py` normalizer. With the exclusive SSH board
reservation, the command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/quiet-cadence-20261021/run.py
```

An independent 480-second root timer arms before the temporary service
override. The controller refuses unexpected apps, identities, occupied
output/recovery directories, or existing overrides. Each arm restarts the
candidate, applies `output DSI-1 max_render_time <8-or-12>`, and checks the
resulting output identity before and after collection. Collector metadata
independently records 8/12/8. FD 2 must match the owned regular log file by
device/inode. Other logging properties stay unchanged. Future replication
requires new owned staging/output/recovery paths and a unique timer.

[private-source-receipt.json](private-source-receipt.json) verifies all three
private log prefix hashes separately from final shutdown-appended files.
Raw stderr and native screenshots remain protected outside Git. No camera,
real-finger, or optical acceptance is claimed by this injected-input probe.

[final-audit.json](final-audit.json) independently verifies original `2ig`
system/profile, normal compositor `4fc7bf3a…`, same boot, still generation,
landscape, original 8 ms allowance, journal routing/socket, active normal
services, zero injected devices, absent owned override, and inactive restore
timer. The board reservation was released after audit/export. Boot files,
system profile, priorities, preferences, and persistent defaults are unchanged.

## Replay and validation

```sh
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination/test-log-destination-analyze.py
python3 -m unittest tests.test_card_shell_board_tools
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/quiet-cadence/quiet-cadence-analyze.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/quiet-cadence --repo .
openspec validate --all --strict
python3 tools/blob-scan.py --no-vendor
```

The analyzer imports the previously tested CPU-window helper and unchanged
frozen/elapsed/cadence parsers. Its board replay checks 8/12/8 controller and
collector observations, file FD routing receipts, all six gestures, normalizer
idempotence, timing/frame uniqueness, single attempts, CPU counter/window
validity, restoration, and equality of diagnostic/frozen tracking count/p95.
The five CPU-window tests and 30 board-tool tests pass. Host tests validate
analysis and normalization; board records supply the timing evidence.
