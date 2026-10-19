## Why

`the-shell-has-one-visual-language` put Settings, the Vision page, the
Shade's header and controls, the drawer, the Clock and Battery details on
five type roles with a 26 px floor at 100%. Elsewhere the shell still sets
text by hand, well under that floor:

- Home app and folder labels are 14-15 px. A Home cell is about 110 x 139 px
  on the landscape panel with a 108 px icon plate, so a 26 px label does not
  fit without a new grid.
- The Battery and Weather widget captions are 12-13 px.
- The Shade's audio stream and output rows are 15 px and the notification
  source line is 14 px.
- The Wi-Fi pages use 16-21 px, the Help page 18-22 px, the theme grid 16 px
  and the recovery menu 20 px.

## What Changes

- Home's app and folder labels take the 26 px Caption role across the
  whole cell; a cell too short for the full icon plate above that label
  gets a smaller plate. Columns, pages and saved layouts do not change.
- Widget captions, the Shade's audio and notification rows, the Wi-Fi pages,
  the Help page, the theme grid and the recovery menu move onto the roles.
- Each surface reflows without clipping, ellipsizing or overlapping its own
  text at all four steps and in high contrast, in both orientations.

## Non-goals

- No change to the five roles, the rhythm, the card treatments or the icon
  set themselves.
- Text from elsewhere (app names, notification bodies) may still be cut
  short after it fills its space.
