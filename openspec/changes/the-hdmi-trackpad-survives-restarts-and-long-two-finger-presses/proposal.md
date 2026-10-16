## Why

On HDMI the operator found that the first two-finger swipe on Home did
nothing, and that holding two fingers on a widget to right-click it stopped
working. The board record shows two separate causes in `k230-touch-trackpad`:

- After the compositor restarts (every live shell deployment does this), the
  daemon still holds its old IPC connection. The next two-finger gesture fails
  on it with `BrokenPipe`
  (`k230-touch-trackpad: shell IPC phase=begin error=BrokenPipe`, 22:48:36 on
  2026-10-15), is dropped, and only the gesture after it reconnects.
- A still two-finger contact is held back from libinput for 250 ms and then
  passed on while the fingers are still down. libinput timestamps the
  contact when it is passed on, so a two-finger tap only right-clicks if the
  fingers lift within libinput's tap timeout of that moment. A press longer
  than roughly 430 ms right-clicks nothing.

## What Changes

- A two-finger gesture that finds the compositor connection stale reconnects
  once and still begins.
- A still multi-finger contact stays buffered until it moves, pinches or
  lifts. On lift, the whole press reaches libinput together, so a two-finger
  press of any length is a right-click. Movement, pinches and extra fingers
  behave as before.

**Non-goals:** changing libinput configuration, swipe or fling thresholds, or
how the shell treats a right-click.
