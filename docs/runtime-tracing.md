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

The span timeline is not a sampled CPU flamegraph. For that, build the opt-in
target sampler with `nix build .#runtime-perf`. It stays outside the normal
image, so copy it to the board. Then run the host tool:

```sh
tools/board-profile.py OUT_DIR --unit shell-ui --unit shell \
  --title "drawer scroll" --fetch /var/tmp/drawer-run \
  --workload docs/evidence/interaction-jank/drawer-scroll/drawer-scroll.py.txt \
  -- /var/tmp/drawer-run SYSTEM 30
```

`SYSTEM` is the board's `readlink /run/current-system`. The workload refuses
to run against any other system.

The tool holds the board lock and samples the main process of each unit with
`perf record -e cpu-clock -F 199 --call-graph dwarf,65528`. It starts the
workload a second later and stops sampling when the workload exits. It records
each PID with its start time and warns if a unit restarted. It runs
`perf script` on the board and renders on the host with the flake-pinned
FlameGraph scripts. `OUT_DIR` receives:

- `flamegraph.svg`: aggregated stacks. Open the SVG on its own to zoom and
  search.
- `perf-script.txt.gz`: raw samples. Import into
  [speedscope](https://www.speedscope.app) for a time-ordered flame chart per
  thread.
- `folded.txt` and `summary.json`: sampled CPU per process and the hottest
  frames, inclusive and self.

Unwinding notes:

- Use DWARF unwinding. Frame pointers stop inside the nixpkgs C libraries.
- A 16 KiB stack copy truncates inside pixman's `general_composite_rect`,
  which keeps a large buffer on the stack. 65528 bytes holds full chains.
- Stock nixpkgs binaries keep `.symtab`, so Rust, pango, cairo and pixman
  frames resolve by name without debug packages.

Sampling costs CPU on the one-CPU board. Use a profile to see where time goes,
and take timing figures from a separate unprofiled run of the same workload.
The output names processes, functions and store paths. Review it before
committing, as with any capture. First use, with before/after flamegraphs:
[drawer profile](evidence/interaction-jank/drawer-profile/README.md).

The remaining work and physical evidence gates are tasks 13 and 15 of
`the-shell-swaps-themes-without-a-python-stall`.

First physical trace: [picker timeline](evidence/theme-picker/runtime-trace/README.md).
First physical CPU sample and stack-quality limits:
[picker CPU profile](evidence/theme-picker/cpu-profile/README.md).

## Cost attribution counters (task 13.2)

The same recorder keeps fixed-size counters, independent of the event ring, so
totals stay exact after the ring overflows. A fixed table of 17 names (scene
rebuild, render total, row repaint, overlay draw, thumbnail request,
completion, poll, cache read, hash, resolve and decode, appearance prepare,
helper RPC, theme request, speculative admission, speculative completion and
overlay pre-render) is bucketed by three gesture phases reported by the shell
loop: `rest`, `held` and `moving` (coasting and settling are not separated).
Each cell holds count, wall microseconds, thread CPU microseconds and the
maximum wall time; names are constants, so nothing request-derived is a key.
Span times are inclusive of nested spans, so kinds must not be summed. Phase
changes go to a 1,024-entry log with a drop count. Reports add `counters`,
`phase_log`, `phase_log_dropped` and `counters_only` (schema stays 1).

Modes, selected only by the service environment (default is off):

| mode     | environment                                              |
|----------|----------------------------------------------------------|
| off      | none of the `K230_TRACE_*` variables                     |
| counters | `K230_TRACE_PATH` + `K230_TRACE_COUNTERS_ONLY=1`         |
| trace    | `K230_TRACE_PATH` (event ring plus counters)             |

`tools/theme-picker-profile.py` (plan keys `instrumentation` and
`attribution`) verifies the mode from the Rust process environment, samples
per-thread CPU with start-time identity, RSS and helper cgroup CPU, and
`reduce --rust-trace FILE` correlates counters with the monotonic harness
phases. Counter, PID and thread-identity discontinuities are counted and
excluded, never summed. `overhead OFF.json ON.json` compares an
instrumentation-off report with an on report of an otherwise identical run;
interpret detailed timings only after that observer cost is known. Do not run
native screencopy inside the timing pass.
