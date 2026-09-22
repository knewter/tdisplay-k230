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
- Discover installed desktop applications through GLib's GDesktopAppInfo on
every Apps open, retain the built-ins first, and paginate the portrait list.
- Use GLib/GAppInfo launch semantics rather than a shell or custom Exec parser;
wire the service XDG data paths so Nix profile entries are visible.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `runtime/shell`: The cable-free session gains a native portrait Apps surface
  for installed desktop applications as well as its built-in terminal and monitor.

## Impact

The change affects the shell Nix module, its bar action path, a small local
Wayland client, touch-menu tests, and the `runtime/shell` OpenSpec delta. It
adds only the Wayland client libraries and protocol build tools already in the
shell's dependency family. Package build evidence can be collected on a
laptop; real-glass usability remains coordinator hardware work.
