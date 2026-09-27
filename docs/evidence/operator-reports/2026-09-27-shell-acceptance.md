# Operator real-finger report, 2026-09-27

Evidence class: operator report from real-finger use on the physical board.
There is no camera recording and no native capture. The board was running
the combined installed system built from `master` at the time (see
`docs/evidence/card-shell/transparent-corners/installed-system/`).

The operator, verbatim: "the rounded cards seem fine ... launch splash seems
fine ... new apps seem fine shade drag is fine brightness should be a
slider".

| Feature | Report | Change and task |
| --- | --- | --- |
| Large rounded overview cards: flicking, open/close, radius | fine | `the-overview-shows-large-rounded-cards` E.1 |
| Launch splash | fine | `launching-an-app-shows-a-splash` 6.1–6.3 stay open: they require captures |
| New drawer apps | fine | `feat/more-apps` (no OpenSpec change) |
| Shade drag-to-close, including dragging the panel | fine | shade drag-to-close evidence |
| Brightness | works; the control should be a slider, not a stepper | follow-up |

Not covered by this report: the video-card overview flow, the timeout and
failure splash states, and line-out audio.
