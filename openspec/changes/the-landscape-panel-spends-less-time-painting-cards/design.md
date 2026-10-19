## Context

Userspace: Sway/wlroots/Pixman. Baseline runtime source29fe458c, system identity
and paired traces are committed under docs/evidence/coherent-shell/motion-2026-10-19/.
The existing rotate-once renderer is already enabled for the landscape panel;
its current output-turn pass allocates a fresh full-frame scratch image and
forces a full logical redraw. The22–23ms build cost is not yet attributed to
that allocation, painting or final rotation individually.

## Goals / Non-Goals

Goals: attribute the measured cost, remove the proved redundant work and
preserve exact visual/lifetime behavior. Follow proposal.md for scope.
No speculative GPU/kernel work or modification of the portrait HDMI gates.

## Decisions

1. Profile the installed code first using existing bounded draw and output-turn
   diagnostics and the same persistent native-input workload. Separate texture
   draws, final rotation, scene preparation and commit; retain unmapped remainder
   and observer overhead. If caps expire before the workload, capture a smaller
   explicitly diagnostic run or extend only bounded instrumentation.
2. Select the smallest fix supported by that profile. Candidate boundaries are
   repeated scratch allocation/initialization, unnecessary full redraw, repeated
   scaling, or the measured final rotation. Do not cache live client pixels
   without invalidation. A retained output scratch must be bound to its actual
   buffer, dimensions, format and transform and invalidate after failure/change.
3. Keep the baseline available and compare identical workloads with all work
   counted. Native tests compare pixels for transforms/crops/scale/alpha/clips,
   damage across multiple frames/buffers and changing client content; exercise
   allocation failure and buffer teardown if their ownership changes.
4. Use the frozen motion schema and budgets unchanged. Build the exact source,
   install via recoverable userspace/boot bundle procedure, record running store
   identity, repeat full/reduced traces and camera, then restore normal mode/Home.

Rejected: blaming all build CPU on Pixman sampling from coarse totals; hiding
wallpaper/rounding, freezing client content, lower resolution, or changing
thresholds after measurement. Those would not fix the authorized workload.

## Risks / Trade-offs

- Retained state can leave stale pixels → explicit buffer/geometry invalidation
  plus native multi-frame and actual changing-client tests.
- Partial redraw can miss prior buffer contents → prove damage ownership before
  enabling it; retain full redraw when correctness is unproved.
- Instrumentation can change cost → label profiling separately and compare
  qualifying runs with equivalent diagnostics/settings.
- Camera sampling misses physical refreshes → preserve actual PTS gaps and
  clock alignment bounds; no inferred optical-latency/every-refresh claims.

## Migration Plan

Publish this proposal early, then implement within the authorized optimization
scope. Land tested source promptly with hardware gates open. Reserve build/board
slots only during actual work. Enable a candidate by default only after its
pixel/lifetime and board gates; restore exact baseline if it regresses.
Archive only with committed complete evidence, sync the delta through OpenSpec,
push and inspect matching CI/Pages publication.
