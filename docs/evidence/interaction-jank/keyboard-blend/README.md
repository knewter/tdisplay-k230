# Keyboard frames and the OVER blend of opaque surfaces

**Evidence class: board, injected native touch.** All captures were taken on
2026-10-25 (UTC) on the board's DSI panel in landscape: 1232x568 logical
pixels, 52.19 Hz (19.16 ms per refresh), `max_render_time 12`, one online
CPU. There was no real glass and no camera.

## Workload

[`measure.sh`](../compositor-repaint/measure.sh.txt) from compositor-repaint,
unchanged: a 30 s drawer scroll, then eight
[keyboard cycles](../keyboard/keyboard-cycles.py.txt) (show, type,
hold-and-reverse, hide) with the compositor benchmark armed. The analysers are
[`analyze.py`](../keyboard/analyze.py.txt) for the keyboard and
[`cadence.py`](../drawer-profile/cadence.py.txt) for the drawer.

| Run | System | Pixman in sway | Time (UTC) |
| --- | --- | --- | --- |
| [run-base](run-base) | `pb5l6lmb` (boot default), test-activated | stock RVV | 00:53 |
| [run-first](run-first) | `jpc0hl8p`, test-activated | first patch: test every chunk | 00:51 |
| [run-final](run-final) | `h4rqzlgr`, test-activated | final patch: per-row bail-out | 00:59 |

All three ran on the same boot within nine minutes, in the order first, base,
final.

## Where the settle time went

Show settle was the last keyboard phase over budget after compositor-repaint
(38.3 ms presented interval, 16 ms render).

- **Profiles timed on CLOCK_MONOTONIC.** [prof-base](prof-base/flamegraph.svg)
  records sway with `perf record -k CLOCK_MONOTONIC` (otherwise
  `tools/board-profile.py`, unchanged), so samples line up with the
  benchmark's repaint rows. Without `-k`, perf's clock ran 2.31 s from
  CLOCK_MONOTONIC on this boot. [`perframe.py`](perframe.py.txt) gives the
  CPU per frame for each phase ([per-frame.txt](prof-base/per-frame.txt)).
  In full-damage settle frames, `rvv_composite_over_8888_0565` took
  6.1 ms per frame, against 1.3 ms in full-damage show-contact frames.
- **No preemption.** A system-wide `sched:sched_switch` trace of the same
  workload ([`schedwin.py`](schedwin.py.txt), [result](sched-switch.txt))
  shows sway on the CPU for its whole repaint in every phase. The raw trace
  is not committed.
- **What is composited.** A logging `LD_PRELOAD` shim
  ([`composite-shim.c`](composite-shim.c.txt)) recorded every
  `pixman_image_composite32` call in sway for three cycles
  ([composites](composites/show-cycle-1.txt), replay with
  [`composites.py`](composites.py.txt)). Each keyboard frame blends three
  ARGB8888 surfaces OVER the RGB565 output:
  - the Foot window, 1232x568;
  - wvkbd's key-preview popup, 1232x480, which is fully transparent unless a
    key is held;
  - the keyboard, 1232x240.

  wvkbd's colours carry no alpha, so the keyboard is opaque. The Foot
  terminal is opaque too. OVER still reads and blends the destination for
  every pixel of all three.
- **Not the popup alone.** wvkbd creates the popup surface even with
  `--no-popup`, so the [popup A/B](popup-ab) (wvkbd restarted with
  `--no-popup` under a transient unit) changed nothing: show-settle render
  16.1 → 16.7 ms. The normal keyboard service was restarted afterwards.

## The change

`nix/patches/pixman-rvv-over-0565-exact-shortcuts.patch` adds two exact
shortcuts to Pixman's RVV `over_8888_0565` (OVER, a8r8g8b8 → r5g6b5):

- a vector chunk whose source alpha is all 0xff is converted and stored. OVER
  with alpha 0xff yields the source;
- a chunk whose source is all zero is skipped. OVER leaves the destination
  unchanged, and the 0565 → 0888 → 0565 round trip is lossless.

Neither declares or infers an opaque region, and nothing below a surface is
culled. Each frame is the same OVER blend as before, computed faster.

The first version tested every chunk. On the drawer, whose sheet is drawn at
alpha 0.95, every chunk failed both tests: sway's drawer repaint rose from
10.19 to 10.79 ms ([run-first](run-first)). The final version stops testing
for the rest of a row once a chunk is neither, so a uniformly translucent
surface pays one test per row.

