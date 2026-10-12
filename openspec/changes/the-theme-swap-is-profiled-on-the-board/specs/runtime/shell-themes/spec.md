## ADDED Requirements

### Requirement: Theme swap latency and runtime CPU cost are reported from board measurements

<!-- UNVERIFIED: carried from the-shell-swaps-themes-without-a-python-stall
tasks 2.3, 3.4, 15.2 and 15.3 on the operator-authorized 2026-10-12 split.
No board result for these measurements exists yet. -->

The shell theme system's latency and CPU-cost claims SHALL rest on reviewed
measurements from the installed board. Each report SHALL name the runtime
identities, the exact commands, the observer cost and the coverage gaps.
Tap-to-visible latency SHALL be reported against the ~100 ms target. A miss
SHALL remain a miss. Elapsed trace spans SHALL NOT be presented as sampled
CPU cost. Host, QEMU and injected-only results SHALL NOT be presented as
physical latency.

#### Scenario: A swap is measured against the target

- **WHEN** an operator captures a bundled dark, a bundled light and a community theme swap on the reserved board
- **THEN** the committed report gives tap-to-visible latency, frame gaps over 33/50/100 ms and per-process CPU, together with the exact board commands

#### Scenario: The compositor cannot be unwound

- **WHEN** CPU sampling on the board cannot attribute compositor stacks
- **THEN** the report documents the precise unsupported sampling or unwinding gate instead of a flamegraph
