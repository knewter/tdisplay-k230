# Draw less per frame: motion-time filtering on the live-mirror composite

For `perf/deck-draw-less`, continuing
`openspec/changes/the-card-deck-still-misses-its-frame-budget` task 4.2 with
the user-authorized option "draw less per frame" (2026-09-28, "yeah work on
the card overview smoothness"). Host measurement only (`tests/card_shell_runtime.py
--benchmark` under QEMU user-mode emulation); no board access, per this
task's own instructions.

## What was tried and rejected first (recorded, not silently dropped)

**Approach: give the live mirror's real opaque region to the Pixman renderer
instead of forcing it empty every frame**, so a rounded card's fully-opaque
interior (everything but the four corner squares, which `rounded-clip.h`'s
`k230_round_composite` always alpha-blends via a hardcoded `PIXMAN_OP_OVER`
regardless of the caller's `op`) could take Pixman's `PIXMAN_OP_SRC` fast
path instead of `PIXMAN_OP_OVER`. `nix/card-shell/adapter.c`'s `sync_node`
unconditionally calls `wlr_scene_buffer_set_opaque_region(copy, &empty)` on
every mirror, every frame; the patched wlroots's own `scene_buffer_clip_opaque`
(`nix/patches/wlroots-k230-rounded-clip.patch`) already conservatively
excludes the rounded corners from any declared opaque region for occlusion
culling, but the *render-time* blend-mode decision in `scene_entry_render`
folds the corners' non-opacity into the whole node's blend choice, so a
moving card's corners (almost always inside the frame's damage region while
animating) forced `PIXMAN_OP_OVER` for the ~95% interior too.

A wlroots patch hunk implementing this (restrict the render-time opacity
check to the interior cross before the corner-disqualification, since
corners are masked correctly regardless of the chosen op) was written,
applied cleanly (`patch -p1`, zero fuzz, verified against the pinned
`wlroots_0_20` source before touching the real patch file), and built
successfully (`nix build .#card-shell`). **Measured with four alternating
before/after pairs on the same host in the same few minutes (to cancel the
shared host's load drift, not just separate runs): no reproducible win.**
Build p50 moved from a 3-pair average of 26.31 ms to 26.98 ms (about 2.5%
*worse*), p95 from 29.58 ms to 29.91 ms -- within this host's own run-to-run
noise band, not a real signal. The patch was reverted
(`git checkout -- nix/patches/wlroots-k230-rounded-clip.patch`) rather than
kept on a hoped-for board result; per this task's own instruction, only
changes that measurably help are kept. Plausible reason: Pixman's `OVER`
path for an opaque (no-alpha-channel) source with no mask may already be
close to as fast as `SRC` in this pixman version, and the extra
`pixman_region32` bookkeeping this approach added per card per frame roughly
cancelled whatever it saved.

## What was tried and kept: nearest filtering while a card is in motion

`card_scaled_buffer_create`'s own `fast` parameter (`nix/card-shell/render.c`)
already trades bilinear for nearest-neighbor resampling while
`scene_in_motion()` is true, but only inside the RGB565 scaled-cache path
(`SWAY_K230_CARD_SCALED_CACHE=1`). The *other* path -- `sync_node`'s direct
mirror composite, which `host-cost-table.md` already measured as the
majority path in this exact workload (fallbacks outnumbering
hits+misses 1.4:1) -- hardcoded
`wlr_scene_buffer_set_filter_mode(copy, WLR_SCALE_FILTER_BILINEAR)`
unconditionally, every frame, regardless of motion. Bilinear resamples four
source texels per destination pixel; nearest reads one. Every card in the
deck view is a *scaled-down* live mirror of a full-panel app buffer, so this
filter runs on nearly every composited pixel, every frame.

**Change** (`nix/card-shell/adapter.c`, `sync_node`): filter mode is now
`scene_in_motion() ? WLR_SCALE_FILTER_NEAREST : WLR_SCALE_FILTER_BILINEAR`,
mirroring the scaled-cache path's own existing trade instead of introducing
a new one. A card is shown at full bilinear quality the instant motion stops
(drag released, entry/expand/close settled); nothing changes at rest, so
this is a no-op for the "no visible quality loss at rest" requirement by
construction -- rest was never touched.

## Method

Cross-built package: `nix build .#card-shell --max-jobs 1 --cores 6
--no-link --print-out-paths`. Before:
`/nix/store/17y4la6qcjcj8b73z6k97mqj4n10rsk4-k230-card-shell` (unchanged from
`host-cost-table.md`, confirming a clean baseline); sway-unwrapped
`/nix/store/crnmkgfahs0v3xzxn8rq60lzfz8qh1hj-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.
After (final, with the filter-mode change plus its own telemetry):
`/nix/store/gqc5r6nfg55dgnqi82a8wzv5byx2pjwg-k230-card-shell`; sway-unwrapped
`/nix/store/kkqy1m0fvlxv39qagkd0g5jspianyfgg-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.
Client (unchanged): `/nix/store/ycqmry86px8micsk8vnx1g0zbd61vawz-k230-card-composition-probe`.

```sh
python3 tests/card_shell_runtime.py --native-touch --benchmark --delayed-touch \
  --sway <sway-unwrapped>/bin/sway \
  --client /nix/store/ycqmry86px8micsk8vnx1g0zbd61vawz-k230-card-composition-probe/bin/card-composition-probe-client \
  --output <dir>
```

`K230_CARD_SHELL repaint-cost` rows parsed directly from `sway.log`
(`build_cpu_ns`/`prepare_cpu_ns`/`commit_cpu_ns`), same method as
`host-cost-table.md`. This host is shared by concurrent agents per
`AGENTS.md`; load average during this work ranged 34-38 on a many-core box,
which is why absolute numbers vary run to run far more than
`host-cost-table.md`'s original session did. Before/after pairs below were
run **alternating** (before, then after, immediately) specifically to
cancel that drift, not as separately-timed batches.

## Host Build-stage cost, before/after (ms)

| Pair | Config | n | p50 | p90 | p95 | max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | Before | 105 | 18.26 | 21.83 | 23.30 | 24.87 |
| 1 | After | 1* | 6.75 | 6.75 | 6.75 | 6.75 |
| 2 | Before | 1* | 17.89 | 17.89 | 17.89 | 17.89 |
| 2 | After | 106 | 9.42 | 10.85 | 11.14 | 28.22 |
| 3 | Before | 105 | 29.16 | 30.11 | 30.47 | 31.59 |
| 3 | After | 106 | 9.39 | 10.57 | 10.76 | 28.89 |

\* Two runs (pair 1 after, pair 2 before) logged only a single
`repaint-cost` row instead of the usual ~105 -- the harness's own drag
window elapsed while this specific QEMU process was starved of host CPU
(load average 34-38 during this session; `AGENTS.md`: several agents share
this host). Not a code defect: `clean-compositor-teardown` and all other
native checks still passed in every run, and this was purely a wall-clock
window that closed before the emulator produced more frames. Kept for
honesty rather than discarded, but treated as unreliable single-sample
data, not averaged into the headline numbers below.

Using only the four pairs with a full ~105-sample side on **both** ends
across this and an earlier (pre-telemetry-instrumentation) measurement pass:

| Config | Build p50 | Build p95 |
| --- | ---: | ---: |
| Before (4 full runs: 18.26, 26.15, 28.61, 29.16) | mean 25.55 ms | mean (23.30,31.48,30.60,30.47) 28.96 ms |
| After (4 full runs: 8.18, 9.19, 9.39, 9.42) | mean 9.05 ms | mean (11.44,11.54,10.76,11.14) 11.22 ms |

**Build p50 drops about 65%, p95 about 61%, consistently across every
full-sample run.** `host-cost-table.md`'s own board multiplier
(host ≈ 1.5-2x board Build time on this workload) would put this at roughly
board Build p50 ≈4.5-6ms, p95 ≈5.6-7.5ms if the reduction transfers
proportionally -- **UNVERIFIED**, a board run is required to confirm; the
mechanism (fewer texels read/blended per pixel) is architecture-independent,
but the proportion is not assumed to carry over exactly.

## Visual-regression checks

- `python3 -m pytest tests/test_card_rounded_clip.py tests/test_card_scaled_cache.py tests/test_card_shell_state.py -q`:
  **38 passed** (host pixel oracle unaffected -- rounded-clip masking itself
  was not touched, only the interior's resampling filter).
- `tests/card_rounded_clip_qemu.py` against the final build, both
  `--cache 1` and `--cache 0`: **both PASS**. Wallpaper still exactly matches
  baseline at all eight rounded-corner sample points; live card pixels still
  change between captures; `render_format: RG16` confirmed. Visually
  reviewed `drag-held.png` and `entry-held.png` (both captured mid-gesture,
  i.e. while nearest filtering is active): rounding intact, no missing or
  stale regions, no corruption -- content is visibly blockier under nearest
  during motion, which is the accepted trade this task's own "Motion-time
  quality" approach authorizes.
- New: `tests/test_card_shell_motion_filter_runtime.py` runs the actual
  drag/entry/expand benchmark session and asserts the new
  `K230_CARD_SHELL filter-mode nearest=N bilinear=M` telemetry row (added to
  `nix/card-shell/adapter.c`, logged at session close and every 60 ticks
  like the existing `scaled-cache` line) shows **both** N>0 and M>0 in one
  session -- guards against the conditional silently taking only one branch
  for this workload. Passed.
- All 17 native-input headless checks in `tests/card_shell_runtime.py`'s own
  acceptance list still pass on every run cited above, including
  `clean-compositor-teardown`.

## System build

```sh
nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel \
  --max-jobs 1 --cores 6 --no-link --print-out-paths
```
`/nix/store/8ygar1sgyb7wj4avhiz3zjy75i80m0dp-nixos-system-nixos-26.11.20260919.20b1ddd`

`openspec validate --all --strict`: 57 passed, 0 failed.
`python3 scripts/render_work_board.py`: exits 0 (62 items).
`python3 tools/blob-scan.py`: ok, every binary accounted for.

## Board commands for the coordinator

Same pass criterion as `board-commands.md`: tracking-presentation p95 at or
below 2 vblank periods (38.3 ms), ideally 1 period (19.16 ms), during a deck
drag.

```sh
nix build .#card-shell --max-jobs 1 --cores 1 --no-link --print-out-paths
# push the resulting sway/card-shell binaries and run the acceptance workload
# exactly as docs/evidence/card-shell/board-cost/long-trace/README.md does, then:
python3 tools/card-shell-benchmark.py --board \
  --input <telemetry from the board run> \
  --output docs/evidence/card-shell/frame-budget/pixman-motion-filter-<date>.json
```

Re-run `tools/measure-panel-refresh.sh`'s idle/drag captures
(`board-commands.md` section 2) immediately after, to confirm raw hardware
vblank is still the clean 19.16 ms grid `board-result-2026-09-28.md`
established (it should be -- this change touches only the card-shell
Pixman composite, not the kernel or DRM path).

Decision after the capture:
- `tracking_present_interval_ms` p95 now at or below 38.3 ms (2x), especially
  if at or below 19.16 ms (1x): task 4.2 passes; proceed to task 5.1.
- Still above 38.3 ms p95 but visibly improved: record the new number next
  to `board-result-2026-09-28.md`'s ~57.5 ms and reopen whether commit
  pipelining (`commit-pipelining-assessment.md`) is now worth its
  known boot-panic risk, informed by a smaller remaining gap.
- No change from `board-result-2026-09-28.md`: something about this
  workload's card format/eligibility differs from the board's real
  apps -- check `K230_CARD_SHELL filter-mode` counts in the board log; if
  `nearest` never increments, `scene_in_motion()` was never true for the
  captured window (the drag was too brief or already settled at capture).

## What this does not resolve

- Not measured or claimed here: real-finger feel, presentation-feedback
  timing, or anything about the compositor's commit cadence (H1 in
  `analysis.md`) -- this is a Build-stage CPU cost reduction only. If the
  ~57 ms tail is dominated by commit-path serialization rather than render
  cost (as `analysis.md` itself argues is likely for the *tail*), a large
  Build-cost win may still leave the presentation p95 short of budget; only
  a board capture can say.
- The static-backdrop-layer and pre-composed-card-buffer approaches (this
  task's options 1 and 2) were not attempted: once the motion-time filter
  win was found and measured this large, further host time went to
  confirming it (repeat runs, visual checks, system build) rather than
  layering more changes before any of them has board proof. Left as
  further options if board measurement shows the budget still isn't met.
