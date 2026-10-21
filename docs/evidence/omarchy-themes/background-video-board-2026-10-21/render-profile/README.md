# Runnable wait overlaps the slow render windows

The reserved-board probe ran **2026-10-21 15:20:09Z–15:22:41Z**, after the
operator saved/closed Omawrite. It reused the tested benchmark compositor
from the [elapsed probe](../tracking-elapsed/README.md), with the original
still background, landscape output, and unchanged 8 ms render allowance.
Three Foot cards received six persistent native-uinput drags in each arm.
This is an injected-input timing diagnostic, not real-finger or optical proof.

## Findings

| Metric | Untraced | Traced | Untraced return |
| --- | ---: | ---: | ---: |
| Input-correlated rendered frames | 190 | 202 | 201 |
| Frame-update CPU p95 | 7.776 ms | 7.836 ms | 7.532 ms |
| Render elapsed p95 | 10.056 ms | 9.588 ms | 9.079 ms |
| Precommit elapsed p95 | 9.578 ms | 8.971 ms | 8.290 ms |
| Commit-return elapsed p95 | 0.960 ms | 0.812 ms | 0.803 ms |
| Render-start lateness p95 | 0.335 ms | 0.401 ms | 0.341 ms |
| Frozen tracking interval p95 | 38.321 ms | 38.320 ms | 38.321 ms |

The traced arm contains **111,183** qualified numeric kernel records with no
overrun, commit overrun, or dropped events. All 202 correlated renders have
one render attempt. Their main-thread off-CPU time is entirely runnable wait:
p50 **0.851 ms**, p95 **2.835 ms**, maximum **8.064 ms**. Observed blocked
and unknown off-CPU partitions are zero within these render windows. This
does not claim that the compositor never sleeps outside rendering.

Most descheduled time occurs before the commit call: precommit off-CPU p95
is **2.795 ms**, versus **0.548 ms** during commit. These percentiles are
separate distributions and must not be added. Twenty-four traced renders
exceed 8 ms. Subtracting their measured off-CPU intervals leaves every render
below 8 ms, with p95 **6.759 ms** and maximum **7.330 ms**. This subtraction
describes the capture; it is not a prediction of performance under another
scheduling policy. The remainder includes interrupts and kernel execution,
and is not a CPU charge. Process CPU also includes another compositor thread;
the scheduler trace targets only the main thread.

The task first scheduled after a render-window switch-out is labelled
`systemd-journald.service` for **112.189 ms** of aggregate overlapping wait,
`kernel-worker` for **44.999 ms**, and other/exited tasks for **57.016 ms**.
Smaller categories and exact values remain in [profile-analysis.json](profile-analysis.json).
Target-filtered switches do not capture intervening scheduling among unrelated
tasks: these numbers are **not their CPU time or causal ownership** of the
whole wait. The trace supports a scheduling-contention investigation and a
controlled check of benchmark logging overhead; it does not justify a
journald priority change, compositor priority change, or kernel patch.

There are 1,395 render-overlapping `write` calls to FD 2, independently labelled
`journal-stream`, with **43.684 ms** total syscall wall overlap. The principal
DRM ioctl group has **32.376 ms** across 202 calls. Syscall wall intervals
include any off-CPU time inside them; do not add them to scheduler wait.
Numeric syscall/FD/command groups remain available without pointer values,
buffer contents, arbitrary process names, or private cgroup paths.

The traced render p95 lies between the two untraced arms. This brackets
observer/workload variation in this short sequence; it does not establish zero
tracing overhead or a causal improvement. All arms still fail the unchanged
**33.334 ms p95** tracking target. The other frozen CPU/input/release/session
memory checks pass, with zero excluded input pauses. The portrait-only parser
geometry warning remains explicit for this landscape board. Tasks 3.3 and 4.2
remain open, and video remains disabled by default.

## Exact source, capture, and recovery

[result.json](result.json), [descriptor.json](descriptor.json), and
[render-profile-staged-sha256.json](render-profile-staged-sha256.json) preserve
source `4459b06011fe8b164cee25f275bdeff7dec462d0`, all staged script hashes,
and installed identities. The selected compositor package is
`/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`,
with actual ELF SHA256
`2778ed3cdac48b83806117a8d96accba0163dae21ba12b7a1104f1c1289fa3be`.
Its build source is `1a8e72ac52df5c80540bdeedc22edfcc4e5c167a`; Nix/runtime
inputs are unchanged through `4459b060`. No new build or system image is
claimed. The previous build receipt remains in the elapsed probe directory.

The exact controller is [run-board.py](run-board.py), staged as `run.py` under
`/var/lib/k230/render-profile-20261021`. Its collector is
[collect-board.py](collect-board.py), staged as `collect.py`, alongside
[cadence_audit.py](cadence_audit.py), the descriptor, and the source revision's
normalizer and transitive `landscape-hdmi-stall-trace.py` dependencies. With
the exclusive board reservation, the command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/render-profile-20261021/run.py
```

The controller refuses unexpected apps, identities, occupied output/recovery
directories, or an existing override. A 480-second root timer independently
restores the normal compositor. Each isolated trace instance has its own
600-second cleanup timer; no global trace controls are changed. The existing
trace tool's harmless board smoke proves the actual RISC-V ioctl/write/writev
ABI and monotonic marker brackets before the workload. Each instance uses a
32 MiB per-CPU trace buffer, with CPU0 as the only online CPU.

Artifacts are captured outside `/run/shell`, which a session restart removes.
Raw trace, private collector output, and screenshots remain protected outside
Git. The published trace is only the strict numeric export, compressed with
fixed gzip mtime and registered as DATA in the blob inventory. Its original
raw/export hashes, marker brackets, loss counters, and four partial events
outside the qualified render window are preserved; no capture timestamps were
adjusted. Microsecond trace timestamps leave small boundary precision error
against nanosecond render timestamps.

[final-audit.json](final-audit.json) independently checks the original `2ig`
system/profile, normal compositor SHA `4fc7bf3a…`, same boot, original still
generation, landscape, 8 ms allowance, active normal services, zero injected
devices, absent owned override/trace instances, and inactive owned timers.
The board reservation was released after export and this audit. There are no
boot/profile writes, priority changes, or persistent runtime changes.

## Replay and validation

From the repository root:

```sh
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/render-profile/test-render-profile-analyze.py
python3 tools/landscape-hdmi-stall-trace.py --self-test
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/render-profile/replay.py
openspec validate --all --strict
python3 tools/blob-scan.py --no-vendor
```

The four wait-partition tests and nine existing trace qualification/privacy
tests pass. Replay checks the strict public event schema, unchanged event
hash/count, mono clock brackets, zero loss, complete interior syscall/switch
pairs, disjoint wait partitions, phase sums, and trace cleanup. It reproduces
the scheduler/render join and independently replays the frozen card parser,
asserting its tracking count/p95 equals the cadence diagnostic. Host tests
validate analysis; the committed board records supply the timing evidence.
