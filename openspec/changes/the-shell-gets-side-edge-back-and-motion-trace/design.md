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

## Motion producer completion (2026-10-19)

Layer: userspace, the Sway compositor and host trace consumer.

- The frozen `K230_CARD_BENCH` event schema stays compatible with the
  existing acceptance parser. Supplemental `K230_CARD_SHELL motion-*`
  rows carry the motion mode, scene-update completion, and frame callback.
- `scene_damage` is stamped at the first successful scene update within
  an accepted input handler or after it while its input is still pending.
  Its timestamp is emitted with the accepted input ID only after ownership
  is known; an unconsumed input emits no damage trace. This is scene-graph update completion, not the later
  output-buffer damage-region calculation.
- `frame_done` is stamped immediately after the actual surface callback
  dispatch, in both immediate and delayed Sway paths. It identifies the
  output's current successful commit sequence. Multiple surfaces on that
  commit yield one row; a different output is ignored.
- Missing stages, mismatched frame IDs, or event provenance do not become
  a pass. The report includes each adjacent stage's measured distribution.
  A callback that cannot be correlated remains incomplete or invalid; no
  timestamp is fabricated to fit the schema.
- Native producer tests feed real C output through both consumers. They
  are host evidence only. The board measurement, reduced-motion comparison,
  and camera-visible panel correlation remain task 2.2.

Rejected: adding new events to `K230_CARD_BENCH`, which would break its
strict existing consumers; labeling render completion as a frame callback;
and treating a missing scene/callback stage as a successful legacy run.

Release traces finish at the successful frame committed after the card/Home
policy stops moving. The producer emits a separate settlement correlation;
the consumer waits for that commit's callback and presentation, rather than
calling the first frame after lift-off a completed animation. The policy
observer excludes the motion sampler's 300 ms quality hold. An interrupted
release stays unresolved. `--compare-motion` checks one full and one reduced
run from the same recorded workload using these measured settled frames.

The log adapter retains all output presentation events inside each gesture's
tracking/settling window. Cadence and inferred missed intervals use those
frames, including animation frames with no new touch; they are not derived
from gaps between accepted input IDs. Motion-to-first-present and
release-to-settled-present distributions are separate. Output events marked
unpresented are reported, and camera-visible blank frames require the
separate physical recording. The fixed-grammar journal exporter preserves
only the known diagnostic fields and stage/mode values.

### Ordering observed on the landscape panel

The initial 2026-10-19 injected diagnostic probe (source `3c6ea3eb`)
showed DRM presentation timestamps 0.4–6 ms before surface-callback dispatch.
The pinned Sway output path commits before sending callbacks; a synchronous
output commit can report an earlier scanout timestamp. The consumer therefore
checks causal order input <= scene update <= commit, then commit <= callback
and commit <= presentation independently. Callback-to-presentation intervals
remain signed. The native producer fixture reproduces both this ordering
and coalesced inputs whose scene update occurs in the next accepted handler.
The initial probe is not a performance acceptance run: it has only 17 trace
IDs, missing stages in the first producer, and an intrusive held `grim` capture.

When the existing `input-origin` diagnostic is present, the input stage uses
its device monotonic timestamp, including dispatch queueing in the latency.
Legacy logs and synthetic fixtures fall back to handler dispatch. The
fixed-grammar exporter preserves only numeric origin fields; timestamps
following their handler dispatch are rejected. The board collection records
which producer and consumer were used.

## Board and camera completion (2026-10-19)

The actual userspace producer is installed at source `29fe458c`. Native-uinput
full/reduced runs capture every named stage and honestly fail timing budgets.
After the operator repositioned the camera, new concurrent video/trace runs
completed the optical correlation task with bounded alignment and sampling
limits. Evidence: `docs/evidence/coherent-shell/motion-2026-10-19/camera/README.md`.
Reduced settling is shorter; no renderer performance fix is claimed. The camera
checks visible movement and sampled blanking, not every physical refresh or
precise optical latency. Original software-only runs keep their evidence class.
