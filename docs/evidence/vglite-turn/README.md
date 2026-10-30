# Standalone output-turn benchmark: CPU vs VG-Lite on the mainline board

**Evidence class: board observation, private buffers, runtime `insmod` only.**
Not compositor evidence, not an interaction or presentation measurement. Run
2026-10-30 ~14:45-15:00Z on boot `0b49504f-...`, kernel 7.3.0-rc5, boot default
`49mnsl2s...` (GPU device-tree node installed, `vglite.ko` `c07fydj8` loaded and
unloaded by each run; after each run no PLIC 135 line, no `vglite` in `lsmod`,
no Oops/BUG; shell and seatd stayed active). Charger online. Each run held the
board lock for well under a minute. The module is not loaded at boot and the
system closure is unchanged.

Program: [`nix/vglite-turn-bench.c`](../../../nix/vglite-turn-bench.c), built by
`nix build .#k230-vglite-turn-bench`, executable
`/nix/store/59vvqwy2bykb9qq4x883xpb5456pfrbd-k230-vglite-turn-bench-...` (the
earlier runs used predecessors of the same program: `chpz00d8...`, `16d7f5hc...`,
`lzywc3nyk...`; the last changes only added diagnostics and the `BENCH_NOCLEAR`
switch). It turns one full 1232x568 RGB565 frame into 568x1232. Destination is a
DRM dumb buffer created and freed by the program on `/dev/dri/card0` with the
padded 576-pixel storage width (pitch 1152), imported into VG-Lite as a dma-buf;
it is never attached to a CRTC, so it is the same kind of memory as sway's
scanout buffers but not a scanout buffer. Source is a contiguous VG-Lite
allocation (stride 2464). Reps: 40 per mode, 3 rounds, transform 1 (the
compositor's `rotation=1`) and 3.

## Correctness

The GPU turn (`vg_lite_blit`, 90 degree matrix set directly, point filter,
`VG_LITE_BGR565`) is byte-identical to the compositor's `k230_turn_copy_rect`
(`nix/card-shell/quarter-turn.h`) for both transforms: `bad_rows=0 of 1232`
(files `*-noclear*`).

## Cost per full frame (median of 12 rounds x 40 frames; `summary-passing-runs.txt`)

| Mode | wall | process CPU | of which submit / finish wait |
| --- | ---: | ---: | --- |
| CPU turn into heap | 4.38 ms | 4.01 ms | - |
| CPU turn into the dumb (scanout-like) buffer | 4.36 ms | 4.01 ms | - |
| GPU turn, source dirtied by the CPU before each pass | **18.91 ms** | **0.22 ms** | 0.12 / 18.79 ms |
| GPU turn, source untouched | 18.86 ms | 0.18 ms | 0.08 / 18.78 ms |
| GPU landscape copy (control, no rotation) | 2.59 ms | 0.15 ms | 0.07 / 2.53 ms |

`vg_lite_blit` already cleans the source cache (SDK `vg_lite.c:2511`) and
`vg_lite_finish` invalidates the target (`vg_lite.c:4319`); both are inside these
numbers, and the dirty-source run shows the cost of the source clean is about
0.04 ms CPU / 0.1 ms wall for a 1.4 MB source (submit 0.118 vs 0.075 ms).

## What this means

- **CPU saved is real.** The turn costs about 4.0 ms of CPU on the CPU and
  about 0.2 ms with the GPU, 95% less.
- **Wall time is not.** The GPU needs **18.9 ms** for the full rotation, 4.3x the
  CPU turn and almost the whole 19.16 ms refresh. The same-size GPU copy takes
  2.6 ms, so the rotation itself, not bandwidth, is the cost. The CPU sleeps in
  the wait (process CPU 0.2 ms), so another task could use it, but a frame's
  scanout would be late by that wall time unless the compositor pipelines it,
  and at 18.9 ms the GPU alone would cap the compositor at about 53 fps. Partial
  damage should shorten it but that scaling is **UNVERIFIED** (the drawer's band
  is about 74% of the frame by area).

## A cache hazard found on the way (relevant to task 2.4 of `the-shell-trials-vglite-composition`)

With `memset(dumb, 0, size)` and a `vg_lite_clear` of the destination before the
GPU turn, the GPU output differed from the CPU turn in the first row of the buffer
in 5 of 6 runs (`bench-transform1-run0-edge-mismatch.txt`, `bench-transform1-run1..3.txt`,
`bench-transform3-run1.txt`: 96-320 pixels from `x=0`/`192`; the one passing run
was luck). Skipping the CPU prefill (`BENCH_NOCLEAR=1`) gave `bad_rows=0` in 4 of 4
runs. So CPU writes to a buffer the GPU then overwrites can leave stale cached
lines that win against the GPU data: a renderer that mixes CPU-path frames
(or CPU damage repair) and GPU-path frames in the same scanout buffer needs a
proven clean/invalidate protocol for the destination as well as the source. Not
root-caused here (which cache operation is missing is open).

## Files

`bench-transform1-noclear-run1..3.txt`, `bench-transform3-noclear.txt`: passing
runs (summarised by `summarise.py`). `bench-transform1-run1..3.txt`,
`bench-transform3-run1.txt`, `bench-transform1-run0-edge-mismatch.txt`: the
failing prefill runs, kept. Raw `TURN_BENCH` lines in each.
