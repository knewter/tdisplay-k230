## Why

The board's LT9611 HDMI path now works on the mainline kernel. The operator
accepted the HDMI image, portrait rotation, and touchscreen-as-trackpad on
2026-10-09; matching evidence is in `docs/evidence/hdmi-mainline/`. The
remaining immediate goal is automatic cable switching: plug HDMI in to
move the shell to the monitor, then unplug it to return to the panel and
direct touch without rebooting.

The DSI lanes are wired in parallel to panel and bridge, and touch shares
the bridge's reset and interrupt nets. The accepted HDMI-only boot is a
qualification/recovery path. The current monitor-only driver has observed
real cable changes with the panel enabled on an unchanged boot ID, while
its explicit panel-touch report remains pending. The runtime re-plan keeps
both DSI consumers registered, uses exclusive DRM encoders with polling,
and keeps touch as the sole shared-pin owner. Visible handoff remains
unproved until the combined board trial.

The operator directed this automatic continuation and parked the separate
Settings reboot prototype. Its historical host proof remains at commit
`58498320`; the manual and landscape requirements/tasks remain open.
They are not prerequisites for the requested automatic switching work.

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
  This optional prototype is parked; its distinct physical sequence remains unproved.
- Attempt, as an explicitly separate and higher-risk stage, no-reboot
  hot-plug automation: detecting a live HDMI connection while the panel
  is active, selecting exclusive DRM outputs and switching direct-touch/trackpad
  mode without a reboot, and switching back on disconnect. Touch retains
  GPIO23/24 ownership throughout. `docs/research/hdmi-hotplug.md`
  §5 names the specific hardware and kernel-architecture blockers this
  stage must clear; it may turn out to be infeasible without further kernel
  work not scoped here, and that outcome must be recorded rather than
  quietly dropped.
- Audit and begin making `nix/shell.nix` and the `rust-shell-client`/
  `card-shell` runtime landscape-aware: 476 call sites assume a fixed
  568×1232 portrait panel today (`docs/research/hdmi-hotplug.md` §5), and
  The accepted HDMI trial already uses its EDID-preferred mode and portrait
  rotation; the separate landscape interaction proof remains open.
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
  and shell/input runtime logic explicitly re-planned in `design.md`.
- Read-only board time for the first probe task; write/reboot board time
  for the manual-switch and hotplug-automation stages, all under the
  single shared board/serial-port reservation rule in `AGENTS.md`.
- No change to stage 1 binaries, U-Boot SPL, or any file the existing boot
  path depends on other than which named `.dtb` the existing DTB-selector
  text files point at (`nix/sd-image.nix:142-156`). The default image still
  selects the protected panel until the combined runtime trial passes. The
  parked manual plan restores its selector in early Linux after an HDMI boot;
  that separate sequence remains unproved. Failure before its restore unit
  requires the protected serial baseline,
  rather than an unproved power-cycle recovery guarantee. See `design.md`'s
  mainline implementation decision.

## Automatic continuation and image gate (2026-10-09)

Preserve the accepted monitor's 1280×800 preferred mode, transform 90, and
HDMI trackpad behavior. The combined candidate first builds as
`kernelMainlineDrmShellHotplugBootFiles` and receives a volatile board trial
with protected panel recovery retained. After matching physical handoff and
navigation proof, promote the same kernel/tree/system to normal boot and
`sdImage`, as requested by the operator. A successful host image build is
not an installed-system or visible-transition result. No monitor photograph
is required; actual operator observations and matching serial/sysfs evidence
remain required. No incomplete requirement is archived or silently dropped.
