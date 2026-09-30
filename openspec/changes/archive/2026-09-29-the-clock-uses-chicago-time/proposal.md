## Why

The operator wants the handheld clock to use America/Chicago rather than UTC. The timezone must be the reproducible image default, so a new image uses it without restoring user state.

## What Changes

- Select `America/Chicago` in the shared NixOS configuration.
- Apply it to the running board and record its effective timezone and local clock.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/nixos-config`: the image provides America/Chicago as its local timezone.

## Impact

`nix/k230.nix`, the generated system closure, and physical console evidence. The shell clock already uses libc local time. This does not change UTC system time, NTP policy, RTC persistence, gesture behavior, or add timezone settings UI. Nix evaluation/build is host proof; observing the effective device setting requires the reserved board.
