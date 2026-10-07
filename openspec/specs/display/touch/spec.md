# display/touch Specification

## Purpose
Defines what the board does when a person touches the screen.

## Requirements

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

### Requirement: While HDMI is the active output, touch is re-emitted as a virtual touchpad

<!-- Grounding: installed board/service evidence in docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/ and overall physical operator acceptance in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. Additional capture is waived. Individual unreported gesture cases are not new physical proof. -->

While an HDMI connector is the active display output (per
`display/hdmi`'s reboot-based device-tree swap in
`plugging-in-hdmi-moves-the-display`), the GT9895 touchscreen's raw
`ABS_MT_*` contact stream SHALL be exclusively grabbed (`EVIOCGRAB`) and
re-emitted through a virtual `uinput` device declared with touchpad
properties (`INPUT_PROP_POINTER` + `INPUT_PROP_BUTTONPAD`, `BTN_TOOL_FINGER`/
`_DOUBLETAP`/`_TRIPLETAP`, no `INPUT_PROP_DIRECT`), so that libinput
classifies it as a touchpad and provides pointer motion, tap-to-click,
two-finger scroll, and pinch/swipe gestures for the HDMI session, in place
of the panel-mode absolute touch-to-output mapping. Qualified two-contact shell gestures and three-contact bottom keyboard gestures
may instead translate to the existing logical touch policies through the bounded
shell gesture path; ordinary application center scrolling/pinch and pointer input
remain on the touchpad path. While the panel (not
HDMI) is the active output, the touchscreen SHALL be left ungrabbed and
unmodified, continuing to report absolute coordinates as
`display/touch`'s existing digitizer-range requirement already states.

*Grounding: host relay/mode/ioctl tests and the independent Linux-header
comparison (`cargo test`); the earlier host udev classification in
`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/host-uinput-classification.md`;
and the real contact/operator checkpoint plus installed-board service probes
in `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/`.
The operator confirmed cursor motion, and Sway classifies the actual virtual
device as a touchpad with tapping enabled. The operator subsequently accepts the HDMI trackpad as working;
`docs/evidence/proposal-closeout/2026-10-01/trackpad.md` records that acceptance and earlier panel-return feedback.
It does not manufacture individual per-gesture observations.*

#### Scenario: HDMI is the active output and a finger moves across the glass

- **WHEN** an HDMI connector is `connected` per `/sys/class/drm/*/status`
  and a finger drags across the touchscreen
- **THEN** the Wayland session under HDMI shows the pointer move, with no
  visible input reaching the panel-mode absolute touch path

#### Scenario: The panel becomes the active output again

- **WHEN** the board is next booted with the panel DTB (or, if
  `plugging-in-hdmi-moves-the-display` group 4's no-reboot switching later
  lands, the HDMI connector reports `disconnected` while running)
- **THEN** the touchscreen is ungrabbed and the coordinator's direct
  absolute touch-to-output mapping behaves exactly as it did before this
  change existed

#### Scenario: Mode switching is verified

- **WHEN** the touchpad-relay capability is claimed to work
- **THEN** the evidence includes the installed-board mode/service record and physical
  operator feedback about HDMI trackpad behavior; an explicit operator capture
  waiver permits that report instead of an additional photograph, and host
  tests alone do not establish physical behavior

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/trackpad.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: The mainline touch candidate is not reported as working without board evidence

The project MAY describe the board's Goodix-compatible touch controller in
the opt-in mainline DRM device tree. It SHALL preserve the candidate's
reported digitizer dimensions and GPIO/interrupt source from the board DTS,
and SHALL record serial probe evidence separately from physical touch
acceptance. Coordinate mapping and physical touch behavior remain UNVERIFIED
until deliberate on-panel interaction is recorded.

*Grounding: the candidate node in
`nix/dts/k230-tdisplay-mainline-drm.dts` follows the board wiring recorded in
`nix/dts/k230-tdisplay.dts`; the exact host DTB check and limits are in
`docs/evidence/mainline-display-dtb.md`. The pinned mainline Goodix Berlin
I2C driver includes `goodix,gt9916`, and the later committed
`docs/evidence/mainline-display/physical-2026-10-01/README.md` records Goodix
input registration. Registration is partial probe evidence; it does not prove
coordinate mapping or deliberate finger interaction.*

#### Scenario: Someone asks whether touch works under the mainline candidate

- **WHEN** only the candidate source or a round-tripped host DTB is available
- **THEN** the response leaves controller compatibility, probe, and touch
  interaction UNVERIFIED

### Requirement: A finger on the glass drives the shell under the mainline kernel
On the mainline full shell, a deliberate finger tap or drag on the panel SHALL
reach sway and change what the shell shows, as it does under the vendor kernel.

#### Scenario: Tap opens something visible
- **WHEN** a person taps a Home target on the mainline full shell while the camera records
- **THEN** the panel changes as it does for the same tap on the vendor-kernel shell, and sway's input log records the touch
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): controller complete contact (4 taps) on the full shell; operator reported the shell responded. Camera did not capture the taps. -->

#### Scenario: Touch capture completes without a timeout
- **WHEN** the trial controller captures a long touch session
- **THEN** it reports a complete contact summary instead of an unverified retrieval
