## Why

The operator cannot read part of the Home Clock widget on the panel. On
2026-10-16, looking at the landscape panel at 200% text, they said the clock
"has got some text too small to see really"
(`docs/evidence/coherent-shell/accessibility-scale/README.md`). The panel
capture `board/14-panel-200-home.png` shows the cause. The digits are large,
but the date line under them ("FRI, OCT 16") is drawn at a fixed 17 px. That
is about 8 dp at the panel's roughly 2.07 px/dp, well under a 12 sp floor.
The analog style's date is 15 px. Home widgets deliberately ignore the
Vision text step, so the date stays that size at every step.

## What Changes

- Every Clock style draws its date line at least 26 px (about 12.5 dp) at
  100%, and that size grows with the Vision text step.
- The date shrinks to fit the cell width when needed, with the same 4%
  margin as the rest of the shell, and never ellipsizes at any step.
- When the date needs more height, the time digits make room instead of
  overlapping it.

## Non-goals

- No new clock styles, colours or fonts, and no change to the widget's cell
  span.
- The Battery and Weather widgets' small labels are not covered.
- The time digits are not made larger.

## Board

Host renders prove the geometry. Readability needs a native panel capture
and the operator's look at the glass. QEMU does not apply.
