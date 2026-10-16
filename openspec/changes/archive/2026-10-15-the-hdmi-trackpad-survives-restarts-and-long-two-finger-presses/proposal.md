## Why

On HDMI the operator found that the first two-finger swipe on Home did
nothing, and that holding two fingers on a widget to right-click it stopped
working. The board record shows two separate causes in `k230-touch-trackpad`:

- After the compositor restarts (every live shell deployment does this), the
  daemon still holds its old IPC connection. The next two-finger gesture fails
  on it with `BrokenPipe`
  (`k230-touch-trackpad: shell IPC phase=begin error=BrokenPipe`, 22:48:36 on
  2026-10-15), is dropped, and only the gesture after it reconnects.
- A two-finger press reaches libinput as an ordinary touchpad tap. The daemon
  keeps the panel's source timestamps, and uinput passes them on, so
  libinput measures the real duration. Any two-finger press longer than
  libinput's tap timeout (about 180 ms) is not a right-click. The operator's
  "long two-finger press" therefore never reliably opened rearrange mode.
  On top of that, after 250 ms the daemon passed a still pair to libinput
  while the fingers were down.

## What Changes

- A two-finger gesture that finds the compositor connection stale reconnects
  once and still begins.
- A still multi-finger contact stays buffered until it moves, pinches or
  lifts. When it lifts without having moved, the buffered press is
  presented to libinput as a 40 ms tap that ends at the lift. A two-finger
  press of any length is then a right-click, and three fingers are a middle
  click. Movement, pinches and extra fingers behave as before.

**Non-goals:** changing libinput configuration, swipe or fling thresholds, or
how the shell treats a right-click.
