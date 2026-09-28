## Context

`the-handheld-talks-bluetooth` finished and build-proved everything except
one hardware-only gate: a real USB Bluetooth dongle plugged into the board.
This project does not own one, and `docs/research/bluetooth-onboard.md`
already established this board has no on-board Bluetooth radio at all (the
Wi-Fi part is the Wi-Fi-only `RTL8188F`, not the combo `RTL8723D`, and the
nRF52840 accessory base's BLE is a proprietary bridge, not a Linux HCI
controller). A dongle is therefore the only way this capability can ever be
observed on this hardware, not a nice-to-have verification path among
several. See `the-handheld-talks-bluetooth/design.md` for the kernel/BlueZ
decisions this change does not revisit.

## Goals / Non-Goals

**Goals:** get a real, HCI-compliant USB Bluetooth dongle onto the board and
resolve the `<!-- UNVERIFIED -->` marker on `radio/bluetooth`'s controller
requirement with an actual `lsusb`/`bluetoothctl`/`btmgmt` observation.

**Non-Goals:** any kernel, NixOS or device-tree change (none is needed; the
parent already did this work and proved it by build); a Settings UI status
row (explicitly out of scope in the parent, unchanged here); porting
LILYGO's `0056`/`0057` `btusb` quirk patches speculatively -- only if the
board test actually exhibits the quirk.

## Decisions

1. **This change makes no source change.** It exists purely to carry a
   hardware-verification task and the requirement it grounds forward,
   separately from the parent's already-finished, already-build-proven
   software scope, so the parent is not held open indefinitely by hardware
   this project does not have on hand. Rejected: leaving the task inside
   the parent forever -- that blocks archiving finished, reviewed work on
   an indefinite hardware acquisition.
2. **No new evidence format.** Reuses the board test plan already written
   in `docs/evidence/backlight-bluetooth-rtc-board-test-plan.md` section 3,
   including its documented LILYGO-quirk failure signature, rather than
   inventing a new procedure.

## Risks / Trade-offs

- [This change sits open indefinitely until a dongle is acquired] →
  acceptable: it carries only a verification task, not source work, so its
  being open blocks nothing else. The parent's finished scope is what this
  split protects.

## Migration Plan

Not applicable -- no source or schema changes.

## Open Questions

- Whether the bundled CSR8510-clone dongle (`0a12:0001`) hits the
  LILYGO-quirk failure mode on this specific board is unknown until task 1
  runs; if it does, porting the two named quirk patches is a further
  follow-up, not part of this change's own task list.
