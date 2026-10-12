## Why
A person holding the handheld cannot open an app's window list with a finger. In
the Rust shell the per-app menu (`app_actions::AppMenu`) opens only on a mouse
right-click (`nix/rust-shell-client/src/main.rs`, pointer button `0x111`). A long
press in the drawer starts the drag-to-Home move instead. So the loading, "No
open windows" and "That window has closed" recovery states added by
`the-rust-shell-explains-stale-denied-and-ended-states` (archived 2026-10-11)
can be reached only with a mouse. None of that change's recovery states has
been observed on the glass with a real finger. The operator closed the
predecessor on 2026-10-11 without that capture ("just close it it's good")
after confirming that brightness works. This change carries the unperformed
capture and the touch-reachability gap.

## What Changes
- A touch route opens an app's window list without conflicting with the
  drawer's long-press drag to Home.
- A real-finger capture shows each recovery state on the glass: empty, stale,
  denied, video stopped and cancelled. "Video ended" is included when a short
  clip is available.

## Capabilities
### Modified Capabilities
- `runtime/card-shell`: the window list is reachable by touch.

## Non-goals
Changing the recovery copy or contract (`src/recovery.rs`), the video session's
lifecycle ownership, or the drawer's drag-to-Home gesture.

## Impact
`nix/rust-shell-client` (touch entry to the menu). The capture needs the
physical board, the bench webcam and the operator's finger. The touch entry's
host tests do not.
