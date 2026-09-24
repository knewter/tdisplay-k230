# Keep Pixman as the required live-card rendering path

Task 4.3 of `the-shell-manages-apps-as-cards` asks for a decision on its optional
VG-Lite path. The decision is **not to pursue VG-Lite as part of this bounded
card acceptance path**. Continue the required live-card interaction and cost
work on Pixman. The separately authorized GPU composition trial remains open
with all its source, synchronization, isolation, performance and physical
control requirements intact. Nothing in this decision archives that trial or
claims GPU acceptance. The machine-readable decision is [renderer-decision.json](renderer-decision.json).

The three committed [GPU scene comparisons](../vglite-scene-board/context-lifetime/README.md)
used a retained context and corrected RGB565 upload. GPU passes averaged
43.959–44.452 ms wall time and 37.046–37.259 ms process CPU; paired forced-Pixman
passes averaged 36.242–36.647 ms and 32.471–32.646 ms. The result fields in the
JSON are copied from the six committed summary files, whose paths are included.
These were animated full-panel parent/child scenes, not live-card workloads.
They do not justify projecting either a card speedup or an identical card cost.
They do identify source snapshots and conversion/upload as unresolved GPU costs.

The [latest card comparison](scaled-cache-board/README.md) retains failed
Pixman CPU/tracking budgets despite complete injected interaction traces. Its
negative cache result does not establish that GPU would pass. There is no
same-workload GPU card measurement, and compositor-only normal-service access
and broader cache/operation correctness remain unproved on the physical board.
Connecting this optional renderer now would add dependencies without current
proof that they solve the measured card gap.

This decision closes only the choice in card task 4.3. Task 4.2 still requires
an accepted cost decision that preserves live cards, direct drag, selection,
expansion and recoverable throw. Image integration and real-finger acceptance
remain open. The user separately authorized making proven RVV support part of
the normal image; that work continues under its own published proposal and is
not rejected by this renderer decision.

Reconsider a GPU card route when the separate trial establishes usable normal
service access, the needed format/clip/scale/completion behavior, and a measured
reason to expect the same live workload to improve. Any such comparison must
use the card workload and unchanged acceptance limits, retain failed trials,
and record physical evidence. Until then, keep the unsupported diagnostic
opt-in and do not make it a prerequisite for the gesture shell.

This is a reviewed decision from existing committed physical evidence, not a
new hardware test. No source, kernel, image, board state, or acceptance budget
was changed. Narrow validation: `openspec validate the-shell-manages-apps-as-cards
--strict`, with referenced JSON values and paths checked against the six source
summaries. Physical gates remain explicitly unchecked.
