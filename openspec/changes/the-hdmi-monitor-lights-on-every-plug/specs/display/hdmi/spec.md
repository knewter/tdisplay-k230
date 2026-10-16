## MODIFIED Requirements

### Requirement: The cable selects the active display without a reboot

With the combined mainline device tree, the system SHALL switch the active
output to HDMI when a monitor is plugged in and return to the panel on unplug,
without a reboot, on every plug however long the system has been running. The monitor SHALL be driven at 1280x800 when it offers that mode. It SHALL preserve the accepted HDMI portrait rotation and
trackpad input, and restore direct touch when the panel becomes active again.
The separately qualified HDMI-only and panel-only boot trees remain available
for recovery; their presence does not require a manual Settings reboot control.

*Grounding: `docs/research/hdmi-hotplug.md` §5 names three concrete,
schematic- and source-grounded blockers this goal must clear: the physical
HDMI hot-plug-sense pin is wired only to the LT9611 itself
(`HDMI_HPD`→`HPD_GPIO2`, schematic sheet "HDMI+ETH"), not to any
independent K230 GPIO, so detecting a plug event at all requires the LT9611
to already be a live, probed I2C device while the panel device tree is the
one running; the shared GPIO24 reset net (see "DSI lanes are shared wiring"
above) forbids independently resetting either chip after their initial
power-on reset; and `canaan_dsi.c` has no live panel/bridge re-attach path
in the surveyed baseline (see the HDMI-only qualification requirement
above). The runtime re-plan keeps both consumers registered and uses two
exclusive encoders with 250 ms HPD work and generic polling as fallback,
rather than adding live re-attachment.
Touch retains both shared pins; their unknown electrical drive type is not
used as an assumption for shared-IRQ operation.*

*Grounding: observed 2026-10-09: the first combined trial established both visible
switching directions with trackpad on HDMI and direct touch on return. The
matching faster kernel trial was accepted by the operator: HDMI replug took
"couple of seconds", panel return was "almost instant". A later "it works
great land it" confirms the requested cable/navigation checks; the qualification
records that question context rather than inventing per-gesture traces.
Read-only state before and after acceptance retains boot ID
`cff529ad-6aa6-4a31-b9af-337bbc783521`, enabled HDMI at the accepted portrait
transform and virtual touchpad. See
`docs/evidence/hdmi-hotplug/live-switch/fast-runtime-operator-report.json`,
`fast-runtime-qualification.json` and `fast-runtime-qualified-state.json`.
No-reboot switching works on this tested mainline arrangement. The matching
normal bundle is installed and ordinary autoboot is observed separately in
`docs/evidence/hdmi-hotplug/live-switch/normal-hotplug-install-serial.json`
and `normal-hotplug-runtime-state.json`. The separate
sampled HPD-to-connector ≤1s and HPD-to-enabled ≤3s targets remain unmeasured:
the bounded watcher captured no transitions. The operator explicitly deferred
precise latency measurement on 2026-10-09; no sampled result is claimed. See
`docs/evidence/hdmi-hotplug/live-switch/closeout-2026-10-09.md`.
Operator-visible approximate
timing is evidence for the 30s scenario ceiling, not those precise targets.*

#### Scenario: A cable is plugged in while the panel is active

- **WHEN** an HDMI cable is plugged into a monitor while the board is
  running the combined mainline device tree with the panel and direct touch active
- **THEN** the visible output moves to the monitor within 30 seconds,
  without a reboot, preserving the accepted HDMI rotation and using the
  handheld touchscreen as the accepted HDMI trackpad

#### Scenario: The cable is unplugged

- **WHEN** the HDMI cable is then unplugged
- **THEN** the visible output returns to the panel within 30 seconds and touch responds to
  direct input again, without a reboot

#### Scenario: A cable is plugged in after hours of uptime

- **WHEN** an HDMI cable is plugged in after the system has run for hours,
  with repeated shell restarts and theme changes
- **THEN** the monitor shows the shell at 1280x800 within 30 seconds, with no
  framebuffer allocation failure in the compositor log
<!-- UNVERIFIED: board proof is task 2.2 -->
