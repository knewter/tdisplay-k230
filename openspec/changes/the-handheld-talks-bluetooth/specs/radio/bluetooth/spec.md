## ADDED Requirements

### Requirement: The kernel and BlueZ can drive a USB Bluetooth controller

<!-- UNVERIFIED: no boot log or console transcript yet confirms a
controller node appears or that BlueZ starts on this board. -->

The system SHALL build the Bluetooth core (`CONFIG_BT`) and the USB HCI
driver (`CONFIG_BT_HCIBTUSB`) into the kernel, with Realtek protocol
support (`CONFIG_BT_HCIBTUSB_RTL`) for the CSR8510-clone dongle
(`0a12:0001`) this project's accessory kit bundles, and SHALL run BlueZ via
`hardware.bluetooth.enable`. No device-tree change is required.

*Grounding: `net/bluetooth/Kconfig` and `drivers/bluetooth/Kconfig` in the
pinned Xuantie kernel tree already carry `BT`, `BT_HCIBTUSB` and
`BT_HCIBTUSB_RTL` with no K230-specific blocker; `nix/kernel.nix`'s
`structuredExtraConfig` sets no `CONFIG_BT*` symbol today. Both DWC2 USB
controllers are already `status = "okay"` in `nix/dts/k230-tdisplay.dts`;
USB Bluetooth binds on the USB bus, not a device-tree node.*

#### Scenario: A person plugs in a USB Bluetooth dongle

- **WHEN** a person plugs a USB Bluetooth dongle into the board's USB host
  port
- **THEN** `lsusb` shows the device and `bluetoothctl show` reports a
  controller

#### Scenario: A person scans for nearby devices

- **WHEN** a person runs `bluetoothctl scan on` with a controller present
- **THEN** nearby discoverable Bluetooth devices appear within the scan
  window

#### Scenario: `btmgmt info` is checked

- **WHEN** a person runs `btmgmt info` with the dongle attached
- **THEN** it reports the controller as powered and running, not merely
  enumerated on the USB bus

### Requirement: Bluetooth status is not yet in the shell UI

Bluetooth SHALL work from the console (`bluetoothctl`, `btmgmt`) in this
change. A Settings status row is explicit, named follow-up work, not a
silent gap — this requirement exists so that gap is tracked rather than
assumed away.

*Grounding: design.md decision 3 — adding a fifth `SettingsSnapshot` field
touches `tools/device_settings.py`, `service_ui.rs`'s touch-routing tests
and `render.rs`'s row layout at nine existing call sites for one control
alone; not "cheap" by this change's own bar.*

#### Scenario: Someone looks for Bluetooth in Settings today

- **WHEN** a person opens the handheld's Settings screen after this change
- **THEN** there is no Bluetooth row yet, and this is documented follow-up
  work rather than an unnoticed omission
