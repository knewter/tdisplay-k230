## Context

These are the limits the operator accepted when closing
`the-shell-and-its-apps-look-finished`. The charger line was already
ellipsised by Pango. The carousel's side slices are cached sprites: the
content is masked by a skewed outline (`CardSprites`).

## Decisions

- **Charger line.** `input_label_choices()` lists the line from most to least
  detailed. The renderer draws the first choice that fits at the line size.
  Shrinking the text instead would push it below the 26 px Label floor.
- **Frame.** The frame is stroked inside `paint_content`, before the mask is
  applied. That keeps it inside the cached sprite and on the existing fast
  path. Its ink is black or white at 22 % alpha, picked against the page's
  background luminance.
- **Measurements.** Timer and Weather are tested with injected touch and grim,
  using the existing board driver. Omawrite's start-up is timed from the tap to
  its first mapped window. Neither measurement has a pass threshold.

## Risks

- A frame on the centred card also shows on dark themes, at low contrast.
  The board captures check that.
