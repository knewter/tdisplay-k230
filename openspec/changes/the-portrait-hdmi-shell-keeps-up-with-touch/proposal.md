## Why

The HDMI shell visibly lags and the operator cannot reliably leave an open app
with a finger gesture. Physical-board traces locate a major rendering problem:
1920×1080 portrait composition builds frames in 442 ms median, versus 15 ms
unrotated with the same pixel format; see
[the board trial](../../../docs/evidence/shell-responsive/board/README.md).

## What Changes

- Preserve the operator's portrait HDMI layout while replacing the expensive
  quarter-turn software composition path with a measured, correct fast path.
- Profile the responsible routines before choosing between software rotation,
  composition before rotation, or a narrowly scoped hardware rotation operation.
- Verify physical bottom-edge gestures from real apps, with input timestamps
  and output geometry recorded; fix the routing or hit area if that proof fails.
- Add reproducible paired performance and pixel-correctness evidence. Carry the
  selected defaults in Nix rather than leaving a live IPC tweak as the solution.

Non-goals: landscape as a workaround for the portrait monitor; lower resolution
as the accepted result; a replacement shell toolkit; a general GPU rewrite;
second-core bring-up; hardware acceleration without a demonstrated gain.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: responsive portrait HDMI composition and physical app-edge
  gesture acceptance, with explicit performance and correctness gates.

## Impact

Userspace Sway/wlroots/Pixman integration, compositor tests, Nix package/default
selection, trace tooling and committed evidence. A GPU candidate may also need
the existing access boundary; any new kernel scope needs a separate proposal.
Host pixel tests can proceed independently. Final performance, gesture and
panel-regression acceptance require the single reserved physical board.

This follows `the-shell-adapts-to-output-resolution` and complements
`the-card-deck-still-misses-its-frame-budget`; it does not close their unchecked
tasks or declare HDMI hotplug/trackpad acceptance complete.
