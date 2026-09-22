## Why

A four-button status row is an entry point, but not a pleasant application
launcher on a 568×1232 handheld. Opening an app needs a full portrait surface
with enough hierarchy, labels, and spacing to be read and tapped comfortably.

## What Changes

- Keep the persistent swaybar controls as the always-available route to Apps,
  Windows, Keyboard, and System.
- Make Apps open a lightweight native Wayland portrait launcher with a title,
  large Terminal, Monitor, and New terminal cards, and an explicit Back
  control.
- Add a small unprivileged action bridge so launcher cards preserve the
  terminal and monitor focus-or-start behavior already used by the menu.
- Package the launcher from local C source with Wayland SHM and layer-shell;
  do not add GTK, Qt, a desktop-file scanner, or a session service.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `runtime/shell`: The cable-free session gains a native portrait Apps surface
  for its installed terminal and monitor.

## Impact

The change affects the shell Nix module, its bar action path, a small local
Wayland client, touch-menu tests, and the `runtime/shell` OpenSpec delta. It
adds only the Wayland client libraries and protocol build tools already in the
shell's dependency family. Package build evidence can be collected on a
laptop; real-glass usability remains coordinator hardware work.
