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

The exact221bbcf3 build passes. The first integration attempt used unsupported
probe IDs and failed before mapping any window; its complete driver log and
command are preserved. The corrected host test uses the existing supported
IDs and detects early client exit. Its source hash is recorded separately;
the compiled compositor/adapter source remains221bbcf3 unchanged.

All three actual-compositor cases pass: rotatedRGB565 full/reduced and normal
RGB565 rollback. In one IPC batch, policy reaches the latest requested pose
without a render; the next render applies that pose. Main/desynchronized-child
frames advance during a held drag. New maps force structural synchronization.
Expansion hides chrome in the same dispatch before a frame can conceal stale
visibility, and settled bilinear counts advance after release. Rotated paths
increment coalescing counters; normal output keeps both zero. Complete numeric
results/client logs and Sway logs are committed under runtime/. This is actual
headless QEMU/Wayland integration, not panel pixels or real touch/latency proof.

`runtime-command.json` preserves the concrete command and exact binary paths.
The legacy mock failure remains an independent fixture limitation; no unperformed
or failed check is marked passed. Board paired timing, live content/current
camera, persistent selection and archival gates remain open. The board stays
on baseline until its recoverable candidate trial is reserved and started.
