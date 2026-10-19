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

## First integrated decision

Source08cf4516 lowered build CPU to16.506ms mean/17.521ms p95, but the same
full/reduced traces still failed timing budgets at26Hz. The persistent system
was not changed and the baseline was restored. The8ms anti-flicker render
window stays in place. Remaining repeated scaling is addressed with a bounded
full-precision opaque cache on the proven logical-composition path. Native
oracles reject RGB565 pre-quantization at rounded edges; XRGB8888 cached
intermediates preserve those pixels. Partial clips use a cached subrectangle,
quality changes invalidate the cache, and landscape client commits always
invalidate (no new15fps content cap). The original scene-surface/callback
ownership and8MiB global cache bound are retained. Software-cursor/debug
frames fall back to the direct path. See copy-only trial evidence for failures.

## Alpha eligibility correction

The sourcef1c70977 board trial recorded zero cache use: Foot suppliesARGB8888,
which the opaque-only guard rejected. Its small build-CPU difference is not
attributed to caching. The next cache path retains premultiplied alpha in an
ARGB8888 intermediate for those buffers, with exact native output comparisons
before enabling it. XRGB8888/RGB565 sources keep their full-precision path;
normal-output RGB565-cache eligibility stays unchanged. No wrapper bypass is
needed: pinned wlroots client buffers forward SHM/data-pointer access.

## Active cache outcome and opacity certificate

The24b2a03d trial records4,736 cache hits/42misses/zero fallbacks but still
fails timing budgets at26Hz; cache activation alone is not success. The next
correction scans the freshly generated ARGB cache, excluding padding. Only
all-255 alpha may be represented asXRGB, enabling existing opaque-region
culling andSRC compositing. No pixels are changed, no source alpha is assumed
opaque, and every new source generation repeats the certificate. Native
fixtures cover opaque→transparent→opaque transitions; rounded corners retain
their geometric mask. Cache-alpha counters separately expose certificates
and retained-alpha allocations. A new integrated trial is mandatory.
