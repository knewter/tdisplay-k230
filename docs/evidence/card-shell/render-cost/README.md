# Diagnostic subdivision of measured frame CPU

This instrumentation runs only while the existing card benchmark is armed.
It keeps the acceptance producer rows, total charged CPU formula, parser and
budgets unchanged, and emits a separate numeric `K230_CARD_SHELL frame-cost` row
for a successful frame with pending input. Key: `(run, frame_id)`.

- `total_cpu_ns` matches that frame's existing `update_cpu_ns`.
- `render_cpu_ns` measures the whole output repaint handler: scene configuration,
  card preparation, wlroots/Pixman work and output commit. It is not pure Pixman
  time and is not wall-clock time spent waiting for presentation.
- `input_cpu_ns` measures synchronous input-handler policy and scene updates.
- The remainder is other charged work, chiefly timer/scene preparation outside
  those handlers. Extra clock calls and one log row add diagnostic overhead;
  this instrumented run cannot itself establish an optimization speedup.

Failed render attempts accumulate until the next successful frame, matching the
existing total's accounting boundary. One row is emitted per frame, not once per
coalesced input. Normal unarmed operation does no additional clock work. The
board exporter accepts only the five expected numeric fields for these rows;
arbitrary strings, missing fields and extra fields are rejected.

`python3 tests/test_card_shell_telemetry.py` executes the actual producer with a
deterministic CPU clock. It checks a 20 ns total split into 10 render, 7 input,
3 other, followed by 13 ns split into 11 render (including a failed attempt) and
2 input. Existing entry ordering cases still pass. The acceptance parser ignores
the diagnostic rows and retains the unchanged total fields. All 18 parser tests
and all 22 board-orchestrator tests pass.

`nix build .#card-shell --max-jobs 1 --cores 8 --no-link --print-out-paths` passes:
`/nix/store/5cxcjkfayy93zhyy2qybbrnad5rd3s6f-k230-card-shell`.
This is instrumentation, not a performance fix or default-image acceptance.

The cross-built Sway also passes all 17 native-input headless runtime checks
with `tests/card_shell_runtime.py --native-touch --benchmark`. `headless.json`
retains that result. The 105 actual diagnostic frame rows correlate exactly to
the corresponding submission totals; deliberately removing profiles or changing
a total is rejected. This is QEMU user-emulation evidence, not board profiling.

`analyze.py --input <telemetry.log> --output <profile.json>` requires complete,
unique frame coverage, matching acceptance totals and non-overlapping CPU
subdivisions before summarizing. It produces no acceptance decision.
