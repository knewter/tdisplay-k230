## Why

`the-handheld-talks-bluetooth` enabled the kernel Bluetooth stack
(`CONFIG_BT`, `CONFIG_BT_HCIBTUSB`, `CONFIG_BT_HCIBTUSB_RTL`) and BlueZ
(`hardware.bluetooth.enable`), with every task proven except one: task 4.1,
plugging in a real USB Bluetooth dongle and confirming `lsusb`,
`bluetoothctl show`, `bluetoothctl scan on` and `btmgmt info` all report a
live controller. That task cannot be performed because this project does
not currently own a USB Bluetooth dongle. `docs/research/bluetooth-onboard.md`
independently confirms this board has no on-board Bluetooth radio of any
kind — the RTL8188F Wi-Fi chip on this board is a Wi-Fi-only part, not the
combo `RTL8723D`, and the optional nRF52840 accessory base offers BLE only
through a proprietary bridge, not a Linux HCI controller — so a USB dongle
is the *only* path to Bluetooth on this hardware, not one option among
several.

This is a scope split, not new work: it exists so `the-handheld-talks-bluetooth`
can close on its own finished software scope (kernel config + BlueZ, both
already build-proven) without silently dropping the one requirement that
needs hardware this project does not yet have. Nothing here is authorized
to run yet — this proposal stages the successor and its preserved task so a
future coordinator with a dongle in hand can execute it and archive this
change, and so the parent can be archived once this split is authorized.

## What Changes

- Carry forward, verbatim, `the-handheld-talks-bluetooth` task 4.1: install
  the built kernel, reboot, plug in a USB Bluetooth dongle, and confirm
  `lsusb`, `bluetoothctl show`, `bluetoothctl scan on` (10 s) and
  `btmgmt info` all report a live, powered controller. Commit sanitized
  console output (no MAC addresses or SSIDs of nearby devices) under
  `docs/evidence/bluetooth/`.
- Carry forward the board test plan already written for this in
  `docs/evidence/backlight-bluetooth-rtc-board-test-plan.md` section 3,
  including its documented LILYGO-quirk failure mode (dongle enumerates on
  USB but `btmgmt info` never reaches `powered`/`running`) and its remedy
  (LILYGO's `0056`/`0057-bluetooth-btusb-*.patch` quirks, not ported
  speculatively per `the-handheld-talks-bluetooth`'s design.md decision 1).
- Resolve the `<!-- UNVERIFIED -->` marker on `radio/bluetooth`'s "The
  kernel and BlueZ can drive a USB Bluetooth controller" requirement once
  the board test passes, or restate the requirement against what was
  actually observed if the quirk patches turn out to be needed.

**Non-goals:** re-doing any of the kernel/NixOS/BlueZ work `the-handheld-talks-bluetooth`
already did and proved by build — this change touches no Kconfig, no Nix
module, and no device tree. A Settings status row remains out of scope here
too, per that change's own "Bluetooth status is not yet in the shell UI"
requirement, unchanged.

## Capabilities

### Modified Capabilities

- `radio/bluetooth`: resolves the `<!-- UNVERIFIED -->` marker on "The
  kernel and BlueZ can drive a USB Bluetooth controller" with an actual
  board observation against a physical dongle, once one is available.

## Impact

No source changes. This is a board-verification-only change: it needs a
USB Bluetooth dongle (LILYGO's bundled kit ships a CSR8510-clone,
`0a12:0001`, but any HCI-compliant USB dongle proves the same requirement)
and the reserved board/serial port. `the-handheld-talks-bluetooth` remains
open, with task 4.1 pointing here, until a coordinator authorizes this
split; only then does the parent archive its finished kernel/BlueZ scope
and this change carries the remaining hardware gate forward.
