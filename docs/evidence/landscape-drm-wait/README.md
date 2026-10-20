# Landscape DRM stalls: sleeping kernel wait identified

Four reproduced >100 ms direct-IPC input-to-present samples contain a long
WW modeset-mutex wait on the compositor main thread. Three property queries
sleep in `ww_mutex_lock → drm_modeset_lock_all_ctx → drm_mode_obj_get_properties_ioctl`;
one atomic call sleeps in `ww_mutex_lock_interruptible → drm_modeset_lock → drm_atomic_get_connector_state`.
The latter function explicitly takes `mode_config.connection_mutex` in the
pinned running kernel source. The property-query all-lock helper takes that
mutex first, then CRTC/plane/private locks; its exact contended object is not
established by this symbol-only stack. No kernel worker/lock-holder trace or
poll-disable comparison was obtained. Connector polling remains a candidate,
not a proved cause. No performance/default fix is delivered by this diagnostic.

## Actual workload and observations

Same running compositor PID77507, source
`221bbcf34a276a939356e5a6af9bfb124af9896a`, original DEBUG and persistent/running
system `/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`.
HDMI-A-1 stays1280×800 normal at59.91Hz/scale1, with one ordinary idle Foot and
its pinned color follower. No shell/kernel/image restart, new defaults or
geometry changes. Each run is24 direct compositor-IPC drags,35 moves per drag,
0.7s nominal motion and1.6s rest; actual timestamps include IPC processing.
Both runs have864 complete input/submit/present joins. The first traced run
captured four late samples, so no extra gesture run was needed or performed.

| Run | Dispatch→present p95 | p99 | Max | >100ms | Build CPU p95 / samples |
| --- | ---: | ---: | ---: | ---: | --- |
| Untraced |26.294ms|45.580ms|207.668ms|2|4.866ms /855|
| Stack traced |32.474ms|47.425ms|223.216ms|4|5.078ms /851|

Observed traced p95 wall difference is+6.180ms; buildCPU p95 is+0.212ms
(~4.4%). These paired differences include instrumentation and run variation;
they do not isolate tracing cost or prove an unchanged rare-stall rate. All
four late frame builds use4.780–5.150ms CPU. The trace identifies a sleeping
kernel lock wait, not excessive frame-building CPU.

| Input / frame | Total | Pre-submit | Post-submit | Long DRM ioctl | Matching sleep / wake→run |
| --- | ---: | ---: | ---: | --- | --- |
|28 /6687|212.684ms|199.704ms|12.979ms|OBJ_GETPROPERTIES179.526ms|D179.458ms /0.021ms|
|162 /6919|191.966ms|183.984ms|7.982ms|OBJ_GETPROPERTIES167.797ms|D167.736ms /0.020ms|
|301 /7171|185.011ms|183.791ms|1.220ms|OBJ_GETPROPERTIES175.360ms|D175.301ms /0.022ms|
|578 /7666|223.216ms|18.025ms|205.192ms|ATOMIC191.422ms|S191.028ms /0.022ms|

`board/report.json` preserves exact monotonic timestamps, ioctl values and full
symbol chains joined to these sleeping spans. The atomic call's chain reaches
`drm_atomic_get_connector_state`, whose source takes connection_mutex. Both
ioctl names are grounded in the installed libdrm headers cited by the prior
`docs/evidence/landscape-hdmi-stall-trace/preflight/drm-source-map.json`.
Current kernel source paths, hashes and excerpts are in
`preflight/kernel-wait-and-counter-source.json`. The previous ~10.24s cadence
and nominal10s connector polling motivate a separate lock-holder/poll probe;
this capture does not identify the holder or why its critical section is long.

## Rejections and offline recovery are explicit

The original paired board command **exited2**, after both capture contexts had
recorded CAPTURED, the full trace was exported and recording was off. Its old
postprocessing checker incorrectly equated trigger-count consumption with
recorded stacks. No original trial success manifest or traced per-run control
record was written. Those records remain absent: none was fabricated.
`board/trial-a/original-driver.log`, `original-command.json` and `recovery.json`
preserve the original error, command, exit status and revalidation provenance.

