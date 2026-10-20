# Landscape paint attribution and candidate — 2026-10-19

The installed landscape compositor spends about **10.8 ms per frame in final
RGB565 rotation**, in addition to about **12 ms in texture draws**. This
selects the final-copy loop for the first bounded optimization. A standalone
on-board comparison copies identical pixels into **unattached** DRM dumb
buffers: baseline10.130 ms, candidate4.109 ms for the panel's actual copy
rotation. The later [copy-only integrated trial](candidate-copy-only/README.md)
reduced build CPU but still failed latency/frame budgets. The board/camera/
default-selection tasks remain open.

## Identities and workload

- Worktree `.claude/worktrees/panel-paint`, branch `perf/panel-paint`, base
  `26c4da44905153683a9e13bbecbb151c65fae0d5`.
- Published proposal `c6bdfda34f40c45d80f90eab1cc00f8c1fd00740`; CI39337441474
  succeeded and exact revision/proposal presence was verified at
  <https://knewter.github.io/tdisplay-k230/work/>.
- Installed baseline source `29fe458cc4044cb5095e6aeb5fc84b4fdfb3d931`, system
  `/nix/store/48afqvxz6i15rz9q4if3b1c08j6l3n37-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Same native landscape panel: transform270, logical1232×568, physical568×1232,
  nominal52.19Hz, Pixman. The actual session and rotation rows say **RGB565**.
  Earlier motion READMEs incorrectly said XRGB8888; their labels are corrected
  without changing the source telemetry or recorded timing results.
- Runtime flags: `WLR_PIXMAN_OUTPUT_TURN=1`, `WLR_PIXMAN_QUARTER_TURN=0`;
  diagnostic-only `WLR_PIXMAN_DRAW_TRACE=1` in one owned runtime override,
  with an independent180-second restoration watchdog.
- Full-motion run `85990710516561`, three cards, three alternating gestures,
 35 moves over700ms each and800ms settling. Same persistent native uinput
  injector as the motion proof; no per-event process-spawn timing.
  This is an explicitly smaller **diagnostic** workload, not the qualifying
  six-gesture full/reduced acceptance pair.
- [baseline/workload.json](baseline/workload.json) records each contact and
  actual output state; [baseline/telemetry.log](baseline/telemetry.log) is the
  bounded normalized benchmark/motion output. No camera was used for profiling.

## Attribution and observer limits

[baseline/profile-metadata.json](baseline/profile-metadata.json) records the
running system/PID and whitelisted runtime flags. [baseline/profile.log](baseline/profile.log)
contains numeric-only draw and final-rotation fields. It was collected only
from that compositor PID, using journal receipt monotonic timestamps.
These times group same-process log order; they are not exact commit IDs or
input-to-photon observations.

| Selected gesture window | Samples | Mean CPU | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Final rotation | 65 | 10.755ms | 10.748ms | 10.982ms |
| Grouped texture draws per completed observed pass | 44 | 12.728ms | 11.724ms | 12.332ms |
| Final rotation in those same passes | 44 | 10.781ms | 10.752ms | 11.001ms |

The512-row texture cap was reached; the128-row rotation cap was not (89 total
rotation rows including setup). Rows after the texture cap are not grouped
as complete frames. Texture timers omit solid rectangles, scene preparation
and output commit. Logging/observer overhead is not subtracted. This is
partial diagnostic attribution, not a new total-frame budget measurement.
The earlier non-draw-logged paired trace remains the baseline performance
acceptance data. [baseline/profile.json](baseline/profile.json) retains all
samples/counts and the `PARTIAL` status.

Exact analyzer command:

```sh
python3 tools/panel-paint-profile.py \
  --log docs/evidence/panel-paint/baseline/profile.log \
  --workload docs/evidence/panel-paint/baseline/workload.json \
  --output docs/evidence/panel-paint/baseline/profile.json