Only the compositor gets the patch. `nix/card-shell.nix` builds sway's
wlroots against the patched Pixman and puts it first in sway's build inputs,
so sway's RUNPATH resolves its own `libpixman-1.so.0` there. Cairo's request
then reuses it by soname. On the board, `/proc/<sway>/maps` shows only
`sn5is273…-pixman` on `h4rqzlgr`. The rest of the closure keeps the shared
Pixman: patching it globally would rebuild 104 store paths (about 300 MB,
GTK, GStreamer, Nautilus among them), whereas the system delta for this
change is about 25 MB.

## Exactness

[`exact.c`](exact.c.txt), built by [`exact.nix`](exact.nix.txt), composites
112 OVER a8r8g8b8 → r5g6b5 cases on the board:

- 16 widths (1 to 1232), with odd source and destination offsets and
  strides;
- seven source patterns: all opaque, all zero, random alpha, 11-pixel runs,
  alpha 0 with non-zero colour, alpha 1 or 254, and sparse mixes.

It ran under stock RVV Pixman (`brhzfimak…`), patched RVV Pixman
(`sn5is273…`), and the patched library with `PIXMAN_DISABLE=rvv`. All three
destination dumps have sha256 `a39338ae…be41`.

The same program timed a keyboard-sized 1232x240 composite (best of 30, heap
memory):

| Source | Stock RVV | Patched RVV | Scalar |
| --- | ---: | ---: | ---: |
| Opaque | 2.28 ms | 1.01 ms | 2.42 ms |
| Alpha 242 everywhere | 2.37 ms | 2.26 ms | 9.92 ms |
| Random alpha | 2.28 ms | 2.26 ms | 9.77 ms |

Each run's grim captures were taken from sway's output:

- keyboard: before, shown, hidden;
- drawer: open, mid-scroll, after close.

All six are pixel-identical between run-base and run-final, with an empty
difference bounding box. They are not committed, matching compositor-repaint.

## Results

Cells give the presented interval median / p95 in ms, intervals over
33.334 ms, and the render wall median / p95 in ms.

| Phase | run-base | run-final |
| --- | --- | --- |
| Show, contact | 19.2 / 172.5, 29 of 78, 8.4 / 20.3 | 19.2 / 172.4, 21 of 94, 8.1 / 16.0 |
| Show, settle | **38.3** / 57.5, 79 of 102, **16.0** / 17.5 | **19.2** / 57.5, 54 of 124, **10.0** / 12.9 |
| Hold and reverse, contact | 19.2 / 57.5, 28 of 304, 9.8 / 11.6 | 19.2 / 57.5, 22 of 305, 7.0 / 8.3 |
| Hold and reverse, settle | 57.5 / 115.0, 19 of 33, 10.7 / 18.7 | 19.2 / 76.6, 9 of 19, 8.4 / 14.0 |
| Hide, contact | 19.2 / 19.2, 2 of 129, 8.7 / 11.4 | 19.2 / 19.2, 0 of 134, 6.2 / 8.1 |

| Drawer | run-base | run-first | run-final |
| --- | --- | --- | --- |
| Distinct presented fps | 23.6 | 23.3 | 24.2 |
| Interval median / p95 | 21 / 39 ms | 21 / 39 ms | 21 / 39 ms |
| Sway repaint median (p10–p90) | 10.19 (10.08–10.31) ms | 10.79 (10.69–10.90) ms | 10.22 (10.11–10.33) ms |

- **Show settle** now presents a median of every refresh. Its p95 is still
  three refreshes and 54 intervals remain over budget, so it is not declared
  passed.
- **Every keyboard render** is about 2.5 ms shorter at the median.
- **The drawer** is unchanged against run-base.
- All frames were presented in every run (889, 916 and 922 rows).

[preload-trial](preload-trial) ran the first patch under a runtime-only
`LD_LIBRARY_PATH` drop-in in `/run/systemd/system/shell.service.d/` before
any system was built (show-settle render 16.6 → 12.2 ms). It was removed
again, and `/proc/<sway>/maps` showed the stock Pixman afterwards.
[prof-trial](prof-trial/flamegraph.svg) profiles that arm.
[`slowfast.py`](slowfast.py.txt) splits its settle frames into those under
and over 11 ms ([slow-fast.txt](prof-trial/slow-fast.txt)).

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- Presentation time is not photon time.
- Only landscape was measured, with one Foot window as the app.
- One run per build. Card entry and the shade were not re-run; they composite
  through other paths (scaled cards, the shade's sheet) and are not claimed
  either way.
- Profiles sample at 499 Hz with 64 KiB DWARF stacks (`perf record -q`, so
  lost-sample counts were not reported). Sampled CPU per frame is below the
  repaint wall time, so the profiles give shares, and timing comes from the
  unprofiled runs.

The board was left test-activated on `h4rqzlgr` with `pb5l6lmb` as the boot
default. Owned files under `/var/tmp` were removed.
