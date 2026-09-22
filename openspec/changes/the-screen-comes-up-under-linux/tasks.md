# Tasks

Every group here is a **hardware claim**. QEMU's `k230` machine models no
display pipeline, so nothing in this change can be proven under emulation.

## 1. Extract the working init sequence

- [x] 1.1 Transcribe the RM69A10 init sequence, PHY frequency, lane count and delays from LilyGO's `mpp/kernel/connector/src/rm69a10.c` into a reviewable table. Verify by committing it to `docs/evidence/rm69a10-init-sequence.md` with each entry citing its line in the vendor source
- [x] 1.2 Record the vendor bring-up order and GPIO usage from `docs/rtsmart-boot-log.txt`, including the three resets on GPIO22 before init. Verify by extending that document and noting anything the boot log shows that the source does not explain

## 2. A device tree for this panel

- [x] 2.1 Write `display-rm69a10-568x1232.dtsi` for `panel-canaan-universal`, modelled on `display-st7701-480x800.dtsi`, carrying the sequence from 1.1. Verify by building the DTB with `nix build .#deviceTree` and checking it compiles without warnings
- [x] 2.2 Write this board's top-level `.dts` including that panel, and record every divergence from `k230-canmv-v3-lcd.dts`. Verify by committing the divergence list to `docs/evidence/dts-divergence.md` and building the DTB
- [x] 2.3 Boot the board with the new device tree and confirm the panel probes. Verify by capturing the kernel log to `docs/evidence/panel-probe.txt` showing the panel bound with no DSI errors

## 3. The screen actually shows something

- [x] 3.1 Confirm a framebuffer at 568x1232 is present. Verify with `fbset -i` over the serial console, captured into `docs/evidence/panel-probe.txt`
- [x] 3.2 Write a test pattern to the framebuffer and photograph the physical screen. Verify by committing the photograph to `docs/evidence/` — a framebuffer node is explicitly not sufficient evidence for this task
- [x] 3.3 Put the kernel console on the panel so the board is usable without a serial cable. Verify with a photograph of the boot messages on the screen

## 4. Touch

- [x] 4.1 Determine which driver can drive this part, by experiment rather than assumption: mainline has no GT9895 support at any version (`docs/evidence/gt9895-touch.md`). Verify by booting with `compatible = "goodix,gt9916"` against a backported `goodix_berlin` and recording in `docs/evidence/touch-probe.txt` whether it binds
- [x] 4.1b Depending on 4.1, either add a `gt9895_data` chip entry to the backported driver or port LilyGO's RT-Smart `gt9895.c`. **Neither was needed.** The backported `goodix_berlin` drives the GT9895 with the existing `gt9916` chip data once the device tree declares the interrupt correctly: `IRQ_TYPE_EDGE_FALLING` yields 0 interrupts, `IRQ_TYPE_LEVEL_LOW` yields 2173 in a 45 s capture, with multitouch events on `/dev/input/event0`. Both branches of this task assumed the driver could not drive the part; it can. See `docs/evidence/touch-reports.md`.
      - REOPENED. Closed earlier as "neither branch needed, the Berlin
        backport works". It binds, but two evtest runs with a finger on
        the panel produced zero events and /proc/interrupts shows only 4
        interrupts since boot on the goodix-berlin line. Binding is not
        working. See docs/evidence/touch-probe.txt. Verify with `nix build .#packages.x86_64-linux.xuantie-kernel` and by recording the choice and its reason in `docs/evidence/kernel-patches.md`
      - Resolved to NEITHER branch. The GT9895 answers the Berlin protocol,
        so the existing v6.12 backport binds it through the
        `"goodix,gt9895", "goodix,gt9916"` fallback and no driver change is
        needed. The first branch was not available in any case: the driver
        has no chip table to add an entry to. Recorded in kernel-patches.md.
- [x] 4.2 Add the GT9895 to the device tree on I2C with reset GPIO24, interrupt GPIO23. Verify by booting and capturing the probe to `docs/evidence/touch-probe.txt`
- [x] 4.3 Confirm touches report coordinates that track a deliberate movement across the panel. Verify with a recorded `evtest` session committed to `docs/evidence/touch-evtest.txt`, showing a drag rather than a single tap, and confirm the axes are neither swapped nor mirrored. Drag: continuous slot-0 trajectory spanning X 86..728 and Y 765..1765 (`docs/evidence/touch-reports.md`). Orientation: a drag cannot establish it, so two taps on a drawn target at opposite corners were used, with predictions recorded before reading the result -- observed (250,208) and (850,2130) against (216,234) and (807,2166) predicted, matching the unmirrored unswapped mapping and excluding swap, X-mirror and Y-mirror.

## 5. Ground the specs

- [x] 5.1 Resolve the `UNVERIFIED` markers in `display/panel` and `display/touch` against the committed photograph and `evtest` session, or restate what remains unproven. Verify with `openspec validate the-screen-comes-up-under-linux`. `display/panel`: resolved against the committed photographs; what remains unproven is restated precisely -- a uniform whole-frame vertical shift of ~2.8 panel rows, measured in real panel rows after rectification, mechanism not established. `display/touch`: resolved -- reporting and axis orientation both grounded, with the wider-than-declared X range recorded as a caveat.
- [x] 5.2 Record the carried patches and device tree divergences under the modified `system/kernel` requirement so a later kernel bump can tell what is still needed. Verify with `openspec validate --all`
