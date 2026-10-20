## Context

See proposal.md and the completed logging comparison. At the same installed
source 221bbcf3, INFO retained six over 100 ms samples; removing DEBUG did not
eliminate the stalls. Six of nine late samples spanned mostly pre-submission
delay and three mostly post-submission, with frame-build CPU 4.351–5.174 ms.
The running kernel already exposes per-instance tracing, mono clock, scheduler
and raw-syscall events. Only CPU 0 is online. The global tracer is nop, enabled,
with no enabled events and the local clock; leave it untouched.

## Goals / Non-Goals

Userspace diagnostic tooling controls existing kernel tracepoints and joins them
to the current compositor's monotonic benchmark records. No source/kernel/image,
service logging, geometry, frame budget or app-content changes are planned.
Trace only the main event-loop thread, and report the limits of that coverage.

## Decisions

Create a unique owned instance under `/sys/kernel/tracing/instances/`, with
`trace_clock=mono`, a 32 MiB CPU 0 buffer and a 64 MiB total allocation ceiling.
Use only per-event filters: raw_syscalls/sys_enter and sys_exit by common_pid;
sched_switch by prev_pid/next_pid; sched_wakeup by its target pid. Do not set
global PID filters, clocks, tracers or enable flags. Record hashes of global
controls before setup and after cleanup. Arm independent 600 s cleanup before
creating/configuring the instance; verify ownership before stopping/removing it.

Use numeric raw-syscall events, not the named sys_enter_write tracepoint: its
observed format includes dynamic user-buffer contents. Raw events contain only
numeric register arguments; the public exporter omits pointers, buffer data,
process names and unused arguments. Commit numeric event records, source/raw
SHA256 provenance, trace formats, commands, timestamps, clock bounds and loss
statistics. Keep original raw trace text in protected scratch, not public docs.

First run a short isolated controller/clock smoke test using only the diagnostic
Python process. Known harmless write/writev/ioctl operations on /dev/null ground
the target ABI's syscall numbers without installing a profiler. Use bracketed
monotonic markers to verify the trace clock and parser. Then capture one untraced
and one traced 24-drag workload on the same live compositor PID, existing DEBUG
level, one ordinary Foot and 1280×800 normal HDMI. Keep 35 moves/0.7 s nominal + 1.6 s rest;
record the same runtime/config/environment/format and collector hashes. Start/
stop trace and export logs only outside the timed gestures. Keep memory-resident
trace collection bounded; no concurrent filesystem/journal reads during drags.
If no >100ms sample occurs in the first traced run, permit one more traced
24-drag run, retaining both attempts. Do not repeat indefinitely to find a win.

A trace qualifies only with zero overrun/commit-overrun/dropped events, matching
clock markers and complete benchmark joins. Correlate each late interval with
complete syscall enter/exit spans and switch-out/in intervals. Retain runnable
versus sleeping state and wakeup-to-reschedule time when observed; an elapsed
syscall is not automatically kernel CPU work or proof of blocking I/O. Boundary
partial events may be reported only outside the qualified input/present window.
Report tracing overhead and any ambiguity rather than force a causal label.

Cleanup disables and removes only the owned instance, stops benchmark mode,
requests Home, verifies original output/system/logging and unchanged global
controls, then stops its timer. No shell restart or default change is needed.

Rejected: modifying the global tracer, recording user buffers, installing a
new kernel, assuming C CPU counters locate wall delay, or reporting an
instrumented run as physical/optical acceptance.

## Risks / Trade-offs

- Tracing changes scheduling → paired untraced/traced measurements and explicit
  overhead; no guarantee that a rare untraced stall has the same mechanism.
- Ring capacity/partial capture → fail on loss or missing boundary coverage,
  preserve the failed attempt, never fabricate gaps or drop slow samples.
- Host disconnect → independent cleanup before enabling events, isolated owned
  directory and idempotent recovery; preserve any ownership conflict.
- Scheduling state alone is ambiguous → report syscall/switch/wakeup overlap
  and distinguish observed intervals from causal interpretation.

## Migration Plan

Land this tooling-only plan first. Host-test parsing, correlation and cleanup
ownership. Reserve the board for the short smoke and bounded paired workload,
restore normal state, commit safe evidence and inspect exact CI/publication.
Archive only after all performed proof is committed; keep inconclusive results
explicit and all separate portrait/glass gates open.
