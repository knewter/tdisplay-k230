## Why

Plugging in HDMI moves the shell to the monitor; unplugging returns it to the
panel and direct touch without rebooting. The operator accepted the faster
cable cycle, portrait HDMI rotation, trackpad behavior and navigation on
2026-10-09. The qualified tuple is installed normally and is the default built
SD image. This change closes that delivered automatic behavior.

## What Changes

- Add `display/hdmi`: bridge presence, shared wiring constraints, separate
  qualification/recovery trees and physically proved automatic cable switching.
- Keep both DSI consumers registered, with exclusive outputs and 250 ms HPD
  polling plus generic fallback. Touch retains sole GPIO23/24 ownership.
- Retain the accepted monitor's 1280×800 preferred mode, transform 90 and
  touchscreen trackpad; restore panel mapping and direct touch on unplug.
- Promote the matching qualified tuple to normal boot and default `sdImage`,
  preserving protected stage 1, selectors and rollback roots.
- Drop the obsolete Settings reboot/self-revert requirement and tasks 3.1–3.3
  at the operator's explicit direction. No reboot button is delivered or needed.
- Transfer all landscape requirements/tasks 5.1–5.4 to the separately landed
  `the-hdmi-shell-works-in-landscape` proposal. Its physical gate remains open.
- Record precise HPD timing as explicitly deferred, without claiming ≤1s/≤3s
  sampled targets passed. Independent performance proposals keep their gates.

**Non-goals:** HDMI audio, CEC, camera/ISP, shared IRQ experiments, landscape
layout implementation and precise sampled latency qualification in this closeout.
The operator waived a monitor photograph; actual observations and matching
serial/sysfs identities are committed physical evidence.

## Capabilities

### New Capabilities

- `display/hdmi`: board-specific HDMI qualification/recovery and accepted
  automatic cable switching without rebooting.

### Modified Capabilities

- `display/touch`: shared GPIO23/24 constraint and the existing virtual-trackpad
  requirement updated to reflect physically accepted automatic panel return.

## Impact

Kernel DSI/LT9611 drivers, device trees, Nix image wiring and the existing input
relay implement this behavior. Implementation/default promotion landed at
`6b4fe555645ac553914549fcd926d1f0902b65d1`. Evidence lives in
`docs/evidence/hdmi-mainline/` and `docs/evidence/hdmi-hotplug/live-switch/`.
Normal installed system is
`/nix/store/yl3si5ak6yi709yg1fqsnwgq0zn4xfcs-nixos-system-nixos-26.11.20260919.20b1ddd`.
The volatile trial, normal installation/autoboot and built SD image remain
separate evidence classes; no whole-image flash is claimed. This archive changes
planning/spec/evidence only and requires no new board action.