```

Result0; four host parser checks also pass via `--self-test`. The collector
[sources/collect-paint-profile.py.txt](sources/collect-paint-profile.py.txt)
accepts only the fixed draw/rotation grammar and numeric dimensions/costs;
it does not export arbitrary journal text. Collection/mode/workload scripts
retain their historical scratch/store paths and are records of execution,
not portable installed commands.

## Selected copy and standalone board comparison

The existing16×16 tiled loop writes individual16-bit pixels into separated
destination rows. The candidate walks contiguous destination runs within
source tiles and combines four fresh RGB565 pixels in one naturally aligned
64-bit store. Scalar prefixes/tails handle odd geometry and padding. It does
not cache image contents, change interpolation, add new CPU ISA requirements,
retain output state or modify callback/buffer ownership. The32-bit copy keeps
its established loop after the initial pair-packing prototype regressed it.

[sources/candidate-quarter-turn.h.txt](sources/candidate-quarter-turn.h.txt)
is the exact candidate header; [sources/baseline-turn.h.txt](sources/baseline-turn.h.txt)
is the baseline function extracted from base26c4da44. The executable compiled
both into the same binary with GCC15.3.0, `-O2`, without new ISA flags.
The first attempted GCC15.2 executable referenced a loader absent on the
board and did not run; it was rebuilt with the installed toolchain generation.

The benchmark creates source patterns and fresh heap or DRM dumb targets.
The DRM target is **never attached to an output**, and no master/modeset is
requested; it is mapped, copied, byte-compared, unmapped and destroyed.
For each format/rotation it alternates baseline/candidate order across three
rounds,12 copies per timed round after a warm copy. The table is the median
per-copy process CPU across the three rounds, not an application frame cost.

| Target | Bytes/pixel | Rotation | Baseline | Candidate |
| --- | ---: | ---: | ---: | ---: |
| Heap | 2 | 1 | 10.125ms | 4.115ms |
| Heap | 2 | 3 | 8.574ms | 4.042ms |
| DRM dumb | 2 | 1 | 10.130ms | 4.109ms |
| DRM dumb | 2 | 3 | 8.507ms | 4.066ms |
| Heap | 4 | 1 | 13.117ms | 12.618ms |
| Heap | 4 | 3 | 11.751ms | 11.781ms |
| DRM dumb | 4 | 1 | 12.457ms | 11.990ms |
| DRM dumb | 4 | 3 | 11.140ms | 11.172ms |

Both formats and rotations pass byte equality including row padding.
The retained32-bit results are essentially unchanged; small differences
are not a claimed improvement. Full source, compile command, raw CPU/wall
samples, binary hash and timestamps are in
[copy-microbenchmark/](copy-microbenchmark/) and [sources/hashes.json](sources/hashes.json).
Heap/copy timing and an unattached buffer do not prove scanout behavior.
No frequency-normalized claim or end-to-end performance improvement is made.

## Native correctness and restoration

Commands/results:

```text
python3 tools/panel-paint-profile.py --self-test: 4 passed
python3 tests/test_panel_paint.py: 288 guarded multi-frame cases passed (UBSan)
python3 tests/test_pixman_quarter_turn.py: 1152 exact affine pixel comparisons passed
python3 tests/test_card_rounded_clip.py: 288 rounded-clip pixel comparisons passed
```

The new guarded fixture covers both turns/formats, odd and native dimensions,
4/8-byte alignment, row padding, three successive changed source patterns,
allocation guards and invalid/overlapping inputs. Existing fixtures retain
crop/scale/filter/alpha/rounded-clip/damage checks.

After diagnostic logging, the owned profile override was removed and the
normal shell/UI restarted. The first workload attempt had hit a transient
Rust hide-route timeout after restart; the later run is the recorded one.
[baseline/restored.json](baseline/restored.json) confirms normal motion,
active shell/UI, no virtual test device and Home navigation. Both board
reservations (profile and standalone copy) were released. No integrated
candidate has been installed, no camera proof or reboot claimed here.

## Remaining gates

Build/install the exact candidate, repeat the six-gesture full/reduced
performance pair and cost profile, test changing live app content/callbacks,
and record concurrent camera-visible motion with the actual capture limits.
Keep the native pixels, resolution, card count and frozen motion budgets.
Require p95 build CPU within19.161ms and the existing latency/frame/memory
gates; retain any failures as failures. Default selection and archival stay
open pending those named proofs.

## Follow-up selected after the integrated result

Copy-only build CPU dropped to16.506ms mean/17.521ms p95, still above the
existing8ms anti-flicker render window. The next candidate avoids repeated
resampling of unchanged opaque card content during logical composition.
RGB565 pre-scaling differed at15/18 rounded-edge pixels in a diagnostic
nearest/bilinear probe, so it is not used for the rotated output. Full-precision
XRGB8888 pre-scaling matched exactly in that probe. Production native tests
now exercise full-precision rounded/partial/rotated pixels over64 cases and
three changed source frames each. Cache keys include source generation,
geometry, pixel format and quality filter. Landscape updates invalidate on
every source commit, preserving the former uncached path's freshness rather
than adding the normal-output15fps thumbnail cap. The existing total8MiB
cache memory bound remains. Software-cursor/debug fallbacks retain the direct
path, and cropped scene fragments sample only the visible cached subrectangle.
This follow-up still requires a new exact-source build and board qualification.

The [cache eligibility trial](candidate-cache-ineligible/README.md) atsource
`f1c70977` also failed timing budgets. Its cache counters stayed atzero because
Foot usesARGB8888. The small timing difference is not a cache-gain claim. The
next version preserves premultiplied alpha in anARGB8888 intermediate rather
than treating those pixels as opaque. The pixel oracle now passes96 cases
(three sourceformats, filtering, cropping, rounding, rotation and changed
sourcecontents); normal-output RGB565 eligibility is retained.

The [active alpha-cache trial](candidate-alpha-cache/README.md) proves cache
use but still fails timing budgets and gives no build/cadence gain. The next
correction certifies all-255 cached alpha before exposing an immutable image
asXRGB; actual transparency retainsARGB. It relies on pixel contents, not
format naming or a user background setting. Native tests pass160 cached
cases, including opaque→transparent→opaque changes, plus the288 guarded
copy cases. Board acceptance remains open.

The [opaque-cache trial](candidate-opaque-cache/README.md) confirms all cached
Foot texels are opaque but still fails at26Hz. Its bounded profile selects
unscaled format conversion next. An [isolated conversion benchmark](conversion-microbenchmark/README.md)
shows3.4× lower CPU with identical pixels; integrated proof remains open.

The [integrated conversion trial](candidate-conversion/README.md) reduces full
build CPU to11.210ms mean/11.828ms p95, but both modes still fail latency at26Hz.
[Rejected rotation variants](rejected-rotation/README.md) preserve the measured
16-pixel tile. Bounded format/mask/scaling diagnostics are the next step;
geometry alone does not identify the remaining large draw. Hardware gates stay open.

[Format attribution](format-attribution/README.md) identifies the remaining
full-panel image as unscaledARGB OVER. Dense-alpha direct blending was slower
and rejected. The selected correction is a per-frame wallpaper opacity
certificate plus exact ARGB SRC conversion; transparent images retain blending.
New native/Rust tests pass; exact build and integrated acceptance remain open.

The [opaque wallpaper trial](candidate-wallpaper-opaque/README.md) reaches
9.970ms mean/10.817ms p95 build CPU and confirmsSRC compositing, but both
motion modes still fail at26Hz. The remaining forced whole-frame repaint/copy
selects buffer-owned logical images and damage-only composition/rotation.
Native three-buffer/failure tests pass; exact build and board proof remain open.

The [retained-output board trial](candidate-retained-output/README.md) proves
cache reuse and copies about433k of700k pixels per selected frame, with
7.804ms mean/8.705ms p95 build CPU. Both timing modes still fail at26Hz.
Changing main/child clients advance callbacks and releases; compositor PNGs
are committed separately from the still-missing camera proof. Repeated
conversion of immutable cached card interiors is the next measured boundary.

An [opaque-interior microbenchmark](interior-microbenchmark/README.md) selects
an optionalRGB565 representation for reused immutable card interiors, within
the existing8MiB app-cache budget. Full-precision masked edges remain exact
(512 new oracle cases and32 corner-loss sentinels). Isolated card draws fall
about6×, but setup costs and all frozen board/physical gates still need proof.

The [opaque-interior integrated trials](candidate-opaque-interior/README.md)
activate the auxiliary path and pass the exact cross-build/live-content check,
but still fail the comparable full/reduced timing pair. Earlier full passes
used a different starting card order and cannot qualify the pair. Serialized
terminal mapping now fixes setup. Mostly empty ARGB title blending is the next
measured boundary; quality,8ms guard and all hardware gates remain unchanged.

The [label-ink candidate](candidate-label-ink/README.md) builds and preserves
native pixels/live clients. After waiting for the late startup Terminal and
verifying actual selected app, full/reduced setup captures are identical.
Reduced software timing passes; full p95/p99 latency still fails. The title
falls0.399→0.059ms and full build mean6.243→5.246ms; no paired qualification or
optical claim. Rotation is the remaining largest measured stage. Baseline
restored, quality/8ms guard unchanged, camera/default/archive still open.

The [rotation scheduling experiments](rotation-batches/README.md) reject
rectangular tiles and changed traversal order, but select eight-pixel batches
with the existing disjoint-range contract. Isolated full/partial copies improve
about12%/16%; native pixels and explicit overlap rejection pass. Integrated
build/timing/live/camera/default/archive proof remains open for this source.
