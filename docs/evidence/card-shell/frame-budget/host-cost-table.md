# Where the per-frame time goes: a host measurement, not an inference

For `openspec/changes/the-card-deck-still-misses-its-frame-budget`, authorized
2026-09-28 ("frame budget go"). This is a host measurement (the real
cross-built RISC-V compositor under QEMU user-mode emulation, the existing
`tests/card_shell_runtime.py --benchmark` harness) plus one new,
board-reusable diagnostic: a per-frame damage-extent row. It changes no
visual behavior; the one production-affecting finding it surfaces (the
scaled-cache path) is reported, not silently patched, because removing it
would drop a requirement (the capped live-preview rate) this change must
preserve.

## New instrumentation

`nix/card-shell/telemetry.c`'s `card_bench_render_damage()` (declared in
`telemetry.h`) logs the exact region `wlr_scene_output_build_state` computed
for the frame, via `sway/desktop/output.c` reading `pending.damage` right
after a successful build (`nix/patches/sway-k230-card-shell.patch`). It emits
a `K230_CARD_SHELL frame-damage run=... frame_id=... rects=N damage_px=N
bbox_x1=.. bbox_y1=.. bbox_x2=.. bbox_y2=.. output_w=.. output_h=..` row --
deliberately **not** a `K230_CARD_BENCH v=1 event=...` row, since
`tools/card-shell-benchmark.py`'s `parse_rows` raises on any event name
outside its fixed `FIELDS` whitelist and this diagnostic must never break
that existing strict acceptance parse. It costs nothing when `card_bench_arm`
was never called (the `bench.armed` guard already every other diagnostic
here uses).

## Method

Cross-built package: `nix build .#card-shell --max-jobs 1 --cores 6
--no-link --print-out-paths` -> `/nix/store/17y4la6qcjcj8b73z6k97mqj4n10rsk4-k230-card-shell`
(sway-unwrapped `/nix/store/crnmkgfahs0v3xzxn8rq60lzfz8qh1hj-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`).
Client: `nix build .#card-composition-probe` ->
`/nix/store/ycqmry86px8micsk8vnx1g0zbd61vawz-k230-card-composition-probe`.

```sh
python3 tests/card_shell_runtime.py --native-touch --benchmark --delayed-touch \
  --sway /nix/store/crnmkgfahs0v3xzxn8rq60lzfz8qh1hj-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/ycqmry86px8micsk8vnx1g0zbd61vawz-k230-card-composition-probe/bin/card-composition-probe-client \
  --output <dir>
```

All 17 native-input headless checks passed in every run cited here
(`horizontal-live-deck`, `expand-focus-keyboard`, `three-dynamic-views`,
`clean-compositor-teardown`, ... -- the full list `repaint-stages/README.md`
already documents). One run of several hit the harness's own
`k230.card.one`/`k230.card.two` frame-advance assertion
(`tests/card_shell_runtime.py:560`) under this machine's current load
(`uptime` showed a load average of 63 on 32 cores from unrelated concurrent
work -- multiple agents share this host per `AGENTS.md`); two immediate
retries of the identical binary/flags passed cleanly, and the same assertion
never failed against the **other** build in this investigation, so this is
recorded as host-machine contention, not a regression, per the "does every
frame damage" scope of this change -- it does not bear on a hardware timing
claim, and this is a host-only diagnostic, not board acceptance evidence.
`K230_CARD_SHELL frame-cost`/`repaint-cost`/`frame-damage` rows were parsed
directly from `sway.log`; the full raw logs are not committed (each is
several MB and QEMU-user timing on a shared host is not a page of evidence
in the sense `docs/evidence/` requires -- the board capture already
committed in this directory is the timing evidence of record). The numbers
below reproduce to within noise across three independent runs of the final
build.

## Ranked host cost table (105 submitted frames, single-output benchmark)

| Stage | Share of render CPU | p50 | p90 | p95 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Build** (`wlr_scene_output_build_state`: scene config, card prepare already counted separately below, Pixman composite) | 94.9% | 28.12 ms | 29.63 ms | 29.98 ms | 31.27 ms |
| **Prepare** (`card_shell_prepare`: `sync_scene`/`sync_card`, label/plate/icon cache checks, appearance-canvas refresh, home/backdrop self-heal) | 4.6% | 1.36 ms | -- | -- | 2.96 ms |
| **Commit** (`wlr_output_commit_state` CPU only -- headless backend, so this excludes any DRM register write/vblank wait; **not** comparable to the board's `canaan_crtc_atomic_flush` cost) | 0.5% | 0.08 ms | -- | -- | 7.10 ms (one outlier attempt) |

Total render CPU: p50 29.56 ms, p95 31.68 ms, max 32.73 ms -- for reference,
the board's own `repaint-stages/README.md` capture (real hardware, normal
kernel) measured Build CPU p95 14.00 ms (one card) / 19.79 ms (two cards),
i.e. **this host run is 1.5-2.1x slower than the board** for the same
diagnostic stage. QEMU user-mode emulation of the RISC-V binary on this x86
host is not free, and does not obviously accelerate the RVV paths the same
way real silicon does; treat any host number here as ordering information
(which stage dominates, which change helps or hurts) rather than a
board-cost predictor. State the multiplier this way -- **host ≈ 1.5-2x board
build time on this workload** -- rather than assuming host is a cheap stand-in
for a faster board.

## Damage extent: does every frame damage the full output?

Effectively yes, during any card-shell motion -- not because damage tracking
is broken, but because the webOS-fan deck layout moves most on-screen cards
at once. Across 486 `frame-damage` rows in one run:

