## Context

`mkBoardImage cfg kernel` (`flake.nix`) always used the vendor device tree
package. `kernelMainlineDrmShellBootFiles` already presents the mainline DRM
tree as `k230-tdisplay.dtb` for the installed board.

## Goals / Non-Goals

**Goals:** `.#sdImage` produces the same system, kernel, initrd and DTB the board
runs today. Every vendor image stays byte-identical.

**Non-Goals:** release tooling (`sdImage-coherent`) and stage-1 changes.

## Decisions

- `mkBoardImageWith { cfg, kernel, deviceTree ? vendor }` is added, and
  `mkBoardImage` becomes a wrapper for it, so existing callers keep the same
  derivations. Tasks check this by comparing drvPaths.
- The renamed mainline DTB becomes the package `mainlineDrmDeviceTreeNormalName`.
  The boot bundle and the image share it, so they cannot drift.
- The kernel is taken from the system's own `boot.kernelPackages.kernel`.

## Risks / Trade-offs

- A fresh card has never booted mainline from first power-on. Root growth and
  path registration run on first boot, while the installed board only ever ran
  them under the vendor kernel. Mitigation: the operator-scheduled flash task
  stays open until it is observed.
