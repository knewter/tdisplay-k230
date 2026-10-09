## Why

Plugging in HDMI now moves the shell to the monitor; unplugging returns it to
the panel with direct touch, without rebooting. The operator accepted the
faster cable cycle, portrait HDMI rotation, trackpad behavior and navigation
on 2026-10-09. The same qualified bundle is the normal installed mainline
system and default built SD image. The proposal records delivered automatic
switching alongside the still-open Settings reboot and landscape scope.

## What Changes

- Add `display/hdmi`: bridge presence, shared-net constraints, separate
  qualification/recovery trees and physically proved automatic cable switching.
- Keep panel and LT9611 registered, with exclusive DRM outputs, 250 ms HPD
  polling and generic polling fallback. Touch owns GPIO23/24 throughout;
  shared interrupt drive type remains unknown and no bridge IRQ is enabled.
- Select the accepted HDMI EDID-preferred 1280×800 mode, transform 90 and
  touchscreen trackpad; restore panel mapping and direct touch on unplug.
- Promote the physically accepted tuple to normal boot and `sdImage`, retaining
  protected stage 1, selectors, rollback roots and qualification outputs.
- The manual Settings reboot prototype remains parked at `58498320` and absent
  from shipping source. Tasks 3.1–3.3 retain its distinct implementation and
  forward/restore physical gates; automatic switching does not prove them.
- Landscape tasks 5.1–5.4 remain open, reusing the responsive-shell proposal's
  geometry implementation without treating portrait acceptance as landscape proof.
- The operator explicitly deferred precise HPD latency measurement. Task 4.3
  records acceptance of visible switching and navigation, not a sampled ≤1s/≤3s
  result. Independent performance proposals retain their own requirements.

**Non-goals:** HDMI audio, CEC, camera/ISP, shared-IRQ experiments, a full
landscape redesign, and precise sampled latency qualification in this closeout.
No monitor photograph is required by the operator; actual observations and
matching serial/sysfs identity remain the physical proof.

## Capabilities

### New Capabilities

- `display/hdmi`: LT9611 qualification/recovery and automatic switching,
  with the unimplemented manual Settings switch explicitly retained for now.

### Modified Capabilities

- `display/touch`: shared GPIO23/24 constraints and sole touch ownership during
  the accepted mainline HDMI arrangement.

## Impact

Kernel DSI/LT9611 drivers, combined and qualification device trees, Nix image
wiring and the existing input relay implement automatic switching. Evidence
lives in `docs/evidence/hdmi-mainline/` and
`docs/evidence/hdmi-hotplug/live-switch/`. Implementation/default promotion is
`6b4fe555645ac553914549fcd926d1f0902b65d1`; normal installed system is
`/nix/store/yl3si5ak6yi709yg1fqsnwgq0zn4xfcs-nixos-system-nixos-26.11.20260919.20b1ddd`.
Normal installation and ordinary autoboot are distinct from the volatile trial;
no whole-image flash is claimed. No board action is required to reconcile these
committed records. Archive remains gated on explicit scope preservation for
manual Settings and landscape, with unresolved markers retained honestly.
