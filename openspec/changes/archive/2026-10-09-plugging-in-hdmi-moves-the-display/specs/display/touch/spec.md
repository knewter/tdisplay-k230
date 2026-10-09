## ADDED Requirements

### Requirement: Touch shares its reset and interrupt lines with the optional HDMI bridge

Touch's reset (GPIO24) and interrupt (GPIO23) lines SHALL be treated as
shared with the optional LT9611 HDMI bridge, not as touch-exclusive pins,
by any future change to this capability. The panel's own reset and enable
lines (GPIO22/GPIO25) are not part of this sharing and are unaffected.

*Grounding: schematic `T-Display K230_V1.0_NEW.pdf` sheet "Video" ties
`HDMI_RSTN`→`TP_RST` and `HDMI_INT`→`TP_INT` as single unbroken wires — the
LT9611's reset and interrupt pins are the same physical nets as touch's,
not merely the same GPIO number reused in a different device tree. The
vendor's own LT9611 device-tree node (`k230-canmv-v3.dts:64,66`, pinned
kernel tree) requests `GPIO_ACTIVE_HIGH` reset and `IRQ_TYPE_EDGE_FALLING`
on these pins, while this board's touch node
(`nix/dts/k230-tdisplay.dts:200,224`) requests `GPIO_ACTIVE_LOW` reset and
`IRQ_TYPE_LEVEL_LOW` — a real disagreement on the same wire, not a
cosmetic one. Full detail, including the specific schematic sheets and net
labels, in `docs/research/hdmi-hotplug.md` §1–§2.*

The vendor baseline `nix/dts/k230-tdisplay.dts` carries touch only,
matching the vendor sources surveyed (`docs/research/hdmi-hotplug.md` §3).
The later mainline HDMI tree from task group 7 combines touch and LT9611
without giving the bridge reset/IRQ ownership: its polling bridge waits
for the touch driver to bind before programming the shared-reset device.
That matching trial and the operator's acceptance are recorded in
`docs/evidence/hdmi-mainline/README.md`.

#### Scenario: A change proposes adding an LT9611 node to the default tree

- **WHEN** a future change proposes adding the LT9611 to the same device
  tree that already carries the GT9895 touch node
- **THEN** the review checks the proposed GPIO23/24 reset polarity and
  interrupt trigger type against both consumers' existing requirements, not
  only against the LT9611 in isolation, since the pins are shared hardware,
  not independently configurable per node

## MODIFIED Requirements

### Requirement: While HDMI is the active output, touch is re-emitted as a virtual touchpad

<!-- Grounding: installed board/service evidence in docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/ and overall physical operator acceptance in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. Additional capture is waived. Individual unreported gesture cases are not new physical proof. -->

While an HDMI connector is the active display output, the GT9895 touchscreen's raw
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
The later accepted automatic cable cycle, matching unchanged boot identity
and normal installation are recorded in
`docs/evidence/hdmi-hotplug/live-switch/fast-runtime-qualification.json`,
`docs/evidence/hdmi-hotplug/live-switch/normal-hotplug-install-serial.json` and
`docs/evidence/hdmi-hotplug/live-switch/normal-hotplug-runtime-state.json`.
It does not manufacture individual per-gesture observations.*

#### Scenario: HDMI is the active output and a finger moves across the glass

- **WHEN** an HDMI connector is `connected` per `/sys/class/drm/*/status`
  and a finger drags across the touchscreen
- **THEN** the Wayland session under HDMI shows the pointer move, with no
  visible input reaching the panel-mode absolute touch path

#### Scenario: The panel becomes the active output again

- **WHEN** the HDMI cable is unplugged from the combined mainline runtime
  and the panel becomes the active output, or the panel-only recovery tree boots
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
