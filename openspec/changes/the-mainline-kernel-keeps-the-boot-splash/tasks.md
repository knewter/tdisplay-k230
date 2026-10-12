# Tasks

Carried from `the-screen-lights-before-linux` (archived 2026-10-11 by an
operator-authorized scope split). Tasks marked "Moved from" keep their
original text and proof commands verbatim after the prefix. Nothing here is
ticked: none was performed. Hardware tasks take the board and its serial
port for one operator at a time and are proven by a photograph, film or
console capture committed under `docs/evidence/`; a host build, QEMU run or
injected event does not satisfy them.

## 1. Mainline prerequisites (laptop claims)

- [ ] 1.1 Add a `reserved-memory` framebuffer node for the splash buffer to the mainline device tree (`nix/dts/k230-tdisplay-mainline-drm-common.dtsi` or the file that the hotplug tree includes), with `reg` taken from the same flake constant as U-Boot's splash Kconfig symbol, as task 3.5 did for `nix/dts/k230-tdisplay.dts`. Verify with `nix build .#mainlineDrmHotplugDeviceTreeNormalName` and `fdtget` on the resulting DTB printing the chosen address and size under `/reserved-memory` -- laptop claim
- [ ] 1.2 Carry the stage-1 handoff behaviour (leave a flagged panel alone on the first prepare, no fbdev modeset over the logo, first VO/DSI enable preserved when the mode matches) into the mainline panel/DRM driver, or show with source and a build why the mainline driver already does it, and record each change with its drop condition in `docs/evidence/kernel-patches.md`. Verify with the mainline kernel `nix build` of the attribute `.#sdImage` uses -- laptop claim
- [ ] 1.3 Build an image with `k230.panelConsole = false` on the mainline shell (an `extendModules` target or the flipped default) whose boot partition carries `logo.xrgb` (2 799 104 bytes) and whose `bootargs.txt` lacks `console=tty0`. Verify with `nix build` of that image and `docs/evidence/splash-close-sdimage/inspect-image.py` adapted to expect the logo -- laptop claim

## 2. Hardware gates carried from the predecessor

Each task below is the predecessor's own, in the same order it had there;
the second-card rule applies to every one: flash a second card and keep the
known-good one. `docs/uboot-ums.md` is the in-place flashing and recovery path.
Run them on the image from 1.3.

- [ ] 2.1 Moved from `the-screen-lights-before-linux` 3.6: 3.6 **Hardware.** Flash a second card, keep the known-good one, take the board, and boot. Verify by committing a photograph of the splash on the glass and a `./tools/capture-boot.py` capture in which the moment of the photograph precedes `Starting kernel`, both under `docs/evidence/` and referenced from `docs/evidence/boot-splash.md` — hardware claim
- [ ] 2.2 Moved from `the-screen-lights-before-linux` 3.7: 3.7 **Hardware.** Measure the U-Boot-lit image with `tools/panel-measure.py` exactly as `dsi-hsfreqrange-hardcoded.md` measured the Linux one. If it rolls or is dark, fall back to LILYGO's full table (39.6 MHz / `0x96`) to prove the path, then change one parameter at a time until our mode is stable, recording each step. Verify by committing the measurement table to `docs/evidence/boot-splash.md` with motion figures at or below the `0x87` row of the earlier document, and releasing the board — hardware claim
- [ ] 2.3 Moved from `the-screen-lights-before-linux` 4.3: 4.3 **Hardware.** Boot the new kernel on the card from 3.6 and leave the board at the serial prompt with nothing opening the display. Verify by committing a capture to `docs/evidence/boot-splash-handoff.md` showing `/proc/device-tree/chosen` carrying the flag, the driver's "stage 1 splash: leaving fbdev unset" message, no panel prepare/init sequence before a DRM client starts, `ls /dev/fb0` failing, and a photograph of the splash still on the glass at the prompt. The panel driver's "left as stage 1 set it" line belongs to the first DRM modeset in 4.4, not the idle-kernel phase — hardware claim
- [ ] 2.4 Moved from `the-screen-lights-before-linux` 5.4: 5.4 **Hardware.** Film a complete boot from power-on to the owner's last frame — and, if `the-screen-runs-a-shell-not-a-console` has landed, to the compositor's first frame. Verify by committing the frame timings to `docs/evidence/boot-splash-handoff.md` showing no dark frame between the splash appearing and the last frame filmed, and the first Linux frame indistinguishable from the last stage 1 frame. Release the board — hardware claim

## 3. Decide the default

- [ ] 3.1 Only if 2.1 to 2.4 passed on the mainline image: change the daily configuration to `k230.panelConsole = false` (removing the explicit `true` at `flake.nix:130-134`) and restate the `display/boot-splash` requirement "The splash and the panel console are a build-time choice" to what was measured, resolving its `UNVERIFIED` marker. Verify with `openspec validate the-mainline-kernel-keeps-the-boot-splash --strict` and the `nix eval` of both option states -- laptop claim. If a gate fails, record the failure under `docs/evidence/` and leave the default `true`.

**Proves group 1.** `nix build .#mainlineDrmHotplugDeviceTreeNormalName` and the image build, laptop claims. **Proves group 2.** The photograph, film and captures named in each task, hardware claims.
