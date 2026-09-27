# Correlated picker trace: first physical capture

On 2026-09-27 UTC, an opt-in trace on the physical K230 recorded **36 shell
frames with presentation feedback, no discarded frames, no dropped events, and
four correlated Rust-to-helper requests**. This proves the initial recorder and
cross-process timeline work on the board. It is a single instrumentation smoke
trial, not an observer-overhead comparison or a smoothness acceptance result.

- [Open/download the Perfetto timeline](timeline.json), then load it in
  [Perfetto](https://ui.perfetto.dev/).
- [Frame report](summary.json), [workload and runtime identities](workload.json).
- Original numeric recordings: [Rust](rust.json), [helper](helper.json).
- [Capture script](capture.py) and [artifact hashes](SHA256SUMS).

## What the trace exposes

Across the 40-second recording, 35 scene rebuild spans consumed approximately
2,117 ms of thread CPU and 4,070 ms of elapsed time. The 36 complete overlay draws
consumed 2,251 ms of CPU. These are inclusive totals: do not add a parent span to
its children. The helper's four requests occupied 9,539 ms of elapsed time but
598 ms of its request threads' CPU. Its subprocess waits include work not yet
sampled by this recorder.

The four injected 40-pixel swipes (left/right in each row) produced 16 eligible
presentation intervals within the same gesture phase. Their median was 115 ms,
with a worst/p95 interval of 268 ms. These are **this short traced workload's
observations**, not steady-state FPS or an improvement/regression claim. The
intentional stationary contact pause and the transition into release are
excluded; counting that pause initially produced a misleading 613 ms maximum.
A regression fixture now covers that distinction. The timeline retains all
raw timestamps for inspection.

Presentation clock ID was Linux `CLOCK_MONOTONIC`; feedback flags were 7 and
reported refresh was 19,160,758 ns. Feedback reception can be much later than
presentation. Input latency starts at shell event receipt, not at physical
contact. Native media was not captured during timing. The touch source was the
verified virtual `K230 injected touchscreen`, not a human finger. This trace
is not proof of final visual polish, scanout photons, or physical acceptance.

## Reproduction and identities

Source: `ad752b1d` (recorder/build); the committed exporter also excludes
stationary hold-to-release intervals. Host commands passed:

```sh
python3 -m unittest discover -s tests -p 'test_runtime_trace*.py'
python3 -m unittest discover -s tests -p 'test_theme_helper_daemon.py'
python3 -m unittest discover -s tests -p 'test_theme_catalog.py'
python3 -m unittest discover -s tests -p 'test_omarchy_theme_transaction.py'
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib theme_picker
cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --bin k230-shell-rust
nix build .#nixosConfigurations.k230.config.system.build.toplevel --no-link
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --no-link
```

Those test groups passed 9, 7, 21, 26, 3 and 19 tests respectively. The coherent
candidate was
`/nix/store/h3kswyl1qhvs4a84jvl16dbljfm7nwfz-nixos-system-nixos-26.11.20260919.20b1ddd`;
its Rust executable was
`/nix/store/0xg4840qj0vsqb5dzgr0aifan485k8pc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`.
Full process IDs, start ticks and executable identities are in `workload.json`.

The operator held `/tmp/k230-board.lock`, imported the closure delta, checked
its kernel against the booted system, armed an independent five-minute restore
timer, and used `switch-to-configuration test`. No boot files were flashed.
Runtime systemd drop-ins set one shared trace ID, distinct exclusive trace files,
and `K230_TRACE_SECONDS=40` on `shell-ui` and `theme-helper`. The operator ran
`capture.py CANDIDATE_SYSTEM PROTECTED_UPLOAD_URL` using the image's Python
store path; the transport URL and raw console journal remain private. The
script records phases on the monotonic clock, validates virtual input,
checks service PID/start-time/executable stability, and hashes the unchanged
active generation. It uses the existing committed
`../finger-tracking/k230-picker-baseline.py` as `/run/k230-picker-baseline.py`.

After collection the host ran:

```sh
python3 tools/runtime-trace-export.py rust.json helper.json \
  --timeline timeline.json --summary summary.json
```

The trace drop-ins were removed and the previous installed system
`/nix/store/7hhr1fp722cq147svn5ni67ar1i66mys-nixos-system-nixos-26.11.20260919.20b1ddd`
was restored. Five shell/helper services were active, and no failed units were
reported; see [restoration observations](restoration.json). The durable theme
generation remained unchanged.

## Remaining coverage

Compositor internal stages, scheduling, sampled CPU stacks, subprocess CPU
attribution, matched instrumentation-on/off overhead, and an additional
interaction remain open (OpenSpec tasks 13 and 15). The board kernel has
`PERF_EVENTS`, `FRAME_POINTER`, `RISCV_PMU` and `FTRACE` enabled, but the normal
image does not contain `perf`. A subsequent [CPU profile](../cpu-profile/README.md) uses the separate
`runtime-perf` package and documents its stack-quality limits. This earlier
capture is a span timeline with thread CPU totals.
