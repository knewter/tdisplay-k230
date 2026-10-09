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

*Observed 2026-09-29 (docs/evidence/hdmi-hotplug/probe/lt9611-probe-2026-09-29.md):
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

### Requirement: HDMI output is a boot-time device-tree choice

The board SHALL expose an `HDMI-A-1` DRM connector, driven by this board's
own device-tree wiring of the LT9611 (not a copy of an unrelated reference
board's tree), by loading an alternate device tree — not by any runtime
reconfiguration of a single booted kernel.

*Grounding: `drivers/gpu/drm/canaan/canaan_dsi.c`'s `canaan_dsi_bind()`
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
connector for the bridge, which it does not today.

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

*Observed 2026-10-09 on the shipping mainline path: the group-7 kernel and
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

- **WHEN** the board boots the default (panel) device tree
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
today (see "HDMI output is a boot-time device-tree choice" above) — new
kernel logic would be required with no existing pattern in any source
surveyed to base it on.*

<!-- UNVERIFIED: not attempted. This requirement is expected to resolve
either to a working scenario below or to a recorded infeasibility finding
per tasks.md task 4.4; it must not be archived with this marker simply
removed without one of those two outcomes on file. -->

#### Scenario: A cable is plugged in while the panel is active

- **WHEN** an HDMI cable is plugged into a monitor while the board is
  running the panel device tree with touch active
- **THEN** the visible output moves to the monitor within a bounded time,
  without a reboot, and touch stops responding to further input while HDMI
  is active

#### Scenario: The cable is unplugged

- **WHEN** the HDMI cable is then unplugged
- **THEN** the visible output returns to the panel and touch responds to
  input again, without a reboot

#### Scenario: The goal proves infeasible

- **WHEN** the blockers named above cannot be cleared within this change's
  board time
- **THEN** this requirement is restated against what was actually found,
  naming the specific blocking cause, rather than left as an unresolved
  `<!-- UNVERIFIED -->` marker with no explanation
