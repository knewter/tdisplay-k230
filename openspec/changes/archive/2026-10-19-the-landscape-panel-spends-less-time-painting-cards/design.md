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

## Conversion result and remaining attribution

Source748545c0's exact unscaled opaque conversion lowers integrated build mean
to11.210ms, p95 11.828ms, while full/reduced motion still fails at26Hz. The
512/128-capped follow-up profile observes8 complete gesture passes: texture
mean7.290ms and rotation4.244ms. Exact block-transpose and tile-size experiments
are slower, so they are rejected and the current rotation remains unchanged.
A699,776-pixel draw still averages2.323ms, but geometry does not establish
its source format, mask or scaling. Add only bounded numeric identities to
the existing512 draw rows before selecting another rendering boundary.
No new logging during qualifying motion runs and no8ms render-window change.

## Opaque wallpaper producer boundary

The0eae9900 profile proves the remaining full-panel draw is unscaledARGB8888
OVER→RGB565 without an extra mask. Source lookup identifies the Rust wallpaper
producer; default/still/video frames share its draw/attachment boundary.
Direct partial-alpha blending is pixel-exact but regresses dense alpha3.5×,
so it is rejected. Instead, scan each completed frame before committing:
all255 alpha permits a full opaque region; any transparency or allocation
failure clears the region. No assumption about videos or source formats,
and no retained-opacity state across frames. Preserve pool/callback/damage/
attachment ownership. ARGB SRC conversion is exactly Pixman's RGB565 result;
ARGB OVER and all masks keep Pixman. Rebuild and repeat the frozen paired
motion workload before any default selection; camera gate remains open.

## Buffer-owned logical output and actual damage

Theed45dc69 trial confirms the wallpaper SRC path and build CPU9.970ms mean,
10.817ms p95, but still26Hz/failed budgets. The original design's retained
output-scratch option is now selected to remove forced whole-frame work.
Each Pixman physical-buffer wrapper owns exactly one logical image keyed by
geometry, format and output transform. A begin operation consumes the valid
flag; only a successful submission restores it. Ordinary/cursor/debug passes,
failed/interrupted draws, allocation/image failure and key changes invalidate.
Buffer destruction frees the image/data; the pass only borrows it under the
existing buffer lock. No live-client/callback/attachment ownership changes.

The scene damage ring remains physical and keeps its existing buffer-age
accounting. Convert its aged region through the exact inverse of the final
copy into logical coordinates. Fresh/invalid images require a whole repaint.
Accumulate actual clipped draw rectangles and rotate only those source pixels;
keep unchanged target pixels and padding. Preserve stock fallback when output
turn is unavailable. Bound supplemental damage logging by the existing128
rotation rows and the diagnostic draw flag; qualifying runs add no new logs.

Native proof uses the production mapping/copy/cache helpers: three physical
buffers,16 geometry/format/transform cases,352 compared compositions with
moving rounded/alpha-changing content and a disjoint clock update. It covers
failed/interrupted passes, ordinary fallback, transform changes, wrapper
recreation, empty/outside damage, allocation/image failure and balanced frees.
The full288 guarded copy cases,1152 affine comparisons and288 rounded cases
remain required. Exact-source build, quiet paired timing, changing live clients
and camera still gate persistence/archive; no host result substitutes for them.

## Immutable opaque interiors without quantized edges

Source2636ea7c correctly reuses logical output images but still has build p95
8.705ms/failed motion. The profile identifies1.492ms of repeated XRGB interior
conversion. Add an optionalRGB565 plane to the existing immutable scaled-buffer
owner, on its second cache request. Charge canonical+auxiliary bytes to the
same8MiB limit; constructor/registration failure keeps the canonical path.
New source commits retain the current per-commit invalidation/freshness and
receive fresh buffer ownership. Cache requests are not presentation counts.

The producer owns both allocations. A local wlroots addon owns only a Pixman
view, destroyed by buffer_finish before producer pixels are freed. No extra
client lock/callback ownership. Both package variants provide the API; the
adapter prepares it only on eligible rotatedRGB565 output. Unscaled unmasked
XRGB interiors may copyRGB565 rows. All corner/global-alpha masks, ARGB,
scaling/transforms, other destinations and geometry/format mismatches keep
original full precision. Native512 cases/32 sensitivity sentinels prove the
previous rounded-corner quantization regression cannot silently return.

Select paired32-bit constructor stores and8-byte row alignment from actual
board measurements; the64-bit constructor was slower and is rejected. Isolated
hot copies improve about6× with pixel equality, while observed2.3–2.4ms setup
is explicitly counted by the next frozen end-to-end trial. Preserve all failed
prior budgets. No new ISA,8ms render-window change, content cap or optical waiver.
