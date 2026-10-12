## Why

The board's daily system is now the mainline-kernel `k230-mainline-drm-shell`
(`flake.nix:238`), and on it the glass is dark from power-on until the shell
draws. `the-screen-lights-before-linux` built and photographed the stage 1
splash on the vendor kernel, but its Linux handoff was never made to hold on
the card the board runs today, so the daily image deliberately ships without
the splash: the coherent shell sets `k230.panelConsole = true`
(`flake.nix:130-134`), `splashImage` is then `null` (`flake.nix:84`) and
`nix/sd-image.nix:86-88` leaves `logo.xrgb` off the boot partition.

On 2026-10-11 the operator chose to close that change with a successor
rather than carry its unperformed hardware tasks. This change holds exactly
those tasks, plus the work the mainline kernel adds: its device tree has no
`reserved-memory` or framebuffer node (task 3.5 of the predecessor added one
only to the vendor `nix/dts/k230-tdisplay.dts`), and its panel/DRM driver has
not been shown to leave a stage 1 image alone.

## What Changes

- The splash buffer is reserved from the mainline kernel by its device tree.
- The stage 1 handoff is re-proved on the mainline panel/DRM driver, on a
  second card, with the known-good card kept.
- An image with `k230.panelConsole = false` is built and its boot partition
  carries `logo.xrgb`.
- The physical tasks the predecessor left open are carried verbatim: the
  second-card boot photograph (3.6), the U-Boot-lit motion measurement (3.7),
  the idle-kernel handoff capture (4.3), the power-on film (5.4), and the
  `panelConsole = true` image inspection (6.1) if it was not performed there.

**Non-goals.** Plymouth (task 5.2 of the predecessor was not taken; the
measurement selected the minimal DRM owner). Boot animation. Changing the
stage 1 splash port, which the predecessor already delivered and archived.
Any claim that a host build, QEMU run or injected event satisfies a task that
says *Hardware*.

**Needs the physical board** for every hardware task. The device-tree and
image tasks are laptop claims. Recovery stays as it was: a second card with
the last known-good image, and `docs/uboot-ums.md` for flashing in place.

## Capabilities

### Modified Capabilities

None yet. The requirements this change must satisfy are the ones
`the-screen-lights-before-linux` archived into `display/boot-splash` and
`image/boot-chain`; their `UNVERIFIED` markers point here. A delta is added
when a hardware result restates one.

## Impact

`nix/dts/k230-tdisplay-mainline-drm-common.dtsi` (a `reserved-memory` node fed
from the flake's splash-address constant), the mainline kernel patch set in
`nix/` (panel and DRM handoff), `flake.nix` and `nix/panel-console.nix`
(the selected default), and new evidence under `docs/evidence/`.
