## Why

The latest verified shell fixes run only after runtime activation: reboot still selects an older system. A matching-current-kernel manual boot reaches Linux but has unresolved visible navigation acceptance, so selecting it persistently would lose the usable handheld.

## What Changes

- Produce one coherent normal boot bundle from the selected NixOS configuration: Image, exact initrd wrapper, board DTB, environment init path and system identity.
- Diagnose the failed current-kernel panel trial, retaining the working vendor system and recovery path.
- Install a qualified bundle with root-partition backup and rollback; verify an ordinary physical reboot selects the same system and restores the visible usable shell.
- Publish failed trials and actual recovery, rather than treating runtime activation as persistent deployment.

## Non-goals

Mainline kernel adoption, Linux SMP, GPU acceleration, theme/performance redesign, whole-card reflashing or routine flash readback. This change repairs normal deployment consistency only. Host inspection can proceed independently; panel and ordinary reboot acceptance require the reserved physical board.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/nixos-config`: add coherent selected-system boot and safe physical rollback requirements alongside the existing console boot capability.

## Impact

`flake.nix`, a bounded normal boot bundle derivation under `nix/`, a bundle inspector and board operator controller under `tools/`, and committed `docs/evidence/boot-verification/`. Existing external-bootloader no-op activation is preserved until an explicit install is qualified. Normal selectors and stage 1 are preserved. Evidence baseline: `docs/evidence/boot-verification/2026-10-01/README.md`.
