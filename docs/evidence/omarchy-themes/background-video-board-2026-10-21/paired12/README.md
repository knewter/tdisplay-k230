# Paired quiet 12 ms trial: three numeric passes, one tracking failure

The complete reserved-board trial ran **2026-10-21
16:57:40Z–17:01:42Z**. It repeats the named background workload, then tests
one and three cards with the same still/video fixture, file logging, and
12 ms render allowance. Three card arms pass every frozen numeric metric.
**Video with three cards still fails tracking p95 at 38.321 ms against
33.334 ms.** Task 3.3 and archive 4.2 remain open. No threshold, excluded
sample policy, default background, or persistent render setting changed.

## Card results

| Metric | Still, one | Still, three | Video, one | Video, three |
| --- | ---: | ---: | ---: | ---: |
| Frame-update CPU p95 | 3.995 ms | 6.616 ms | 3.794 ms | 6.232 ms |
| Render elapsed p95 | 4.758 ms | 6.975 ms | 5.881 ms | 7.794 ms |
| Motion-to-submit p95 | 18.815 ms | 18.715 ms | 18.499 ms | 19.284 ms |
| Motion-to-present p95 | 28.027 ms | 25.816 ms | 28.090 ms | 26.534 ms |
| Frozen tracking interval p95 | 19.167 ms | 19.176 ms | 19.167 ms | **38.321 ms FAIL** |
| Tracking interval maximum | 38.324 ms | 38.326 ms | 38.326 ms | 38.325 ms |
| Above-target tracking intervals | 6 / 204 | 8 / 204 | 7 / 204 | 12 / 204 |
| All-present interval p95 during motion | 19.166 ms | 19.166 ms | 19.166 ms | 19.165 ms |
| All-present interval maximum during motion | 19.258 ms | 19.205 ms | 19.171 ms | 19.237 ms |

All other numeric CPU/input/release/session-memory checks pass in all four
arms. There are **zero excluded input pauses**, six releases per arm, and
210 accepted motion inputs per arm. The original 33.334 ms p95 / 100 ms
maximum tracking target is retained. The combined report now contains both
one/multiple-card workloads; its portrait-only geometry warning remains for
this landscape board. The overall board-budget gate is not reported as passed.

Every above-target tracking interval in this trial contains an intermediate
actual presentation. In particular, all twelve failing-arm intervals have
one. The actual-present diagnostic remains separate from the frozen metric;
steady backend feedback is not a substitute acceptance test or optical proof.

## What the association audit establishes

[correlation-audit.json](correlation-audit.json) joins the recorded motion
timestamps to the actual render starts. All **840** motion inputs map to the
first subsequent recorded render; there are **zero** mapping disagreements
and zero render timing rows logged before their input-end row. This supplies
no evidence for a delayed submit association or nested-render accounting bug.

For all twelve failing-arm intervals, the intermediate presentation's render
started **before the next input was dispatched**. Crediting that earlier
render to the later input would change the meaning of the metric. The source
input gaps for these intervals are 20–21 ms, while dispatch gaps are
23.116–30.331 ms. Input delivery/render phase is therefore the next area to
investigate; this is an inference, not an established cause or a reason to
loosen the target. The audit reproduces the original tracking count/p95 and
does not edit the parser, feed rate, workload, or failed result.

Both video arms report `paused-covered`, no decoder PID, and unchanged
reported counters **and timestamps** at their before/after gesture snapshots.
These are boundary observations, not continuous state tracing. They do not
support attributing the failing drag metric to active video decoding merely
because exposed video is expensive elsewhere in the trial. No progress is
fabricated by subtracting counters across decoder lifetimes.

## Playback, resources, cover, and restoration

The named `handheld-theme-trial.py --workload backgrounds` command completes
with `completed-needs-operator-review`, restoration passed, and the fixed
[basic-result.json](basic-result.json). Its 12-second video sample records
72 decoded frames, 72 submissions, 71 callbacks, and distinct native captures.
The public result retains `physical_observation: UNVERIFIED`; this is real
installed-board/native evidence, not real-finger or panel-photon acceptance.

| Exposed-background resource sample | Still | Video |
| --- | ---: | ---: |
| Mean combined shell/shell-ui CPU, named workload | 0.0146 cores | 0.8947 cores |
| Sampled summed process RSS peak, named workload | 163,119,104 B | 197,373,952 B |
| Mean combined CPU, additional idle sample | 0.0159 cores | 0.8776 cores |
| Sampled summed process RSS peak, additional sample | 174,682,112 B | 215,195,648 B |

These measurements include the decoder in the UI service. Summed RSS can
count shared mappings more than once, sampled peaks can miss spikes, and
cgroup memory includes caches; none is a per-frame CPU charge. Resource
sampling is a separate observation from the drag-window decoder state.

The explicit opaque-Foot cover test reports `paused-covered`, null decoder
PID, and unchanged decoded/submitted/callback counters over two seconds.
Removing the owned cover resumes `playing`; the same resumed decoder then
advances each counter by seven. The source fixture is exactly the earlier
[8-second synthetic H264 640×360/30 fps fixture](../fixture.json), including
both original asset hashes. This does not establish universal codec/content
performance. Reduced-motion startup was not repeated here; the unchanged
Rust implementation's existing proof remains under
[candidate2/reduced-motion](../candidate2/reduced-motion/result.json).

