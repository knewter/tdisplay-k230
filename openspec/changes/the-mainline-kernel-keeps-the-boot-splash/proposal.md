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
measurement selected the minimal DRM owner). Boot animation. Stage 1 changes
beyond the bounded DMA-request correction described below.
Any claim that a host build, QEMU run or injected event satisfies a task that
says *Hardware*.

**Needs the physical board** for every hardware task. The device-tree and
image tasks are laptop claims. Recovery stays as it was: a second card with
the last known-good image, and `docs/uboot-ums.md` for flashing in place.

## Authorized follow-up: stage 1 DMA request

After the accepted default reproduced brief garbled-logo frames on a normal
warm reboot (2026-10-20), the operator authorized testing the stage 1 splash
DMA-request correction, `0x40` to `0x4f`, in
`nix/patches/uboot-k230/0004-rm69a10-logo-port.patch`. The pinned vendor
`kd_vo_osd_set_dma_request` sets the lower four bits to `0xf`; the mainline
driver also uses `0x4f` for this pixel format. This is a source-grounded
candidate, not a proven cause or fix. The patch must preserve pixel format,
framebuffer address, stride, timings, SPL and environment. Build, verified
backup/readback and rollback precede a filmed warm-boot trial. The existing
task 4.1 and its ±0.1 s video/kernel timing gate remain open until proved.

## Capabilities

### Modified Capabilities

`display/boot-splash` and `image/boot-chain`. Existing deltas record the
mainline default and framebuffer reservation; the splash delta also requires
a stable image through the first compositor frame. Its remaining physical
proof is task 4.1, not the authorization to test a candidate.

## Impact

`nix/dts/k230-tdisplay-mainline-drm-common.dtsi` (a `reserved-memory` node fed
from the flake's splash-address constant), the mainline kernel patch set in
`nix/` (panel and DRM handoff), `flake.nix` and `nix/panel-console.nix`
(the selected default), the bounded stage 1 splash patch above, and new
evidence under `docs/evidence/`.
