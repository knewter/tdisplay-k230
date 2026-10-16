## Context

Home widgets ignore the Vision text step: `paint_widget_card` divides the
step back out of the font metric, so each widget keeps the proportions of its
cell (commit `8799961c`). The Clock's digits scale with the card's height, but
its date line was a fixed 17 px (15 px for the analog style), about 8 dp on
the panel.

## Decisions

1. **The date is sized before the time.** `clock_date_metrics` starts at a
   26 px floor times the Vision step. That is about 12.5 dp, the usual 12 sp
   minimum for secondary text. The date is the one Clock element that follows
   the step, because the digits are already large.
2. **Drop tracking before shrinking.** The caption's thin-space letter
   tracking costs about a quarter of its width. On a card about 280 px wide
   the tracked date does not fit at 26 px. Removing the tracking keeps the
   size, so it goes first. After that, the date shrinks to the card's width
   with the shell's 4% margin and never ellipsizes.
3. **The time yields.** When the date needs more height, its top moves up.
   The time's positions and sizes are multiplied by the same ratio, so the
   pair keeps its proportions and never overlaps.

## Risks

- The time is smaller at 200% on short cards, which is the intended trade.
- The Thin, dot-matrix and analog styles share the metrics but have no
  committed renders. Task 2.1 covers the default Bubble style on the board.
