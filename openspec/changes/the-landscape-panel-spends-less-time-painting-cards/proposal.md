## Why

Landscape card swipes present at about 26 Hz on a 52.19 Hz panel and miss the
existing motion budgets. Actual board measurements locate 22–23 ms per frame
in scene building/painting; the operator authorized profiling and reducing
that cost after the completed motion-trace change.

## What Changes

- Subdivide the installed landscape render cost before selecting an optimization.
- Remove measured redundant paint/copy work while preserving live client pixels,
  rounded clips, output orientation, damage correctness and callbacks.
- Repeat the same full/reduced native-input workload, with board timestamps and
  concurrent camera proof, against the exact baseline and candidate identities.
- Keep numerical misses explicit; do not trade away visuals or silently lower
  resolution, refresh, card count or the frozen latency/frame/memory budgets.

Non-goals: portrait HDMI acceptance, drawer/keyboard performance checks, new
visuals, a shell rewrite, GPU/ISA/kernel work, or closing neighboring proposals.
Host correctness tests are independent; cost attribution and final acceptance
require the sole reserved board. Camera evidence is separate from native captures.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/card-shell`: measured landscape repaint optimization with explicit
  pixel/lifetime and budget gates, complementing the existing budget decision.

## Impact

Userspace wlroots/Pixman/card compositor, targeted native pixel/lifecycle tests,
Nix package integration only if required, bounded profile collection/analysis,
and committed evidence under `docs/evidence/panel-paint/`. No boot/recovery,
kernel, device-tree or radio change.
