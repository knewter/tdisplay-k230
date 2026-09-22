## Purpose

Defines what the board does when a person touches the screen.

## ADDED Requirements

### Requirement: Touches are reported as input events

<!-- RESOLVED.

Reporting: changing only the device tree interrupt type, same kernel,
IRQ_TYPE_EDGE_FALLING gives 0 interrupts and IRQ_TYPE_LEVEL_LOW gives
2173 in a 45 s capture, with tracking IDs, BTN_TOUCH, ABS_MT_TOUCH_MAJOR
ramping, and a continuous slot-0 trajectory spanning X 86..728 and
Y 765..1765. docs/evidence/touch-reports.md.

Orientation: settled by tapping a drawn target at two opposite corners,
with the predictions for correct / swapped / X-mirrored / Y-mirrored
written down before the result was read. Observed (250,208) and
(850,2130) against (216,234) and (807,2166) predicted for the
unmirrored unswapped mapping; the three competing hypotheses are out by
240 to 1900 units. docs/evidence/touch-evtest.txt.

One caveat recorded rather than smoothed over: reported X was seen to
reach 1058, above the 1023 implied by touchscreen-size-x = <1024>, so
the controller's native range is slightly wider than the device tree
declares and a consumer must clamp. -->

The GT9895 controller SHALL be probed and SHALL report touches as standard
Linux input events, over the digitizer's native 1024x2400 range declared via
`touchscreen-size-x` / `touchscreen-size-y`, mapping monotonically onto the
panel with the axes neither swapped nor mirrored, so that a consumer scaling
by 568/1024 and 1232/2400 lands a touch where it is seen.

*Why not report in the panel's own 568x1232 space, which is what a reader
would expect: the driver cannot. `goodix_berlin_core.c` reports through
`touchscreen_report_pos()`, which applies the swap and invert properties and
**does not scale**; `touchscreen-size-x/y` only declare the advertised
maximum, and the controller's raw values pass through unchanged. Pre-scaling
in the kernel would mean patching the backport further and discarding
digitizer resolution. Reporting the native grid and letting the consumer map
it to the display is the ordinary Linux arrangement.*

*Grounding for the hardware: the schematic gives the controller as a GT9895 on
I2C, with reset on GPIO24, SCL on GPIO36, SDA on GPIO37 and interrupt on
GPIO23. The shipped RT-Smart firmware drives it.*

#### Scenario: A person touches the screen

- **WHEN** the panel is touched
- **THEN** an input event is emitted whose coordinates correspond to where it was touched

#### Scenario: Touch is verified

- **WHEN** touch support is claimed to work
- **THEN** the evidence is a recorded `evtest` session showing coordinates that track a deliberate movement, not only that a device node exists

### Requirement: Touch support is a recorded divergence from upstream

The GT9895 is not supported by the pinned kernel and its support SHALL be
carried as an explicit patch, recorded with what was backported and from where,
so the cost of the pin is visible when the kernel is next moved.

*Grounding: the pinned Xuantie kernel carries `drivers/input/touchscreen/goodix.c`,
which serves the older GT9xx generation, and no `goodix_berlin` source. But
the gap is larger than "backport it": `goodix_berlin` landed in **v6.9**,
not 6.7, and **mainline has never supported the GT9895 at any version**. At
v6.18 the I2C driver matches only `goodix,gt9916` and the binding
enumerates `gt9897` and `gt9916`. See `docs/evidence/gt9895-touch.md`.*

What the project HAS is LilyGO's RT-Smart `gt9895.c` (219 lines): not a
Linux driver, but a working register-level description of this part on this
board.

The route SHALL therefore be chosen by experiment rather than asserted. The
`goodix,gt9916` compatible is a one-word change and the Berlin generation
shares a programming model, so whether the existing driver drives this part
is cheap to discover once the board boots — and the answer decides between
teaching the mainline driver the GT9895 and porting the vendor one.

#### Scenario: The kernel pin is moved

- **WHEN** someone updates the kernel revision
- **THEN** the repository states which patches must be carried forward and why
