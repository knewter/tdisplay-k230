## Purpose

Describe the board-specific HDMI path, shared hardware constraints, qualification
outputs and accepted automatic handoff between the monitor and handheld panel.

## ADDED Requirements

### Requirement: The LT9611 is present and addressable

The board's Lontium LT9611 DSI-to-HDMI bridge SHALL be confirmed present and
addressable on `&i2c3` at `0x3b`, alongside the existing GT9895 touch
controller at `0x5d` on the same bus, through a read-only probe that drives
no GPIO differently from today's normal panel boot.

*Grounding: schematic `T-Display K230_V1.0_NEW.pdf` sheet "HDMI+ETH" places
the LT9611 (`U18`) on the net pair `HDMI_CSCL`/`HDMI_CSDA`, which sheet
"Video"'s net-label table ties to `I2C3_SCL`/`I2C3_SDA` — the same bus as
touch (`docs/dts-evidence.md`, `docs/research/board-capability-inventory.md`).
No address collision (`0x3b` vs `0x5d`).*

*Grounding: observed 2026-09-29 (docs/evidence/hdmi-hotplug/probe/lt9611-probe-2026-09-29.md):
`&i2c3` is Linux adapter `i2c-1`. `0x3b` acknowledges and returns chip ID
`0x17 0x02` (rev `0xe2`), and `0x5d` is bound to `gt9895`. The ID read used the
mainline driver's page-select writes. Touch input was not re-exercised in that
session.*
<!-- UNVERIFIED: touch continuing to report input after the probe was not exercised. -->

#### Scenario: The bus is probed with touch running

- **WHEN** `i2cdetect -y` is run against the `&i2c3` adapter while the
  board is booted normally, with touch active
- **THEN** both `0x3b` and `0x5d` appear as answering addresses, and touch
  continues to report input events normally afterward

### Requirement: DSI lanes are shared wiring, not a switch

This project SHALL treat the DSI data lanes, clock, and the touch/LT9611
reset and interrupt GPIOs as literal shared electrical nets, not as
independently controllable per-consumer signals, in every design and DT
change this capability makes.

*Grounding: schematic sheet "K230" wires the SoC's `MIPI_TX0_CLK_P/N` and
`MIPI_TX0_D0_P/N`..`MIPI_TX1_D3_P/N` pins to net labels `DSI_CLK_P/N` and
`DSI_D0_P/N`..`DSI_D3_P/N`; sheet "HDMI+ETH" wires the LT9611's `MLRXB_*`
MIPI-RX-port-B pins (49–58) to the identical net labels. Sheet "Video"'s
net-label table ties `HDMI_RSTN`→`TP_RST` (LT9611 reset = touch reset,
GPIO24) and `HDMI_INT`→`TP_INT` (LT9611 interrupt = touch interrupt,
GPIO23) as single unbroken wires, not a jumper between two nets. The vendor
LT9611 DT node (`k230-canmv-v3.dts:64,66`, in the pinned kernel tree)
requests `GPIO_ACTIVE_HIGH` reset and `IRQ_TYPE_EDGE_FALLING`; our touch
node (`nix/dts/k230-tdisplay.dts:200,224`) requests `GPIO_ACTIVE_LOW` reset
and `IRQ_TYPE_LEVEL_LOW` on the same physical pins. No mux, switch IC, or
isolation component appears anywhere between the SoC, the panel connector,
and the LT9611 on the schematic. Full detail in
`docs/research/hdmi-hotplug.md` §1.*

#### Scenario: A design or device tree change is reviewed

- **WHEN** a change under this capability proposes driving GPIO23 or
  GPIO24, or wiring the LT9611 into `&dsi`'s graph, differently from touch
  or the panel's existing behavior
- **THEN** the review checks it against the shared-net facts above, not
  against an assumption that the two consumers can be independently reset
  or interrupted

### Requirement: HDMI-only qualification remains a boot-time device-tree choice

The separate HDMI-only qualification and recovery path SHALL expose an
`HDMI-A-1` DRM connector through this board's own LT9611 device-tree wiring,
loaded at boot. This fallback remains available alongside the combined
mainline runtime arrangement described in the no-reboot requirement.
The panel-only qualification tree retains its panel-only graph.

*Historical baseline grounding: `drivers/gpu/drm/canaan/canaan_dsi.c`'s `canaan_dsi_bind()`
calls `drm_of_find_panel_or_bridge(dsi->dev->of_node, 1, -1, &dsi->panel,
&dsi->bridge)` exactly once, at component-bind/boot time (line 695 in the
pinned Xuantie kernel tree); no code path re-invokes this lookup, and
`canaan_dsi_detach()` (line 560) only clears state when the attached child
device itself unregisters. Every vendor source found selects HDMI the same
way: LILYGO's own abandoned board-specific merge attempt
(`k230_bsp` patch `0055-riscv-dts-add-rm69a10-hdmi-output-dtb.patch`) and
their shipped, working fallback (patch
`0062-riscv-dts-rm69a10-hdmi-use-sdk-v3-baseline.patch`, which `#if 0`s the
merge attempt and `#include`s the unrelated `k230-canmv-v3.dts` instead)
both produce a *separate* DTB, never a merged one. Their shipped launcher
UI, `k230_launcher/k230_phone_ui/src/ui_hdmi_test.c`, switches by copying a
DTB file and calling `reboot()` (`ui_hdmi_test.c:312-343`). Full detail in
`docs/research/hdmi-hotplug.md` §3–§4.*

