# Landscape DRM connector polling and mutex waits

This is a diagnostic on the unchanged landscape board, following the kernel
sleep-stack evidence in `../landscape-drm-wait/README.md`. It does not change
hotplug behavior, the installed image, output geometry, or shell defaults.

## Method and qualification

`tools/landscape-drm-holder.py` reuses the existing 24-drag direct-IPC workload
(35 move events over nominal 0.7s, 1.6s rest, 864 complete input/present joins).
The pair uses the same existing DEBUG Sway process, one idle Foot and pinned
color follower, source `221bbcf34a276a939356e5a6af9bfb124af9896a`, and installed/persistent
system `/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`.
HDMI remains 1280x800, normal transform, scale 1, 59.91Hz. No camera or real-glass
input was used; this does not complete any deferred portrait evidence gate.

An exclusive tracefs instance records target-PID scheduler and raw syscall
scalars plus seven selected kernel function entries. The public function
stream contains only timestamps, PIDs, CPU, and allowlisted function/caller
symbols. Other caller symbols become `[other]`; raw pointers, names and
arguments remain in private originals and are not committed. Each stream is
hashed. Monotonic markers bracket `time.monotonic_ns`; the report requires
zero overrun/commit-overrun/drops and exact numeric+function ring entries.
An independent 600s cleanup timer precedes mutation. Cleanup verifies owned
inode, event filters, tracer and function filters; global controls are hashed
and must remain unchanged.

The pinned kernel source excerpts and file hashes are in
`preflight/kernel-grounding.json`. `drm_helper_probe_detect_ctx` acquires its
device's `connection_mutex`, calls `detect_connector_status` on success, then
calls `drm_modeset_drop_locks`. The measured interval from detect entry to
drop-lock entry is therefore a **conservative held-lock interval**, not an
exact acquisition-to-release duration. Qualification requires a complete
poll/probe/detect/LT9611/drop sequence on the same worker PID with matching
callers. Backoff or ambiguous/incomplete probe sequences are rejected. The
small probe helper can be inlined: an observed direct `output_poll_execute`
caller is accepted, or a separately observed helper caller chain is required.
A poll may inspect multiple connectors; each completed probe is qualified
separately.

## Smoke and rejected attempt

Source `6c15edd550c69121681aff085ec1c9d05c432bcc` completed its first 25s idle
capture with strict exports and successful cleanup, but its interval checker
rejected the actual compiler-inlined helper path. The driver exited **2**;
that rejection and unchanged records remain in `board/rejected-smoke-a/`.
It is not a qualified smoke or an exit-0 run.

Source `9afa87c925b823c44340c901b795a89a106484e6`, tool SHA256
`49ef1e5b7de367527a1ab8380a4b8fb9413547dfac9e76e684eb829ddfc19c98`, adds the
inlining/multiple-probe regression fixture. All eight host test methods pass;
these are tooling tests only. A fresh board smoke in a new directory qualified
at **2026-10-20T16:05:42Z**: 39 numeric and 124 function records, three complete
poll cycles, no loss or rejected intervals, all clock/count/cleanup checks
passed. Each cycle contained a fast ~0.4ms probe followed by a slow probe
holding the connection mutex for at least **173.679–176.931ms**. This idle
measurement does not establish that a particular shell input was blocked.

## Paired board result

The original board driver **exited 0** (`board/trial-a/command.json` and
`driver.log`). It performed exactly one untraced workload, one instrumented
workload, and the single permitted instrumented retry because the first
instrumented workload had no >100ms input. No additional trial was run.
Each workload has **864 complete input/present joins**.

| Run | Wall p95 / p99 / max (ms) | Inputs >100ms | Frame CPU p95 / max (ms) |
| --- | --- | ---: | --- |
| Untraced | 27.331 / 45.781 / 208.050 | 1 | 4.884 / 5.456 |
| Traced | 25.920 / 46.181 / 47.399 | 0 | 5.030 / 5.971 |
| Traced retry | 28.328 / 47.052 / 201.241 | 5 | 5.056 / 5.924 |

Wall p95 differed from untraced by -1.411/+0.997ms and frame CPU p95 by
+0.146/+0.173ms (~3.0/3.5%). These include phase variation and tracing;
they are not an isolated overhead calibration or an improvement claim.
The first traced run still recorded six slow poll holds (177.217–181.465ms)
but no >100ms DRM call. The retry recorded six slow holds (171.749–188.606ms)
and six >100ms DRM calls; five overlapped late input samples and one occurred
outside late input samples. Poll starts were approximately 10.240s apart.

