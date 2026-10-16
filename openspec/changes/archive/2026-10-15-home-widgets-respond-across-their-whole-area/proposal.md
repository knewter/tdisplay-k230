## Why

On HDMI at 1280x800 the operator could not move or remove Home widgets. A
press-and-hold on the Battery - Details widget did nothing. Home hit-tests
each grid cell's own tile, but a multi-cell widget is painted across the gaps
between its cells, so a press on a widget's middle often lands in a gap and
hits nothing. At 1280x800 (nine 121 px columns with 18 px gaps, 166 px rows
with 18 px gaps) these dead strips cross every 4x2 widget.

## What Changes

- A press, long press or secondary click on a multi-cell widget hits that
  widget anywhere inside its painted rectangle, including the gaps between its
  cells.
- Single-cell app icons keep their tile-only hit area, and the gaps between
  separate icons stay inert.

**Non-goals:** changing the grid geometry, drop targeting during a drag, or
how a widget is removed.