[final-audit.json](final-audit.json) independently verifies original `2ig`
system/profile, normal compositor `4fc7bf3a…`, same boot, original still
generation, landscape, original **8 ms** allowance, journal routing, active
normal services, zero injected devices, absent owned override, all four
restore timers inactive, exact preference-byte equality, original app
appearance pointer, and removal of the owned fixture. The board reservation
was released after audit/export. There is no boot/profile write or permanent
runtime change in this trial.

## Exact source and commands

Source is `baca1124a22c5ab91200d7517061fbe7530c7667`, following the landed
[quiet 8/12/8 comparison](../quiet-cadence/README.md). The same compositor
package is reused:
`/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`,
actual ELF SHA256
`2778ed3cdac48b83806117a8d96accba0163dae21ba12b7a1104f1c1289fa3be`.
Nix/runtime inputs are unchanged since build source
`1a8e72ac52df5c80540bdeedc22edfcc4e5c167a`; the earlier
[build receipt](../tracking-elapsed/build-receipt.json) applies. No new build
or full image is claimed. [descriptor.json](descriptor.json),
[result.json](result.json), and [paired12-staged-sha256.json](paired12-staged-sha256.json)
retain installed identities and every staged input hash.

The controller [run-board.py](run-board.py) is staged as `run.py`, with
[collect-board.py](collect-board.py) as `collect.py`, [theme.py](theme.py),
[copy-private.py](copy-private.py), [restore-owned.py](restore-owned.py), and
[cadence_audit.py](cadence_audit.py). With the exclusive SSH board reservation:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/paired12-20261021/attempt4/run.py
```

The adapter invokes the named workload as user `shell` with its active
session environment, a private candidate manifest under `/run/shell`,
`--output /run/shell/source3-paired12-attempt4-basic-result`, and
`--raw-private-dir /run/shell/source3-paired12-attempt4-basic-private`.
Public helper code is staged separately under
`/run/k230-source3-paired12-code-20261021-attempt4/tools`; private snapshots
remain below the protected configuration directory. The shared protected
parent's permissions are not relaxed.

Each card arm uses six alternating 35-motion, 700 ms native-uinput drags,
the same selected-app setup, fixed landscape mapping, 12 ms allowance, and
the same bounded file destination. Controller and collector independently
record the output setting. Wallpaper boundary snapshots are added without
altering the input schedule or frozen telemetry rows. Global journal CPU is
sampled separately from the unchanged two-service session-resource rows.

A fresh snapshot captures the original generation, preference bytes, and
app-appearance pointer before activation. An independent 720-second root
restore timer arms before the candidate override. Recovery preserves raw
basic-workload artifacts, restarts the normal services, waits for the fully
configured UI environment, restores theme state as its owner, and validates
the owned fixture inode/hashes before deleting it as root. Raw stderr,
screenshots, and private rollback contents stay outside Git. Their source
log prefix is checked in [private-source-receipt.json](private-source-receipt.json).
Future replication needs fresh owned paths and a unique restore unit.

## Preserved failed attempts

[failed-attempts.json](failed-attempts.json) and the three attempt directories
retain the exact failed controllers/helpers, fixed results where produced,
private-log hashes, and recovery audits. No failed attempt collected card arms.

- Attempt 1 could not run user code placed below a protected parent; its
  initial fallback also read the UI environment before startup finished.
  Original theme/preferences/app pointer were verified directly against the
  snapshot, and owned fixture cleanup/timer removal completed manually.
- Attempt 2 reached `measure-video` with the startup terminal still visible
  and failed the named workload. The exact internal measurement cause was
  not exported; its own theme restoration passed. Outer fixture cleanup
  lacked permission to unlink from its parent. Snapshot equality was checked
  and the known remaining fixture removed as root.
- Attempt 3 ran the named background workload successfully, then rejected a
  different still-generation observation immediately after static activation.
  The exact rejected status was not retained. Automatic and independent
  restoration passed. The successful retry waits for both state and generation.

## Replay and validation

```sh
python3 -m unittest tests.test_handheld_theme_trial tests.test_theme_background_status
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination/test-log-destination-analyze.py
python3 -m unittest tests.test_card_shell_board_tools
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/paired12/paired12-analyze.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/paired12 --repo .
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/paired12/correlation-audit.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/paired12 --repo .
openspec validate --all --strict
python3 tools/blob-scan.py --no-vendor
```

The 28 theme/status tests and previously run 35 CPU-window/board-tool tests
pass. Replay uses unchanged frozen, elapsed, cadence, CPU-window, and video
progress helpers. It validates all four controlled runs, file-logged 12 ms
collector observations, normalized rows, generation identity, resource
windows, cover/resume progress, unchanged boundary snapshots when paused,
and restoration. The separate association audit reproduces the frozen count/
p95 while checking actual render ordering. Host analysis is not a substitute
for the committed board data or the remaining acceptance gate.
