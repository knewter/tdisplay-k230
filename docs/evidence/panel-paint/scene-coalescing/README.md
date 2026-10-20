# Render-boundary scene synchronization — 2026-10-20 UTC

Source1bc9243f's controlled pair14 passes, but repeat15 fails latency. The
unchanged input-cost probe measures about0.53ms of scene synchronization per
accepted touch, then the16ms timer and render preparation repeat scene work.
The selected correction coalesces **plain moving redraws** only on rotated
RGB565 outputs into the existing render preparation, before frame pixels are
built. Input policy/ownership updates immediately. Each deferred redraw
schedules a frame. Structural reconcile/shrink/restore and other outputs keep
the synchronous/legacy12ms behavior. Chrome visibility is updated immediately,
including the start of expansion. Timer preparation still performs lifecycle,
Home-layer self-healing, configuration and reconciliation; it skips only the
redundant moving paint. Idle/interrupted-hold ticks keep normal scene refresh
and settled bilinear restoration. No frame/content cap, quality or8ms change.

Four counters and selected scene coordinates/filter counts are available only
in the existing read-only debug-scene query. No new per-input/periodic logs.
The counters distinguish coalesced redraw/timer calls, render preparations and
structural synchronizations; they do not count physical presentations.

All41 product policy cases pass. The old extracted chrome mock does not
compile against either this source or the unchanged669d56a5 baseline: its
stub/state extraction has drifted (including edge state and missing helpers).
Both complete errors are retained; it is not claimed as a passing check and
its unrelated fixture is not repaired here. The new actual-compositor test
checks immediate policy versus render-time pose, advancing main/child clients,
structural maps, expansion chrome and restored bilinear sampling in rotated
full/reduced mode, plus the normal-output rollback path.

A separate **old-source format probe**, not new-source correctness evidence,
confirms actual headless QEMU Sway can select rotatedRGB565 (format0x10020565).
This enables meaningful integration coverage of the targeted path.

The new test is a deliverable and is not yet proof at this checkpoint:

```sh
CARD_SHELL_SWAY=<exact-cross-built-unwrapped-sway> CARD_SHELL_CLIENT=<native-probe-client> python3 tests/test_card_shell_scene_coalesce_runtime.py
```

Exact build, new headless integration, paired board timings, live callbacks,
current camera, persistent selection and archive remain open. Keep the baseline
installed until the named qualification is complete.
