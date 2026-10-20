# Landscape HDMI DEBUG/INFO comparison

Removing DEBUG verbosity did not eliminate the recorded latency spikes. The
four runs all have complete strict input/submission/presentation coverage.
Across 1,728 accepted input samples per mode, DEBUG p95/p99 were 27.292/45.127 ms,
with 3 samples over 100 ms and a 208.014 ms maximum. INFO p95/p99 were 27.289/44.142 ms,
with 6 samples over 100 ms and a 231.456 ms maximum. These small tail counts do not
establish that INFO is worse; they show that the stalls persist without DEBUG.
INFO benchmark logging remains active, so this does not rule out journal I/O
or other instrumentation overhead.

## Installed source and controlled workload

The compositor source remained `221bbcf34a276a939356e5a6af9bfb124af9896a` in
running/persistent system
`/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`.
The trial tool source is `cb656b618953a93900bac63c646a89f734a51bb0`.
Executable SHA256 stayed 9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670;
configuration SHA256 stayed 575fa8d14d8dda6d0707c369015d37dbd7ea9295c66cefdebef2ef3ea26bdcd0.
The same Pixman mapping/hash, render/input environment, 1280×800 @ 59.91 Hz normal
HDMI output, scale 1 and ARGB8888 format are recorded in every run.

A/B/B/A selects `-d`/`-V`/`-V`/`-d` on the same service/executable. Every run
restarts the session, waits 30 s, verifies only an idle standard startup Foot,
hides the Rust overlay and performs 24 alternating center drags. Each drag has
35 motion steps, nominal 0.7 s motion and 1.6 s rest. IPC adds time to nominal
pacing. There are 864 accepted input samples per run. No additional board queries,
file copies or journal scans ran during gestures. All four capture helpers
returned 0, and the strict report validates every joined frame independently.
The only service override replaces the logging argument; both streams continue
to use journald. No permanent image, default, renderer or geometry change ran.

The independent 900 s systemd restore timer was armed before writing any override.
`board/trial-a/restore-state.json` records its unique unit, original controls and
ExecStart. Only the exact owned runtime drop-in could be removed in cleanup.
The initial idle guard correctly stopped before mutation when it encountered
an unknown child. Inspection identified the normal repo terminal-color follower;
the corrected guard permits only that exact pinned Nix-store script/hash in a
sleeping process without child jobs. Host tests still reject unknown programs,
modified helpers, active jobs and unexpected apps. No user workload was killed.

## Per-run results

All times are milliseconds. Raw journal counts include DEBUG/INFO messages in
a bounded window rounded down to the capture-start second through final export.
Only numeric allowlisted diagnostics are retained; arbitrary journal text is
not committed. No raw collection hit its 20,000-line limit.

| Run | Mode | Build CPU p95 | Dispatch→present p95 | p99 | Max | >100ms | Journal lines | Bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | DEBUG | 4.891 | 26.506 | 45.127 | 208.014 | 2 | 14328 | 2461538 |
| 2 | INFO | 4.832 | 28.292 | 44.318 | 231.456 | 3 | 13096 | 2189091 |
| 3 | INFO | 4.831 | 26.674 | 39.741 | 208.567 | 3 | 13176 | 2203582 |
| 4 | DEBUG | 4.877 | 27.769 | 45.327 | 184.305 | 1 | 14246 | 2446324 |

Removing DEBUG reduced journal bytes by about 10.5% in these runs. Similar p95
latency and persistent large samples do not support changing DEBUG verbosity
as the latency fix. No significance or uniform-smoothness claim is made.

Of nine over 100 ms samples, six spent most of the delay before submission and
three after submission. Their frame-build CPU times were 4.351–5.174 ms. The
per-input spans, frame IDs and log-volume/process counters are in
`board/report.json`; these intervals do not identify a blocking syscall or
attribute runnable/off-CPU delay. Cumulative scheduler counters likewise do
not locate individual stalls.

## Reproduction and cleanup

`board/command.json` preserves the exact board command, and `board/driver.log`
records the four completed modes. Reproduce the strict report from the repo:

```
python3 tools/landscape-hdmi-logging.py --report docs/evidence/landscape-hdmi-logging/board/trial-a --output /tmp/k230-landscape-logging-report.json
```

The report is `MEASURED`, with performance acceptance `NOT_EVALUATED`.
`board/trial-a/restore.json`, `cleanup.json` and the timestamped
`board/final-check.json` verify original DEBUG logging, unchanged running and
persistent system/config/output, active shell/UI, no owned logging drop-in,
restore timer inactive, benchmark-stop and Home commands successful, no virtual
test devices, and an idle standard terminal with only its pinned color helper.
The session was restarted; no board reboot or boot-file change occurred. The
board reservation was released after these checks.

## Limits and next profiling boundary

This is direct-IPC input, not native/uinput, real-finger or optical proof. INFO
benchmark rows still add overhead. Four runs cannot exclude rare stalls or
explain their mechanism. Portrait requirements and every unperformed physical
gate remain open; no default was changed on this evidence.

Neither `strace` nor `perf` is installed. Read-only discovery found scheduler,
write/ioctl syscall tracepoints and per-instance tracing available in the
running kernel; see `preflight/trace-capabilities.json`. An isolated tracing
instance can next distinguish blocking writes, output commits and scheduler
waits while preserving the existing global tracer. No such correlated kernel
trace is claimed by this comparison.
