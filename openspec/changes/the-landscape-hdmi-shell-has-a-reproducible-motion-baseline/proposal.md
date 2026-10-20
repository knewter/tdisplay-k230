## Why

The operator chose to keep the current 1280×800 landscape HDMI layout on
2026-10-19. The existing performance collector accepts only 1920×1080 portrait,
so it cannot measure this setup without mislabelling the result.

## What Changes

- Add an explicit 1280×800 normal-transform diagnostic capture profile.
- Report the installed compositor's one- and two-Foot motion baseline with
  exact runtime identity, frame CPU time and dispatch-to-presentation timing.
- Keep landscape evidence separate from the portrait comparison and real-contact
  acceptance gates. Preserve the portrait proposal and every unchecked task.

Non-goals: changing resolution, orientation, renderer/defaults, image or input
mode; selecting an optimization before measurement; setting new performance
budgets; claiming real-finger or optical acceptance; closing the portrait scope.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is diagnostic tooling and evidence only (`skip_specs: true`).
The accepted `runtime/shell` landscape behavior remains unchanged.

## Impact

Userspace host/board capture scripts, strict parser fixtures and committed
`docs/evidence/landscape-hdmi-baseline/` evidence. Host tests need no board;
measuring the running DRM compositor needs the exclusive board lease. No
Nix rebuild, flashing, reboot, kernel or stage-1 changes are planned.
