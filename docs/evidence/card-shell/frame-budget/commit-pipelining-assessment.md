# Assessing commit pipelining (task 3): finding, not a change

`analysis.md`'s H1 (leading, evidence-grounded, and now confirmed by the
board capture in `board-result-2026-09-28.md`) already identifies the
mechanism: `canaan_crtc_atomic_flush`
(`drivers/gpu/drm/canaan/canaan_crtc.c:90-108`, pinned tree,
`nix/kernel-src.nix`) writes `canaan_vo_flush_config(vo)` -- the hardware
register load -- synchronously inline in the atomic-commit-tail callback,
before arming the vblank completion event. wlroots/Sway's own atomic commit
call (`wlr_output_commit_state`, this change's host measurement above shows
its CPU cost is tiny -- 0.5% of render CPU, p50 0.08 ms) is already
non-blocking at the wlroots level; the blocking happens one layer down, in
the kernel's own commit-tail worker, which is outside what this task's
userspace host measurement can see or change.

## Why this is assessed, not fixed, here

1. **A fix already exists and already failed.**
   `canaan-drm-defer-reg-load-to-vblank.patch` (cited in `analysis.md` H1 and
   H2, and in `docs/evidence/card-shell/bottom-band-flicker/
   kernel-patch-boot-panic.md`) is the natural fix -- defer the register load
   to the driver's own vblank IRQ window instead of doing it inline -- and it
   is "deliberately NOT applied" per `nix/kernel.nix`'s own comment, because
   it caused a boot panic unrelated to card-shell. Any new attempt at this
   exact mechanism needs to either fix or route around that panic first,
   which is its own investigation, not a "small and safe" edit.
2. **No new evidence changes that risk calculus.** This task's own host
   measurement (above) and the board's vblank capture both point at the same
   place H1 already named. Nothing found here narrows the boot-panic's cause
   or suggests the earlier patch attempt was wrong in a way this task can
   now safely correct.
3. **The instruction for this task is explicit**: assess and document the
   finding; only change the kernel "if it's clearly small and safe," and if
   so, as a separate, coordinator-gatable commit. Given (1), it is not small
   or safe within this task's scope -- it is a second attempt at a change
   that already produced a boot panic, on hardware this task was told not to
   touch (`Don't touch the board`).

## What a future attempt would need

- Root-cause the prior boot panic (`kernel-patch-boot-panic.md`) before
  reapplying or rewriting the deferred-register-load patch.
- A way to correlate DRM vblank sequence numbers with presented `frame_id`s
  under load (`analysis.md` section 2's own suggested board command, run
  concurrently with `tools/card-shell-benchmark.py --board`) to confirm the
  overrun is specifically serialized by the synchronous register write and
  not by something else in the commit-tail workqueue.
- Its own separate OpenSpec change under `system/kernel`, since it is a
  device-driver timing change, not a card-shell userspace change, and needs
  its own board-gated proof and its own reviewable diff -- exactly the
  "gate the kernel change separately" instruction this task was given.

## Conclusion carried into `tasks.md`

Task 4.2's decision point is: (b) record the current ~57 ms tracking-interval
miss as an accepted, understood cost (with the distinction `analysis.md`'s
decision table already states -- this is an overrun rate from a
non-pipelined commit, not a hardware refresh limit, so accepting it is a
scoped statement, not "the panel can't go faster"), or open a new,
separately-gated kernel change to attempt commit pipelining with the
boot-panic risk above priced in. This successor's own userspace
investigation (this document and `host-cost-table.md`) has exhausted the
CPU-side and damage-side options available without touching visuals or the
kernel; it does not itself resolve 4.2, and does not claim to.
