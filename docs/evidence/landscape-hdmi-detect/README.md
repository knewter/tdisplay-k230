# HDMI polling EDID-stage timing on the unchanged landscape board

The EDID-read path accounts for **99.76–99.78%** of the measured slow
connector-mutex holds in three complete polling cycles. This narrows the
holder evidence in `../landscape-drm-holder/README.md`: it does not install a
fix or establish a new motion, native-input, glass, or optical result.

## Hardware method and provenance

A single **35s idle observation** traced thirteen selected kernel function
entries and two monotonic markers. There were no injected gestures, no
scheduler/raw-syscall events and no EDID-buffer capture. The existing DEBUG
Sway PID77507, executable9464072…, configuration575fa8…, source221bbcf3 and
installed/persistent `/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`
remained unchanged. HDMI-A-1 stayed1280x800@59.91Hz, normal, scale1, with one
idle Foot and the pinned color follower. No shell restart, reboot or flash.

Controller/capture/report source is
`6b94a7859a8935de28a4d25dc94b2f92e5e649a0`, SHA256
`ddfdbc6d97c250597c829eccba5c5e042a5c772086f9d06f84cea3e8f9434be9`.
Trace metadata records all six imported helper hashes. Seven host test
methods passed; they prove tooling only. A fresh hardware smoke qualified at
**2026-10-20T17:31:02Z**, capturing three records including the controller's
bracketed **50.125456ms** sleep. Its clock/count/loss and cleanup checks passed.
The original main board driver exited **0**. Source, command, timestamps,
actual exit status and unchanged records are in `board/trial-a/`.

The one-MiB CPU0 tracefs instance was exclusive and had an independent600s
cleanup timer armed before mutation. Exact ring/export count is **205**
records, with zero overrun, commit-overrun and dropped events. Mono markers
lie within recorded time.monotonic_ns brackets (microsecond print precision
is allowed ±1µs). The private raw trace is20,521bytes, SHA256 recorded in
`trace.json`, verified byte-for-byte after download. Raw task names/text
remain private outside Git; the committed JSONL exports timestamps, scalar
PIDs/CPU and allowlisted function/caller symbols only. No new binary asset.

## Measured stages

Pinned source excerpts/file hashes are in `preflight/kernel-grounding.json`.
Successful `drm_helper_probe_detect_ctx` detection is within that device's
connection_mutex critical section. The holder parser requires a complete
poll/probe/detect/LT9611/drop sequence with source-grounded caller order on
the same worker. The small probe helper may be compiler-inlined, as already
observed in the preceding diagnostic.

Inside that held interval, the HDMI hotplug/update path calls
`drm_bridge_connector_read_edid` and the LT9611 EDID callback. The subsequent
`drm_edid_connector_update` entry follows completion of that reader in the
pinned source. These two entries bound the EDID-path stage. It includes
wrappers, validation and return overhead; it is not exclusive function CPU
time or an exact inlined lt9611_read_edid duration. That inlined function
is not separately traceable in this compiled kernel.

| Cycle | Detect→reader (ms) | Reader→connector-update (ms) | Update→drop (ms) | Held interval (ms) | EDID-path share |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.366 | 170.050 | 0.043 | 170.459 | 99.7601% |
| 2 | 0.367 | 179.789 | 0.044 | 180.200 | 99.7719% |
| 3 | 0.366 | 183.549 | 0.042 | 183.957 | 99.7782% |

WorkerPID103026 executes each complete path, with two EDID-block callback
entries per read. The trace does not record block arguments or monitor
contents. Poll starts are approximately10.240s apart. Four fast probes
contain no connector EDID-reader marker. A fourth slow probe crosses the
end of the capture: it is explicitly retained as **rejected: capture
boundary before probe completed**, and contributes no invented duration or
stage. There are three qualified EDID stages and no rejected EDID stages
inside those complete probes. `board/report.json` preserves all observations
and the boundary rejection; no extra observation was run.

The earlier diagnostic associates five late inputs with this polling
worker's connection_mutex holds and wakeups just after release. This idle
stage observation is separate evidence. It does not reproduce those input
latencies or show an improvement. All durations include instrumentation and
scheduling; there is no uninstrumented per-stage calibration. No mutex
addresses or per-probe connector IDs were exported. The shell's DRM card0
owns connected/enabledHDMI-A-1 and disconnected/disabledDSI-1, as recorded
in the final hardware query.

## Normal state and remaining work

At **2026-10-20T17:34:30Z**, both owned trace instances and timers were gone,
all **nine** root hashes (controls, function/graph filters and trace options)
matched, Home/benchmark-stop succeeded, services were active, the original
idle Foot/color follower remained, zero virtual inputs existed, and the
running/persistent system, executable/configuration, PID, DEBUG settings and
landscape output matched. Final query and source are committed. The board
reservation was released after private copy/hash verification and checks.

The targeted fix should avoid repeating this EDID path for unchanged link
status while preserving initial detection, real connect/disconnect handling
and requested mode/EDID refresh. That fix, its cross-build/deployment and
hotplug regression proof are **not performed by this diagnostic**. Individual
I2C transaction/delay contributions remain unmeasured. The separate portrait
change remains3/12, with nine hardware/profile evidence gates open.

## Publication

Evidenceaddb24b77886f5ee63bc6fd4f2733afb9533039e passedCI39467836791 and
was observed exactly in the public workboard data-revision at
2026-10-20T17:45:55Z (HTTP200). `publication.json` records URL/comparison.
All6diagnostic tasks are complete, with no delta/main specs. The separately
planned kernel fix remains UNVERIFIED until its own build/runtime/physical
gates pass; this diagnostic does not close those or the portrait gates.
