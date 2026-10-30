# Board attempt 1 (superseded, retained failures)

Evidence class: board, injected touch (uinput), native capture; **incomplete**.
Probe `j2dd2anwbp2hpfmvm4w6kpsa0qn37zq8...`, baseline `y4qh2n92...`, system
`49mnsl2s...` (also the boot default), 2026-10-30 about 11:05 to 12:00 local.

What it did produce:

* `identity-qt.json`, `identity-baseline.json`: WAYLAND_DEBUG protocol
  identity. Qt: `QT_QPA_PLATFORM=wayland`, `QT_QUICK_BACKEND=software`,
  `QSG_INFO=1`, no inherited `QSG_RHI_BACKEND`, journal line
  `Loading backend software`, buffers `wl_shm` `XRGB8888` (3 attaches in the
  3-second window), **0** linux-dmabuf and **0** wl_drm requests, text-input v3
  bound. Libraries mapped include `libEGL`, `libGLX`, `libGLdispatch`,
  `libvulkan` (incidental, recorded; no GPU buffer path was used). Baseline:
  `wl_shm` `XRGB8888`, 1 attach, no dmabuf.
* Qt first frame was logged about 470 ms after process start (client clock).
* Both identity runs restored the session (`restoration/identity-*.json`).

What failed (the runs in `runs/`, all `status` fields retained):

* `pair1-qt`, `pair3-qt`: `no-window`. The compositor tree had no window with
  `app_id` `qtquick-software-probe`; fixed afterwards in source (see
  `../qt-cross-build.md`). Both restored the session.
* `pair1-baseline`: a `grim` call timed out after 40 s and aborted the run
  (a runner weakness, now a 90 s non-fatal timeout); restored.
* `pair2-baseline`: `status ok`, 47 injected interactions, restored, and the
  startup capture matched the expected scene (`gates.pixels_correct`), but
  `client_cpu_us` was unreadable (`None`: the unit cgroup file was not read),
  and none of the scroll/tap/text gates exist (the later `grim` captures did
  not complete). It is therefore not a usable measurement.
* `pair2-qt` also failed with `no-window`. The negative-control arm and pair 3
  baseline never ran: the controller was terminated on the coordinator's
  instruction to free the board for the U-Boot trial. `decide` on this
  directory reports INCOMPLETE (`decision.json`); no measurement from it is used.
* The raw captures of this attempt were deleted by mistake before commit;
  they were never evidence for a claim.

Restoration after every arm that ran: same Sway PID, `shell` active, no
`qtq-*` unit, focus back on the terminal (`restoration/*.json`).
