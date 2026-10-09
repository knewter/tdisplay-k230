## Why

The board has a real HDMI path — a Lontium LT9611 DSI-to-HDMI bridge on
`&i2c3` — but it does nothing today. LILYGO documents it as "diagnostic,"
our kernel builds the bridge driver but never references it from any device
tree we ship, and nobody using this handheld has ever seen an image on an
external monitor. The person using this board wants HDMI to be usable: plug
a cable in, the display moves to the monitor; unplug it, the display comes
back. They are explicit that a full automatic swap, not merely a manual
toggle, is the goal.

`docs/research/hdmi-hotplug.md` (this change) establishes, from the
schematic and from vendor and our own kernel source, that there is no mux
chip to switch — the DSI lanes are wired in bare parallel to both the panel
and the bridge, and the panel/bridge share their reset and interrupt GPIOs
as literal single nets. Every working HDMI path anyone has ever
demonstrated on this hardware (LILYGO's own shipped launcher toggle, and
the vendor reference tree it falls back to) selects the display by which
device tree boots, and switches by rebooting. Our own kernel's bridge-attach
code path is additionally missing the connector it would need to expose
`HDMI-A-1` at all. A no-reboot hot-plug swap is therefore new, unproven
kernel and shell work, not a device-tree edit — this proposal says so
before naming any chip or register, and stages the work so a working,
reboot-based switch ships first instead of being held behind the harder,
uncertain no-reboot goal.

## What Changes

- Add a `display/hdmi` capability: the LT9611 bridge, driven by our own
  board's device tree (not a copy of the unrelated Canaan reference tree),
  producing a real `HDMI-A-1` DRM connector under our kernel. This requires
  a small `canaan_dsi.c` patch (a missing `drm_bridge_connector_init()`
  call) that is a prerequisite for HDMI working at all, independent of how
  it is switched.
- Add a manual, reboot-based switch between the panel DTB and an HDMI DTB,
  self-reverting on the next boot regardless of cause (mirroring LILYGO's
  own shipped one-shot mechanism), plus a Settings row that triggers it.
  This is the change's proven, shippable core.
- Attempt, as an explicitly separate and higher-risk stage, no-reboot
  hot-plug automation: detecting a live HDMI connection while the panel
  is active, switching DRM output and touch/LT9611 GPIO ownership without
  a reboot, and switching back on disconnect. `docs/research/hdmi-hotplug.md`
  §5 names the specific hardware and kernel-architecture blockers this
  stage must clear; it may turn out to be infeasible without further kernel
  work not scoped here, and that outcome must be recorded rather than
  quietly dropped.
- Audit and begin making `nix/shell.nix` and the `rust-shell-client`/
  `card-shell` runtime landscape-aware: 476 call sites assume a fixed
  568×1232 portrait panel today (`docs/research/hdmi-hotplug.md` §5), and
  none of the HDMI work above is visually usable until at least the Sway
  output stanza and the core design-space transform stop being hardcoded
  to that one geometry.
- Every board-touching task is staged separately and marked board-gated,
  per `.skills/k230-spec-change/SKILL.md`'s QEMU-vs-hardware distinction:
  QEMU's `k230` machine models neither the panel, the touch controller, nor
  the LT9611, so none of this capability can be proven under QEMU.

**Non-goals:** LILYGO's 800x480@60 reference-tree HDMI mode is not adopted
as-is; this board gets its own LT9611 DT node reusing our own board's I2C/
GPIO facts, aimed at 720p60 as the initial target mode (the DSI clock/PHY
math in `docs/research/hdmi-hotplug.md` §4 shows both 720p60 and 1080p60
land exactly on this DSI host's clock-generation grid, so 1080p60 is not
ruled out, but 720p60 is the smaller first target). HDMI audio, CEC, and
the camera/ISP work referenced elsewhere in
`docs/research/board-capability-inventory.md` are untouched. A full
landscape redesign of every shell screen is not delivered by this change;
only the minimum needed to show something coherent on an external monitor
is in scope, with the rest tracked as follow-on work if the no-reboot stage
does not land.

## Capabilities

### New Capabilities

- `display/hdmi`: the LT9611 bridge, its device-tree wiring, the
  reboot-based switch, and (best-effort, separately gated) no-reboot
  hot-plug automation.

### Modified Capabilities

- `display/touch`: records the shared-GPIO23/24 hardware constraint with
  the LT9611 (schematic-confirmed net ties, disagreeing reset polarity and
  interrupt trigger-type conventions between the vendor LT9611 node and our
  touch node) and what it means for touch during HDMI mode.

## Impact

- New kernel patch to `canaan_dsi.c` (bridge-connector creation), new board
  DT fragment for the LT9611, new `nix/device-tree.nix` alternate output,
  new `nix/sd-image.nix` boot-file wiring for a second DTB, new Settings UI
  row, and (for the no-reboot stage only, gated separately) new kernel
  and/or shell runtime logic not yet designed.
- Read-only board time for the first probe task; write/reboot board time
  for the manual-switch and hotplug-automation stages, all under the
  single shared board/serial-port reservation rule in `AGENTS.md`.
- No change to stage 1 binaries, U-Boot SPL, or any file the existing boot
  path depends on other than which named `.dtb` the existing DTB-selector
  text files point at (`nix/sd-image.nix:142-156`). The default image still
  selects the panel. Early Linux restores that selector after the HDMI boot;
  failure before the restore unit requires the protected serial baseline,
  rather than an unproved power-cycle recovery guarantee. See `design.md`'s
  mainline implementation decision.
