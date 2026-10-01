## ADDED Requirements

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
