# Landscape HDMI stalls: correlated syscall and scheduler evidence

The bounded trial locates four reproduced >100 ms input-dispatch-to-present
samples in long DRM ioctls on the compositor main thread. Three overlap
`DRM_IOCTL_MODE_ATOMIC` (171.629–185.200 ms, sleeping S); one overlaps
`DRM_IOCTL_MODE_OBJ_GETPROPERTIES` (182.484 ms, sleeping D). Each matching
sleep ends only 0.017–0.020 ms after its wakeup. Frame-build CPU for those
samples is 4.948–5.476 ms. These observations locate the reproduced delay in
the DRM syscall path; they do not identify the internal kernel wait, prove a
particular atomic flag, or establish that every untraced stall has this cause.
No compositor, kernel, logging, image, geometry or frame-budget default changed.

## Workload and result

Installed compositor source `221bbcf34a276a939356e5a6af9bfb124af9896a`, running
and persistent system `/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`;
PID 77507, original DEBUG, Pixman, 1280×800 normal HDMI at 59.91 Hz, scale 1,
one ordinary idle Foot with its pinned color follower. All three runs use the
same PID/config/environment/output/collector and direct `card_shell` IPC route:
24 drags, 35 moves per drag, 0.7 s nominal motion and 1.6 s rest; the IPC client
waits for commands so actual pacing is recorded separately. Each run has
864 complete input-to-submit-to-present joins and 859 frame-build CPU samples.

| Run | Dispatch→present p95 | p99 | Maximum | >100 ms | Build CPU p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Untraced | 26.102 ms | 32.907 ms | 208.472 ms | 3 | 4.828 ms |
| Traced | 27.521 ms | 39.207 ms | 47.923 ms | 0 | 5.031 ms |
| Traced repeat | 26.116 ms | 46.467 ms | 209.954 ms | 4 | 5.034 ms |

The first traced run had no >100 ms sample, so the plan's one permitted repeat
was used and retained. No further searching/repeats occurred. Relative to the
single untraced run, traced p95 wall latency changes by +1.420/+0.015 ms;
build CPU p95 changes by +0.203/+0.206 ms (~4.2%). These are observed paired
run differences, not isolated estimates of instrumentation cost. Rare-tail
counts vary; no claim that tracing eliminates stalls or preserves their rate.

| Repeat input / frame correlation | Total | Before submit | After submit | Long ioctl | Matching off-CPU state / span |
| --- | ---: | ---: | ---: | --- | --- |
| 62 | 199.485 ms | 10.363 ms | 189.122 ms | ATOMIC 185.200 ms | S / 184.790 ms |
| 201 | 201.834 ms | 192.790 ms | 9.044 ms | OBJ_GETPROPERTIES 182.484 ms | D / 182.429 ms |
| 335 | 191.598 ms | 18.422 ms | 173.176 ms | ATOMIC 171.629 ms | S / 171.268 ms |
| 762 | 209.954 ms | 18.944 ms | 191.009 ms | ATOMIC 175.731 ms | S / 175.381 ms |

`board/report.json` contains exact monotonic timestamps, frame IDs, top
syscall/switch spans, scalar ioctl commands and return values. All four long
calls succeed and use fd 10, independently labeled DRM-card in each run's
control record. Headers from the installed Sway's libdrm derivation map
0xc03864bc to ATOMIC and 0xc02064b9 to OBJ_GETPROPERTIES; see
`preflight/drm-source-map.json` for read source paths, hashes and excerpts.
The running kernel source takes modeset locks for GETPROPERTIES. Lock
contention, commit completion, fences and vblank are candidates for subsequent
kernel-stack investigation, not findings of this trace. No further renderer
optimization is justified by these four frame-build CPU measurements alone.

## Capture and privacy provenance

`board/trial-a/command.json` preserves the exact board command; `driver.log`
preserves its completion phases. The hardware capture used helper source
`ce88a7246f3fd4bc12ea4a90242b38b7af788285`, SHA256
`32c177f57e77283460346b1f453a790456e7e441367976d083b099084fae1075`.
Its short controller smoke independently qualifies RISC-V syscall IDs
write=64, writev=66, ioctl=29 and monotonic clock markers.

Only raw_syscalls enter/exit and target-filtered scheduler switch/wakeup events
were enabled in unique instances. The named write event was explicitly avoided
because its kernel format includes user buffer contents. Public exports omit
process names, pointer/register arguments, buffers and unrelated syscall return
values. Unknown returns retain only errno category; selected I/O calls retain
scalar fd/count/command/result. Original raw files and original numeric exports
remain protected private scratch and are never committed. Their SHA256 hashes
are retained. The host re-export helper SHA in each trace.json differs from
the original capture helper SHA: return-field redaction was performed offline
without altering timestamps, event count, ordering or original loss statistics.

Both safe numeric streams are stored as deterministic `events.jsonl.gz`:
371,687 and 373,291 events, respectively. Their trace.json hashes identify the
uncompressed safe exports. The report reader bounds expansion to 64 MiB,
checks that hash, enforces the allowlisted numeric schema, and rejects ambiguous
plain+compressed files. Source `30fd40f5` performed the safe re-export; the
subsequent compression-aware reader does not change capture/export provenance.

Each instance uses mono clock and a ~32 MiB single-CPU ring. Bracketed start/end
markers align with CLOCK_MONOTONIC (printed trace timestamps have microsecond
precision); all input-to-present intervals lie strictly inside those bounds.
Both traces have zero overrun, commit overrun and dropped events. Initial/final
partial switch/syscall pairs lie outside the qualified benchmark windows and
remain explicit in the report. Only the main thread is covered. Syscall wall
time includes descheduling; it is not kernel CPU time. The scheduler identifies
sleep state and wakeup-to-reschedule delay, not the kernel stack or wait owner.

## Reproduce the host proof

```sh
python3 tools/landscape-hdmi-stall-trace.py --self-test
python3 tools/landscape-hdmi-stall-trace.py --report docs/evidence/landscape-hdmi-stall-trace/board/trial-a --output /tmp/landscape-hdmi-stall-report.json
```

The pre-archive OpenSpec proof was
`openspec validate the-landscape-hdmi-stalls-have-correlated-scheduler-and-io-traces --strict`
(exit 0).

Nine host tests pass, including negative clock/loss/private-field/PID/partial-
pair/ownership/cleanup/frame-join cases and compressed identity/expansion guards.
Host command output and hashes are under `host/`. The board workload is a
real DRM hardware diagnostic using direct IPC; it is not native/uinput routing,
physical glass contact, camera/optical proof, portrait acceptance or a shipped
performance fix. The older portrait proposal's nine hardware/profile gates
remain open while the user keeps landscape.

## Cleanup and next boundary

Per-instance independent 600 s recovery timers were armed before kernel changes.
Both instances/timers were removed after capture. Global tracer/clock/enable/PID
filter hashes match before/after, including a separate final check at
2026-10-20T06:08:28Z. Home and benchmark-stop succeeded, services are active,
the original idle Foot/color follower remains, virtual test devices=0, original
DEBUG/output/system/config are intact, and no reboot occurred. See
`board/final-check.json` and its exact query source. The exclusive board lease
was released after copying completed and cleanup verification; no build slot
was needed. The next useful measurement is a bounded kernel-stack/DRM wait
trace around these ioctls, preserving this installed image and landscape.

CI and exact evidence publication at revision `7f590fa3` are recorded in
`board/evidence-publication.json`; the initial missing gzip inventory rows
were corrected and the binary-accounting guard passes. This tooling-only
change has no delta specs or main-capability changes.
