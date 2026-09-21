# Tasks

Every group here is a **hardware claim**. QEMU's `k230` machine models no
display pipeline, so nothing in this change can be proven under emulation.

## 1. Extract the working init sequence

- [x] 1.1 Transcribe the RM69A10 init sequence, PHY frequency, lane count and delays from LilyGO's `mpp/kernel/connector/src/rm69a10.c` into a reviewable table. Verify by committing it to `docs/evidence/rm69a10-init-sequence.md` with each entry citing its line in the vendor source
- [x] 1.2 Record the vendor bring-up order and GPIO usage from `docs/rtsmart-boot-log.txt`, including the three resets on GPIO22 before init. Verify by extending that document and noting anything the boot log shows that the source does not explain

## 2. A device tree for this panel

- [x] 2.1 Write `display-rm69a10-568x1232.dtsi` for `panel-canaan-universal`, modelled on `display-st7701-480x800.dtsi`, carrying the sequence from 1.1. Verify by building the DTB with `nix build .#deviceTree` and checking it compiles without warnings
- [x] 2.2 Write this board's top-level `.dts` including that panel, and record every divergence from `k230-canmv-v3-lcd.dts`. Verify by committing the divergence list to `docs/evidence/dts-divergence.md` and building the DTB
- [ ] 2.3 Boot the board with the new device tree and confirm the panel probes. Verify by capturing the kernel log to `docs/evidence/panel-probe.txt` showing the panel bound with no DSI errors

## 3. The screen actually shows something

- [ ] 3.1 Confirm a framebuffer at 568x1232 is present. Verify with `fbset -i` over the serial console, captured into `docs/evidence/panel-probe.txt`
- [ ] 3.2 Write a test pattern to the framebuffer and photograph the physical screen. Verify by committing the photograph to `docs/evidence/` — a framebuffer node is explicitly not sufficient evidence for this task
- [ ] 3.3 Put the kernel console on the panel so the board is usable without a serial cable. Verify with a photograph of the boot messages on the screen

## 4. Touch

- [ ] 4.1 Backport `goodix_berlin` onto the pinned 6.6 Xuantie tree as a recorded patch. Verify with `nix build .#kernel` and by committing the patch's origin and rationale to `docs/evidence/kernel-patches.md`
- [ ] 4.2 Add the GT9895 to the device tree on I2C with reset GPIO24, interrupt GPIO23. Verify by booting and capturing the probe to `docs/evidence/touch-probe.txt`
- [ ] 4.3 Confirm touches report coordinates that track a deliberate movement across the panel. Verify with a recorded `evtest` session committed to `docs/evidence/touch-evtest.txt`, showing a drag rather than a single tap, and confirm the axes are neither swapped nor mirrored

## 5. Ground the specs

- [ ] 5.1 Resolve the `UNVERIFIED` markers in `display/panel` and `display/touch` against the committed photograph and `evtest` session, or restate what remains unproven. Verify with `openspec validate the-screen-comes-up-under-linux`
- [ ] 5.2 Record the carried patches and device tree divergences under the modified `system/kernel` requirement so a later kernel bump can tell what is still needed. Verify with `openspec validate --all`
