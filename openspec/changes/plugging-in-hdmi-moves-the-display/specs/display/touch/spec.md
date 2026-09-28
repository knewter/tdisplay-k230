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

No device tree this project ships today wires both a touch node and an
LT9611 node into the same boot — `nix/dts/k230-tdisplay.dts` carries touch
only, matching every vendor source surveyed (`docs/research/hdmi-hotplug.md`
§3), which also never combines the two in one working tree.

#### Scenario: A change proposes adding an LT9611 node to the default tree

- **WHEN** a future change proposes adding the LT9611 to the same device
  tree that already carries the GT9895 touch node
- **THEN** the review checks the proposed GPIO23/24 reset polarity and
  interrupt trigger type against both consumers' existing requirements, not
  only against the LT9611 in isolation, since the pins are shared hardware,
  not independently configurable per node
