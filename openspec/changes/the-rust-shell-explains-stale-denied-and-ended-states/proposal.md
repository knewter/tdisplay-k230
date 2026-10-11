## Why
A person using the Rust coherent shell who sees a window list that is still loading, empty, or stale, who is denied a system action, or whose video ends, stops, or is cancelled, gets no short explanation and no named way out. The predecessor change `the-shell-makes-recovery-routes-legible` (superseded 2026-10-11) targeted the Python/C touch-launcher, which the shipped Rust shell (`k230-coherent-shell` / `k230-mainline-drm-shell`) no longer launches. This change carries the still-unmet requirements to `nix/rust-shell-client`.

## What Changes
- Rust shell surfaces use short person-facing copy and a visible Back, Apps, Home, Retry, Cancel, or Stop action for: loading, empty, and stale window lists; a denied system action; video Stop, end-of-file, and cancelled.
- No raw filesystem path, helper/GLib diagnostic, or secret is rendered; those stay in logs.

## Dropped from the predecessor, and why
- Home disclosure ("Windows hides Home in a persistent bar"): the accepted `runtime/home-screen` gesture topology has no persistent bar, so the premise no longer exists. <!-- UNVERIFIED: no board capture of a bar-less discoverability problem. -->
- `nix build .#touch-launcher`: touch-launcher is reachable only via touch-menu.sh from the swaybar, which `nix/shell.nix` omits under `coherentShell` (~889-903); the Rust shell runs Home/drawer/card helpers (~1499, ~1592).
- Failed-launch recovery: already required by accepted `runtime/app-launcher` (~22-25), with board evidence from archived `2026-10-08-the-launcher-explains-app-actions`. Not restated.

## Capabilities
### Modified Capabilities
- `runtime/card-shell`: loading/empty/stale window list; no raw diagnostics.
- `runtime/device-settings`: denied system action.
- `runtime/video`: Stop, EOF, cancelled recovery.

## Non-goals
Modal error stacks, a global notification system, moving video/card lifecycle ownership, reviving touch-launcher.

## Impact
`nix/rust-shell-client` (state copy, rendering, tests). Host work needs no board; the real-finger capture needs the physical board and a deployed image.
