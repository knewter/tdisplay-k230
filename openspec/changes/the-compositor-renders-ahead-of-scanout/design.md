## Context

The bottom-band flicker appeared only while frames rendered continuously,
and it cycled correct, stale-dark and black on consecutive frames
(`max-render-time-fix.md`). Scene and present timing were clean
(`board-diagnostic.md`), and deferring the VO register commit to vblank
changed nothing (`kernel-vblank-latch.md`).

## Goals / Non-Goals

**Goals:** a stable panel image during gestures on real glass.

**Non-Goals:** establishing the scanout or DDR mechanism, and changing the
VO driver.

## Decisions

1. Use Sway's per-output `max_render_time 8`. It moves composition and its
   memory traffic next to the vblank, away from the scan of the last lines,
   and it is a configuration change that is easy to revert.
2. Do not apply the vblank-latch kernel patch. It had no measured effect, and
   a kernel carrying it panicked at boot (`kernel-patch-boot-panic.md`).

## Risks / Trade-offs

- A frame that renders in more than about 8 ms repeats the previous frame
  rather than tearing.
- The root cause is inferred, not measured.