The kernel's `event_trigger_count` continues to decrement with recording off;
the old helper read its final counter after slow board-side export/decoding.
It consumed19,232 counts, while the retained interval contains6,080 stacks.
The remaining30,768 is positive, so it never exhausted. An exact equality was
not a valid event-loss check. The corrected offline checker instead requires:

- Zero overrun, commit overrun and dropped events.
- Exactly370,178 numeric records +6,080 stack records =376,258 ring entries.
- One unambiguous stack for every recorded target S/D switch, before its
  corresponding switch-in; no missing, duplicate or unknown/private records.
- All benchmark joins complete and inside bracketed mono/CLOCK_MONOTONIC bounds.
- Original capture/export SHA256 identity, unchanged source/workload, and
  matching original/final controls plus collector runtime/output observations.
- A positive, owned bounded trigger count whose consumption covers every
  recorded stack; additional off-recording invocations remain explicit.

All these checks pass on the retained files. The report status is deliberately
`MEASURED_AFTER_POSTPROCESSING_RECOVERY`, not an assertion that the original
board driver exited0. Its traced control section identifies the final observed
control and the missing original per-run record. No original timestamps,
record counts, metadata or hardware captures were edited, and no extra
hardware attempt was made for recovery. Capture helper source is
`6fc2adf14df36ad1bb5b102d0b22ef9c18155d71`, SHA256
`4f29492ee1fc84934f181e7688b883e6f645035b599bf9992a526bb397f1f3c6`;
the current report helper SHA is separately recorded in report/host proof.

An earlier harmless smoke-a stopped before tracing_on because the kernel prints
`stacktrace:count=50000`; the first parser expected `stacktrace:50000`. The
count-label correction retained exact ownership guards. That rejection and
verified instance/timer removal are preserved under `board/rejected-smoke-a/`.
Qualified smoke-b captures41 numeric records and one resolved hrtimer_nanosleep
stack, with zero loss, matching clock, count49999 and verified cleanup. It
qualifies the actual capture helper6fc2, separately from later offline analysis.

## Isolation, privacy and reproduction

Only an owned tracefs instance is used: mono, CPU0,32MiB ring,64MiB raw/expanded
export limit, target raw_syscalls/scheduler filters, and50000-count S/D trigger.
Independent600s cleanup is armed before kernel mutation. Global controls stay
unchanged. Symbol addresses/offsets and user stacks are disabled only in the
owned instance. No named write event/user buffers are recorded. Public numeric
and symbol streams omit pointers, process names, modules and buffer contents.
Private raw trace originals retain mode0600 and only their hashes are public.
Deterministic gzip preserves the uncompressed safe-stream hashes; the two
binary inventory rows account for the compressed data.

```sh
python3 tools/landscape-drm-wait.py --self-test
python3 tools/landscape-drm-wait.py --report docs/evidence/landscape-drm-wait/board/trial-a --output /tmp/landscape-drm-wait-report.json
```

Nine host test methods pass, including inherited clock/loss/partial/frame gates,
stack privacy/adjacency/missing/duplicate cases, trigger ownership/exhaustion,
gzip identity/expansion, off-recording counters with exact ring coverage, and
rejection of an unknown recovery failure. The strict recovered report also
passes on the real committed capture. Commands, source hashes and exit codes
are in `host/`. Pre-archive validation command:
`openspec validate the-landscape-drm-waits-have-kernel-stack-evidence --strict`.

At2026-10-20T06:58:10Z, a separate final board observation verifies all three
owned instances/triggers/timers absent, global controls unchanged, Home and
benchmark-stop successful, services active, original idle Foot/color follower,
zero virtual devices, unchanged PID/source/system/DEBUG/landscape and no reboot.
Exact query source and result are in `board/final-check.py.txt` and JSON. The
board lease was released after download and final verification; no build slot.
This is a real DRM hardware diagnostic using direct IPC, not native/finger,
physical glass, optical or portrait acceptance. The older portrait proposal
remains3/12 with nine hardware/profile gates open.