The retry's five late samples are:

| Input / frame | Input→present (ms) | Frame CPU (ms) | Long DRM ioctl / wall (ms) | Main-thread sleep (ms) | Slow poll held interval (ms) | Drop entry→wakeup (µs) |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| 54 / 13015 | 184.382 | 5.303 | ATOMIC / 171.662 | S / 171.310 | 179.229 | 30 |
| 194 / 13260 | 201.241 | 4.772 | OBJ_GETPROPERTIES / 180.604 | D / 180.547 | 187.659 | 31 |
| 333 / 13500 | 185.854 | 5.366 | ATOMIC / 168.060 | S / 167.691 | 171.749 | 30 |
| 480 / 13764 | 193.735 | 4.761 | OBJ_GETPROPERTIES / 165.752 | D / 165.691 | 183.873 | 29 |
| 621 / 14017 | 184.564 | 4.800 | OBJ_GETPROPERTIES / 170.749 | D / 170.681 | 182.381 | 31 |

The two atomic waits occur after frame submission; the three property-query
waits occur before submission. Wake→run was 17–21µs for these main waits.
Worker PIDs 101141/101254 execute the complete source-qualified polling call
chain. Their connector mutex is held throughout the measured detect→drop
intervals. The shell's DRM calls overlap those intervals, its sleeping thread
wakes just after drop entry, and the previous unchanged-kernel diagnostic
locates these call paths in modeset mutex acquisition. **The polling worker
is the source-grounded connector-mutex holder associated with these five
stalls.** This conclusion uses the observed critical section and wakeup,
not the scheduler's next-task PID.

`board/final-check.json` maps the shell's DRM descriptors 10/11/12 to **card0**,
which owns disabled/disconnected DSI-1 and enabled/connected HDMI-A-1. The
atomic connector-state path and polling detector take that device's
connection mutex; the all-lock property-query path takes it first. Symbol
tracing does not export mutex addresses or a connector identifier, so the
per-probe connector identity is not independently recorded.

The trace qualifies 12 held intervals per instrumented run (two probes for
each of six poll cycles), with zero rejected probe intervals. Exact ring
counts are 371,915 numeric + 4,911 function = **376,826** entries, and
370,565 + 4,854 = **375,419** entries for the retry. All overrun, commit-overrun
and dropped-event counters are zero. Clock markers cover all input/present
samples. The strict report and original capture/export hashes are in
`board/report.json` and the run `trace.json` files.

Capture/controller source remains `9afa87c925b823c44340c901b795a89a106484e6`
(SHA49ef1e5b… above); the board copy was not overwritten after qualification.
Host reporting source `ad032fa4f299dad9763acd6f516f88fd26a2f4d9`, SHA256
`6c12fc6b5179e1ff35415076f101687e4878bb846761c11df162f74a2917346f`,
adds all long DRM calls including input-idle intervals, checks paired
capture/smoke/exporter identities, and records `report_tool_sha256` separately.
It does not change capture code, timestamps, counts, records or hashes.
Private raw files remain outside Git, byte/hash-verified against their
original metadata before public curation. Only sanitized deterministic gzip
streams are committed, each with its own binary inventory entry.

## Normal state

At **2026-10-20T16:21:34Z**, final hardware checks confirmed all four owned
trace instances/function tracers removed, all cleanup timers inactive, six
global control hashes unchanged, Home/benchmark-stop successful, both shell
services active, the original idle Foot/color follower, zero virtual test
devices, and unchanged PID77507, executable/config, source221/j30 image,
DEBUG settings and landscape output. No reboot, flash, shell restart,
persistent override or default change occurred. The private copy finished
and hashes passed before releasing the board reservation.

## Limits

A source-grounded held-lock interval and its overlap with a syscall require
interpretation; no mutex address is exported, and the scheduler's next PID
is not used to infer ownership. The prior diagnostic captured actual kernel
sleep stacks in modeset mutex acquisition; this probe adds polling critical
sections without capturing new sleep stacks. All wall durations include
instrumentation and scheduling. Paired differences are observed, not an
isolated overhead calibration.

The full detect path includes bridge and HDMI helper work. Source shows that
HDMI hotplug update may reread EDID within detection. This probe does **not**
measure the duration of the individual status-register read, EDID read, or I2C
transaction. No hotplug fix, polling-disable comparison, optical smoothness,
native input, portrait result, reboot or flash is claimed.
