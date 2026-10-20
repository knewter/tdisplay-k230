## Context

See proposal.md. Previous source221/j30 direct-IPC diagnostics observed four
long DRM calls (three ATOMIC, one OBJ_GETPROPERTIES) with S/D sleep, immediate
rescheduling after wakeup and ~5 ms build CPU. Six whole-trace long calls have
~10.24 s spacing. DRM's nominal 10 s connector poll takes connection_mutex;
LT9611 detect reads I2C. This is a candidate only, without kernel wait stacks.
The board exposes isolated sched_switch stacktrace triggers and mono clock.

## Goals / Non-Goals

Userspace controls existing kernel facilities. Keep source221/j30, original
DEBUG, same compositor PID, one ordinary Foot and normal1280×800 HDMI. Locate
observed sleep stacks; do not change hotplug, service defaults, images or
geometry. No kernel build or glass/optical/portrait acceptance.

## Decisions

Reuse the strict numeric trace, workload and cleanup primitives from
landscape-hdmi-stall-trace.py, with a separate stack schema/controller. Use a
unique owned trace instance, mono clock, CPU0 32 MiB buffer, 64 MiB raw/export
bounds, target-only raw_syscalls and scheduler events, and an independent
600 s cleanup timer armed before changes. Leave global tracing controls alone.
Install a bounded 50000-count stacktrace trigger on sched_switch only when
prev_pid is the target and prev_state is 1 or 2 (S/D). Record the trigger before/after;
reject exhaustion or missing stacks during qualified target sleep intervals.
Set symbol-address/offset options off only in the owned instance. Do not enable
user stacks or the named write event that copies user buffers.

A short harmless sleeping Python process qualifies stack association, clock,
loss and cleanup before any compositor tracing. Pair one untraced and one
stack-traced 24-drag workload, 35 moves/0.7 s nominal+1.6 s rest. Permit at most
one extra stack-traced run if no >100 ms sample occurs; preserve all attempts,
including errors. No filesystem/journal/SSH inspection during timed gestures.
Report instrumentation overhead and an inconclusive outcome if reproduction
or stack completeness is absent; no inference may replace missing proof.

Parse numeric records with existing guards and stack records with a strict
symbol grammar. Remove offsets, addresses, process names, modules and unrelated
payloads. Unknown address-only frames become explicit unresolved placeholders;
never claim an internal wait is identified from those. Preserve raw SHA and
private raw originals; commit deterministic compressed safe numeric/symbol data
and account for each binary in docs/blob-inventory.md. Join each stack to its
immediately preceding target sleeping switch on CPU0 before another event, and
then to syscall/switch/input/frame windows. Reject ambiguity, truncation, loss,
clock mismatch, incomplete qualified pairs or changed source/workload. Distinguish
observed call chains from proposed polling/lock/I2C causality.

Cleanup verifies trigger ownership, disables/removes only the owned instance,
stops its timer, restores Home/benchmark-stop and verifies original controls,
services and no virtual devices. Keep compressed data hashes reproducible.

Rejected: global/function-graph tracing, unbounded stacks, raw pointer exports,
procfs polling during gestures, disabling connector polling, rebuilding the
kernel, and assuming syscall duration or periodicity identifies a wait.

## Risks / Trade-offs

- Stack overhead changes timing: paired baseline, explicit distributions and
  no assumption that all untraced stalls share the captured mechanism.
- Ring/trigger/stack truncation: fail strict qualification and retain rejection;
  do not drop late samples or repeat beyond the bounded allowance.
- Disconnect: independent cleanup and inode/filter/trigger ownership guards.
- Unwinder limitations: qualify harmless sleep first; preserve unresolved or
  inconclusive records rather than invent a call chain.

## Migration Plan

Land this diagnostic plan first. Host-test parsing/correlation/ownership, land
the tool, reserve the board for smoke and bounded paired capture, verify cleanup,
commit proof, then inspect CI/exact Pages. Archive only after every task's named
proof is committed. Main specs stay unchanged (skip_specs true).