| Phase | Damage as % of 568x1232 output | rects |
| --- | ---: | ---: |
| Outside the overview (single live app, its own commits) | 76.3% (constant, same bbox every frame -- this is the app's own repaint, not card-shell's) | 3 |
| `CS_ENTERING` transition start | up to 99.6% | 3 |
| Settled `CS_DECK` browsing | 76-82% (p50 81.5%, max 97.0% across the 105 frames paired with a repaint-cost row) | 5-13 |

The one clean counter-example (`frame_id=217`, 6.6% damage, 4.18 ms build)
confirms damage tracking itself is working -- when a change really is small,
the composited region really is small. During deck browsing it almost never
is: `cs_card_rect`'s webOS-fan layout keeps several cards visible and moving
together, so the union of old+new rects for one frame typically spans nearly
the whole usable deck viewport (`clip_box()`, i.e. the panel minus the title
and footer bars). **This is inherent to the current visual design, not a
damage-tracking defect**, and the task's own constraint ("without changing
visuals or gesture feel") forecloses shrinking it further without redesigning
the deck layout itself (out of scope; not proposed here).

## Candidate wins already implemented (verified by reading, not assumed)

Every code-level candidate this change's task list names was already present
before this investigation, from prior rounds cited in `proposal.md`'s "Why":

- **Damage-limited rendering**: the wlroots scene graph's own damage tracking
  (unchanged, no defect found -- see above).
- **Avoid re-clip/re-scale of unchanged cards**: `label_update` (exact
  text/size match), `card_background` (brush/size/radius `memcmp`), and
  `appearance_canvas_refresh` (generation/size/brush `memcmp`, plus a
  prepare-time warm path, `nix/card-shell/adapter.c:429-518`) all already
  skip rebuilding when nothing changed.
- **Cache each card's rounded, scaled result as a buffer**: this exists
  (`scaled_mirror`/`card_scaled_buffer_create`, `nix/card-shell/adapter.c:
  1014-1084` and `render.c:47-75`) gated by `SWAY_K230_CARD_SCALED_CACHE`.
  See the negative result below -- it exists, and measurably does not help
  this workload.
- **Skip scene sync when geometry is unchanged**: `card_shell_prepare` runs
  `sync_scene()` unconditionally on every output repaint by design --
  `adapter.c:2445-2454`'s own comment explains why (an unrelated Sway focus
  change was observed to silently re-enable the Home layer underneath the
  overview if this self-healing sync ever stopped running every frame; see
  `docs/evidence/card-shell/bottom-band-flicker/hypotheses.md`). Skipping it
  would reopen that fixed bug. Its cost is 4.6% of render CPU regardless
  (measured above), so skipping it would not have moved the dominant Build
  stage either.
- **Reduce allocations per frame**: `scaled_mirror`'s own cache buffer is
  swapped via `wlr_buffer_drop`/`wlr_buffer_init` per miss; the old buffer's
  scene-graph reference (`copy->buffer`, dropped only inside the later
  `wlr_scene_buffer_set_buffer` call in the same function) outlives the
  mirror's own reference, so reusing its backing allocation in place would
  require restructuring buffer lifetime tracking this investigation judged
  too risky to land unverified on hardware within this task's scope.

## Negative result: the scaled-cache path measurably does not help here

`SWAY_K230_CARD_SCALED_CACHE=1` is set unconditionally in `nix/shell.nix`
(the real production image). Toggling it in this same benchmark:

| Config | Build p50 | Build p90 | Build p95 | Build max |
| --- | ---: | ---: | ---: | ---: |
| Off (default RGB, no scaled-cache) | 28.12 ms | 29.63 ms | 29.98 ms | 31.27 ms |
| On (`--scaled-cache --rgb565`, matching the board's real format) | 30.57 ms | 33.26 ms | 33.62 ms | 34.71 ms |

Cache stats for the "on" run: `hits=1863 misses=337 fallbacks=3072` --
fallbacks (the exact same code path as "off") outnumber hits+misses more
than 1.4:1, so most of the time this workload pays the cache's own
eligibility checks and still runs the plain path underneath, and the
eligible fraction does not recoup that cost. This reproduces the parent
proposal's own historical note ("unchanged by ... a scaled-cache mirror path
(on or off)") with a clean before/after on host.

**This is not proposed as a fix here.** `scaled_mirror`'s 66 ms/~15fps
live-preview throttle (`adapter.c:1044-1056`) exists *only* inside this same
code path -- disabling `SWAY_K230_CARD_SCALED_CACHE` would also remove the
capped live-preview rate this change's own task explicitly requires
preserving. The two are currently coupled in one function; decoupling them
(keep the rate cap, drop the pixel-cache path that this measurement shows is
net-negative for Build cost) is a real, bounded follow-up, but it touches the
same function `card_shown_large`/`scene_in_motion` rely on and was judged too
large to land inside this task without a board round to confirm the
live-preview cap still holds -- left for the coordinator as an explicit,
evidence-backed option rather than silently folded in here.

## What this does and does not resolve

This confirms (from the host side) what `analysis.md`'s board capture already
established from the hardware side: the CPU-side, damage-side and cache-side
levers this change's task list names are already implemented, and the
remaining Build cost is dominated by a large, largely fixed composited area
inherent to the current webOS-fan visual design -- not by an avoidable
inefficiency this investigation could find and fix without either changing
visuals (forbidden by this task) or touching the kernel commit path (see
`commit-pipelining-assessment.md`).