The kernel's DSI-bridge-attach code path SHALL create a working DRM
connector for the bridge, as established by the group-2 host build and the accepted group-7 mainline trial.

*Grounding: `canaan_dsi_bind()`'s bridge branch
(`canaan_dsi.c:713-714`) calls `drm_bridge_attach(..., NULL,
DRM_BRIDGE_ATTACH_NO_CONNECTOR)` and nothing in `canaan_dsi.c` or
`canaan_drv.c` calls `drm_bridge_connector_init()` (checked by direct grep
of both files in the pinned kernel tree) — so an LT9611 node in any DTB we
build produces an attached bridge with no connector until this is patched.*

<!-- UNVERIFIED: the kernel patch (nix/patches/canaan-dsi-bridge-connector.patch)
and board-specific DTB (nix/dts/k230-tdisplay-hdmi.dts) described here are
now written and host-build-verified (tasks.md group 2: `nix build .#kernel`,
`nix build .#deviceTreeHdmi`, and `nix build
.#nixosConfigurations.k230.config.system.build.toplevel` with the default
panel DTB unchanged all succeeded 2026-09-28) but have not been booted on
the board (group 3). Host build confirms the patch applies and compiles and
the DTB compiles with exactly one `&dsi` port@1 endpoint; it does not confirm
the LT9611 driver actually probes or that a connector actually appears live. -->

*Grounding: observed 2026-10-09 on the shipping mainline path: the group-7 kernel and
board-specific mainline HDMI tree passed a matching volatile boot, automatic
connected status and 256-byte EDID, native shell/cursor captures, and the
operator's acceptance. See `docs/evidence/hdmi-mainline/README.md`. The
vendor kernel/tree pair above remains host-only; the Settings switch has
its separate group-3 gate below.*

#### Scenario: The HDMI DTB boots with a monitor attached

- **WHEN** the board boots the HDMI device tree with an HDMI monitor
  plugged in
- **THEN** `/sys/class/drm/card*-HDMI-A-1/status` reports `connected` and
  the monitor shows a real image, not only that the sysfs node exists

#### Scenario: The panel DTB boots normally

- **WHEN** the board boots the separate panel-only qualification device tree
- **THEN** `/sys/class/drm/card*-DSI-1/status` reports `connected`, touch
  reports input events, and no LT9611-related kernel log line appears,
  since that DTB carries no LT9611 node

### Requirement: The switch is manual, reboot-based, and self-reverting

A person SHALL be able to trigger a switch to HDMI from Settings, which
reboots the board into the HDMI device tree; the board SHALL automatically
revert to the panel device tree on the *next* boot after that, regardless
of why that next boot happened, so a crash or an unrelated power cycle
cannot leave the board silently stuck showing nothing on the panel.

*Grounding: LILYGO's `ui_hdmi_test.c` implements exactly this pattern —
`hdmi_boot_switch_thread()` (lines 312-343) writes a one-shot marker file
naming the panel DTB before copying the HDMI DTB over the active boot file
and rebooting; `ui_hdmi_test_restore_one_shot_boot()` (lines 279-300) runs
early on every subsequent boot, and if the marker exists, restores the
panel DTB and deletes the marker before continuing. Our own
`nix/sd-image.nix:142-156` documents, from hardware observation, that
U-Boot's `bootcmd` already runs a `k230_set_dtb` command reading a named
selector text file (`force_dtb`, falling back to `hdmi_dtb`/`lcd_dtb`) —
the same class of mechanism, already present and boot-tested on this
board's stage 1, that this requirement's implementation reuses rather than
inventing a new one.*

<!-- UNVERIFIED: not yet implemented (tasks.md group 3) or observed on the
board. -->

#### Scenario: A person switches to HDMI and back

- **WHEN** a person taps the HDMI switch in Settings, confirms it, and the
  board reboots
- **THEN** the board comes up on the HDMI device tree, and the next reboot
  after that — triggered any way — comes up on the panel device tree again
  with touch working, without the person having to do anything else to
  restore it

### Requirement: No-reboot hot-plug switching is a separately graded goal

Automatically switching the active output when an HDMI cable is plugged or
unplugged, without a reboot, SHALL be attempted and its outcome SHALL be
recorded plainly — as working, on-hardware-proven behavior, or as a named
infeasibility with its specific blocking cause — rather than left
ambiguous or asserted without evidence.

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

#### Scenario: The goal proves infeasible

- **WHEN** the blockers named above cannot be cleared within this change's
  board time
- **THEN** this requirement is restated against what was actually found,
  naming the specific blocking cause, rather than left as an unresolved
  `<!-- UNVERIFIED -->` marker with no explanation
