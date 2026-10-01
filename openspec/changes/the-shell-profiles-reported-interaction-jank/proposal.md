## Why

The operator accepts the drawer, keyboard and ordinary-card behavior, but unrelated unperformed
performance measurements keep their proposals open. Investigate reported slow
interactions when they arise, while preserving the exact deferred checks.

## What Changes

- Carry drawer tasks 5.2/5.4 and keyboard task 3.3 into this planned successor,
  authorized by the operator's 2026-10-01 closeout and performance-deferral request.
- Measure the reported slow workload on the installed board before optimizing;
  distinguish client paint cost, compositor presentation and subjective feel.
- Preserve drawer journal timing, the 17.3–34.6 ms estimate comparison and ~20 ms
  target; investigate scroll-direction damage-limited blitting only if warranted.
- Preserve keyboard visibility/gesture measurement against existing shell budgets.
- Carry the ordinary-card change's unperformed sub-400ms entry and sub-100ms touch acknowledgement measurements, using real contact or a persistent uinput device rather than process-spawn timing. Functional ordinary-card acceptance does not establish these numbers.
- Non-goals: new drawer visuals, unconditional performance tuning, more recordings
  just to reconfirm accepted behavior, or declaring an unmeasured budget passed.
- Board dependency: actual timing needs a reserved physical board; planning and
  trace review do not establish hardware performance.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: report drawer frame cost and ground reported slow interaction
  analysis in measured installed-board results. The drawer timing requirement is
  transferred here before its parent's archive; it is not dropped.

## Impact

Userspace Rust shell/compositor instrumentation and evidence only. No kernel,
boot, device tree or radio work. This is planned backlog, not active optimization.
