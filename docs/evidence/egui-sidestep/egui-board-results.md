# egui on the K230: board results (2026-10-30)

**Evidence class:** board, normal Sway session with the shell running, one C908
core online; *injected* input (uinput), native `grim` captures, client commit
timestamps. No real finger, no camera, no optical latency. "Commit" is the
client's own `wl_surface.commit`, which is submission, not presentation.

**Client:** `nix/egui-software-probe`, egui 0.34.1 with `egui_software_backend`
0.0.3 (CPU rasteriser) writing into `wl_shm` buffers; no OpenGL, Vulkan, winit
or softbuffer is linked or mapped (`identity-egui.json`: `mapped_graphics_libs`
empty, no dmabuf or `wl_drm` protocol bound, `wl_shm` buffers attached). Same
scene as the Qt Quick probe and the C `wl_shm` baseline (landscape 1232x568: a
20-row scrolling list, an editor field, an animated tile, an image and text).
**Baseline:** `nix/qtquick-shm-baseline`, drawn with plain pixel loops, same
scene, same gestures, same harness arm.

**Harness:** the Qt trial's board runner and analysis (`tools/qtquick_board_runner.py`,
`tools/qtquick_analysis.py`), driven by `tools/toolkit-eval-trial.py`.

## What can be trusted, and what cannot

Only **one complete matched pair** (30 s idle, 30 s active, 48 interactions per
arm) is valid: `pairs-cargo-build/runs/pair1-{egui,baseline}`. A second short pair
(12 s active, 18 interactions) in `short-pair-12s/` agrees with it. The planned
three-pair trial was **not completed**: the board was taken for a boot-path trial
before the remaining arms could run.

Faults found in the harness, all retained:

- The runner's injected touchscreen did not land at a stable place. In the first
  arm of one run, taps arrived rotated a quarter turn (client log: injected
  (300,400) arrived as (363,138)); a pre-rotating patch of the runner's mapping
  (applied in memory by `tools/toolkit-eval-trial.py` in an earlier version, since replaced by the pointer patch; not applied to the runner's file)
  made pair 1 land correctly, but the first arm of pair 2 landed in the wrong place again (inputs at constant y=138)
  (`pairs-cargo-build/runs/pair2-baseline`: gates scroll and tap fail, CPU 2%);
  it is **invalid and excluded**. A last attempt replaced the touchscreen with an
  absolute pointer pinned to DSI-1 (`pointer-attempt/`); its scroll and tap gates
  also failed in one egui arm and it was not repeated (the board was withdrawn).
  The harness's touch placement needs fixing by its owner; this is a finding for
  the Qt trial too.
- The panel blanks when idle and `grim` then waits forever; the controller wakes it
  with a pointer move before each arm.
- The runner's functional checks assume the scene as launched, but run after the
  30 s of interaction; the controller patches in a reset (scroll to top, tile left,
  row 0 deselected) so the gates test the right state.
- `text_focus` and `text_entry` **fail for the baseline and for egui alike**: the
  client logs `text_input_enable` and the keyboard flag is raised, but the
  on-screen keyboard did not appear in the captures, so typing was not tested.
- The egui build measured here is a cargo cross-build wrapped as a store path
  (`/nix/store/1gik...` and `aypmvv...-egui-software-probe-cargo`). The pinned
  flake output `.#egui-software-probe` (`/nix/store/jr5vpm68...`, 5.8 MB binary,
  closure 4 store paths, 127 MB mostly glibc, built in 1 min 8 s of rustc after
  64 crate derivations) built successfully and was used for the pointer attempt,
  but not for the valid pair. Same sources, same rustc major.
- Whole-system CPU was not sampled for pair 1 (added later); another agent's
  jobs run under the same board lock, not during an arm.

## Numbers (valid pair, 30 s idle + 30 s active)

| | `wl_shm` baseline | egui | notes |
| --- | ---: | ---: | --- |
| first frame after launch | 190 ms | 283 ms | startup |
| memory above the pre-launch session (`MemTotal-MemAvailable`) | 35.6 MiB | 38.0 MiB | whole-system delta, includes the compositor's own growth |
| client CPU, idle | 0.02% | 0.02% | of one core |
| Sway CPU, idle | 1.2% | 1.2% | |
| client CPU, active | 7.6% | **45.9%** | |
| Sway CPU, active | 7.6% | 16.6% | |
| client + Sway CPU, active | 15.2% | **62.5%** | egui costs 4.1x the baseline |
| egui time to run, tessellate and rasterise one frame, p50 / p95 / max | - | **23.6 / 40.8 / 75.2 ms** | card budget is 16.667 ms p95 |
| commits in the 30 s active phase | 406 | 586 | |
| commit interval, p50 / p95 | 19 / 567 ms | 41 / 57 ms | baseline commits only when the scene changes and otherwise on a 500 ms cursor tick, so its p95 is idle gaps; egui redraws continuously while a drag or flick runs |
| input to next commit, p50 / p95 | 13 / 814 ms | 37 / 53 ms | the baseline's p95 counts inputs that change nothing and wait for the cursor tick; egui commits after every input; **not comparable beyond the medians** |

The short pair (12 s active) shows the same shape: egui 52% client CPU and
render p50 35.6 ms against the baseline's 11.5% and no render log; combined
active CPU 68.8% against 22.3%.

Functional gates (pair 1, both clients): pixels correct, readable, tap, scroll
(a 300 ms drag moved the list), interrupted motion (a second tap on the moving
tile retargeted it), software route, bounded lifetime, restoration all **PASS**;
`text_focus` and `text_entry` **FAIL** for both (see above). The normal session
(sway PID, system closure, boot ID, boot default) was identical before and after
every arm, and every transient unit was gone afterwards
(`restoration` fields in each run record).

## Reading it

egui draws a correct, readable UI on this board with no GPU. While the user
drags the list it renders at roughly 24 frames per second (a frame every 41 ms,
23.6 ms of CPU each, median) and uses most of the single core (46% in the app
plus 17% in Sway). Idle it costs nothing (0.02%). It is about three times the
frame rate of the shell's own app drawer under a sustained scroll (about 8
presented frames per second, 39 ms per render;
`docs/evidence/interaction-jank/drawer-scroll/README.md`), but it still misses the
shell's 16.7 ms frame budget and costs four times the hand-written baseline.
