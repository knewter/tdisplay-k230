## Why

The persistent bar already opens Terminal and Monitor, but its Apps page is a
plain utility list. A person holding the 568×1232 device should be able to
recognise and launch the useful installed applications quickly, without a
keyboard or a general desktop launcher.

## What Changes

- Turn the existing Apps page into a compact, visually grouped launcher with
  large Terminal, Monitor, New terminal, and Back targets.
- Give the persistent controls and launcher entries distinct, restrained
  colours while retaining their current names, target sizes, and i3bar touch
  click protocol.
- Keep the launcher fixed to applications this NixOS shell provides; document
  why generic desktop-file discovery is not part of this small Pixman session.
- Extend menu protocol/action tests for the new target and preserve the
  existing Keyboard, Windows/Home, and System paths.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `runtime/shell`: The cable-free session gains a recognisable Apps launcher
  with direct touch actions for its installed terminal and monitor.

## Impact

The change affects `nix/touch-menu.sh`, its wrapper in `nix/shell.nix`, menu
protocol tests, and the `runtime/shell` OpenSpec delta. It adds no package or
desktop environment dependency. It can be tested on a laptop; a real-glass
usability check remains hardware work for the coordinator.
