# Runtime trace capture

The Rust shell and persistent theme helper have bounded, opt-in span recorders.
They are disabled in the normal image configuration. A recording includes wall
and thread CPU time, process/thread IDs, nested spans, helper RPC parent IDs,
numbered shell commits, and Wayland presentation feedback. It contains no
request bodies, theme names, filenames or credentials.

This is an initial implementation, not proof that every component is covered.
Compositor internals, scheduling and sampled CPU stacks remain separate work.
Only the picker currently tags input events and carousel motion phases; spans
also cover other shell rendering and helper operations. Home/wallpaper surfaces
do not yet get numbered presentation feedback from this instrumentation.

## Operator interface

Reserve the board before changing services. Give each instrumented process its
own new output pathname writable by its service user, and the same 32-character
lowercase hexadecimal trace ID:

```sh
K230_TRACE_ID=0123456789abcdef0123456789abcdef
K230_TRACE_SECONDS=30
K230_TRACE_PATH=/run/shell/rust-trace-unique.json
```

Set these only for the bounded diagnostic service invocation. For the helper,
use a different file such as `/run/shell/helper-trace-unique.json`. Files use
exclusive creation and mode 0600. Existing files are never truncated. Rust
allocates a fixed 65,536-event buffer; Python limits its list to the same event
count. The recorder counts overflow. Files remain empty during collection and
are serialized after the observation window (10–180 seconds). A killed process
may leave an empty file; this is a failed capture, not an empty workload. Do not
include serialization after the window in the measured gesture workload.

Collect the two files from the same boot and capture. On the host:

```sh
python3 tools/runtime-trace-export.py rust.json helper.json \
  --timeline timeline.json --summary summary.json
```

Open `timeline.json` in [Perfetto](https://ui.perfetto.dev/). Nested slices show
wall time; `cpu_us` is the thread's inclusive CPU time during each span. Do not
sum nested CPU totals. Parent flows join the Rust RPC span to helper execution.
An uninstrumented subprocess is included in its caller's wall wait but its CPU
work is not attributed to the caller's thread CPU counter.

The summary ranks active presentation gaps, excludes transitions from idle,
and reports presentation clock incompatibility, lost events, unmatched parents,
missing feedback and discards. Wayland callback reception, commit submission,
presentation timestamp and feedback delivery are distinct observations. Input
latency begins at shell receipt, not the physical touchscreen timestamp. A
presentation notification does not measure photons on the panel. Overlap with
helper work is a lead for investigation, not proof it caused a stall.

## CPU flamegraphs

The span timeline is not a sampled CPU flamegraph. Build the opt-in target sampler with `nix build .#runtime-perf`; it stays
outside the normal image. Verify unwinding/symbols for the workload. With that tool,
these are the bounded operator commands (the first physical trial is linked below):

```sh
perf record -e cpu-clock -F 99 -g --call-graph fp \
  -p COMMA_SEPARATED_VERIFIED_PIDS -o /run/profile-private.data -- sleep 20
perf script -F comm,pid,tid,time,period,event,ip,sym,dso \
  -i /run/profile-private.data > /run/stacks-private.txt
```

Use the actual verified shell/compositor/helper PIDs; do not paste that literal
placeholder. Record start times to catch PID reuse. Software `cpu-clock` avoids
assuming hardware PMU support, but its availability and stack quality still
need a board trial. Keep raw stacks private pending review; resolve addresses
against the exact binaries/debug symbols, and report truncated/unknown stacks.
Generate a flamegraph from the reviewed folded stacks using a pinned tool.
Sampling, span instrumentation and combined tracing each need their own observer
cost measurement against the same workload with instrumentation disabled.

The remaining work and physical evidence gates are tasks 13 and 15 of
`the-shell-swaps-themes-without-a-python-stall`.

First physical trace: [picker timeline](evidence/theme-picker/runtime-trace/README.md).
First physical CPU sample and stack-quality limits:
[picker CPU profile](evidence/theme-picker/cpu-profile/README.md).
