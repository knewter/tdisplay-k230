## Why

On HDMI the operator could remove widgets on Home's first page but not on the
second. The board log shows their two-finger trackpad presses on page 2 ending
in `touch-cancel`, and a grim taken at that moment shows Home frozen about 44%
of the way between pages 1 and 2. A two-finger trackpad pan reaches Home as a
synthetic touch (`TRACKPAD_PAN_ID`). When it ends near where it started,
`main.rs` cancels it, and `HomePager::cancel` stops the drag without settling,
so the pager stays between pages. Painting follows the fractional position,
but hit testing rounds to the nearest page, so presses on what looks like page
2 land on page 1's cells.

Removing the only widget on the last page shows the same gap: the page is
deleted, but the pager stays at its index and Home shows a blank page with no
page dots.

## What Changes

- A cancelled page drag settles to the nearest page.
- At rest, the pager settles onto a whole page that exists. This covers being
  left between pages, or past the last page after the page count shrank,
  including while rearranging.

**Non-goals:** changing how trackpad pans are turned into touches, or
swipe thresholds and fling physics.
