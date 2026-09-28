## Context

`nix/card-shell/adapter.c` already claims the bottom edge band for
`cs_begin_entry`/`cs_edge_down` even while a Rust overlay is mapped (the
bottom-edge overlay-escape fix, `the-shell-behaves-as-one-coherent-system`
slice E), and `nix/rust-shell-client/src/service_ui.rs` already shares
`OVERLAY_DISMISS_ZONE_Y`/`OVERLAY_DISMISS_DY` between Shade and Settings for
their own top-anchored downward-dismiss gesture. Neither of those is a
side-edge gesture, and neither defines a general touch-ownership arbiter
across bottom/top/side/keyboard/deck/app-content -- they are point fixes for
one reported bug (swiping up from inside Settings did nothing).

## Goals / Non-Goals

**Goals:** a qualified side-edge inward swipe that dismisses the topmost shell
context; one arbitration point (compositor-side, alongside the existing
bottom-edge recognizers) that decides which surface owns a touch at down;
a host-testable motion-trace tool with declared budgets, mirroring the
pattern `tools/card-shell-benchmark.py` already established for card-shell
cost work.

**Non-Goals:** replacing the bottom-edge overlay escape; a universal
synthetic Back keypress into arbitrary app content; any board work (separate
tasks below).

## Decisions

1. **Side Back is a new compositor-side recognizer, not a Rust-client
   gesture.** Sway/wlroots already owns touch arbitration at the app/deck
   boundary (`nix/card-shell/adapter.c`); the side edge is claimed there,
   alongside the existing bottom-edge `cs_begin_entry`/`cs_edge_down`
   recognizers, using the same `Route::Hide` signal
   (`card_shell_launch_surface`, already accepting `"hide"` per slice E) to
   tell a mapped Rust overlay to dismiss. This keeps one touch-ownership
   authority instead of splitting arbitration between the compositor and the
   Rust client.
2. **Ownership order matches the existing dismiss chain.** Context sheet,
   then Settings/shade/drawer, then keyboard (when keyboard focus owns the
   touch) -- the same order task 2.2's requirement text already specifies.
   No new order is invented.
3. **The trace tool is host-first, board-second.** `tools/shell-motion-trace.py
   --self-test` proves the trace ID schema and budget-reporting format without
   a board (mirrors `tools/card-shell-benchmark.py --self-test`); `--board`
   mode is a separate, later task once a board reservation is available.

## Risks / Trade-offs

- [Side edge conflicts with app content or keyboard] -> test ownership
  arbitration host-side before any board task; keep the existing bottom-edge
  escape as the immediate fallback if side Back's board task fails.
- [Motion-trace tool scope grows into a full profiler] -> bound it to the
  same trace-ID/budget schema already named in the parent's task 4.5 text;
  do not add new instrumentation beyond touch->damage->commit->frame-done->
  output-presented.

## Migration Plan

Implement side Back and ownership arbitration host-side, land host/QEMU
fixtures, then implement the trace tool and its self-test. Board acceptance
for both stays open until a reservation is available. No stage 1, kernel, or
device tree change.
