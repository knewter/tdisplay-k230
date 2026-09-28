## MODIFIED Requirements

### Requirement: The kernel and BlueZ can drive a USB Bluetooth controller

The system SHALL build the Bluetooth core (`CONFIG_BT`) and the USB HCI
driver (`CONFIG_BT_HCIBTUSB`) into the kernel, with Realtek protocol
support (`CONFIG_BT_HCIBTUSB_RTL`) for the CSR8510-clone dongle
(`0a12:0001`) this project's accessory kit bundles, and SHALL run BlueZ via
`hardware.bluetooth.enable`. No device-tree change is required.

*Grounding: `net/bluetooth/Kconfig` and `drivers/bluetooth/Kconfig` in the
pinned Xuantie kernel tree already carry `BT`, `BT_HCIBTUSB` and
`BT_HCIBTUSB_RTL` with no K230-specific blocker; `nix/kernel.nix`'s
`structuredExtraConfig` now sets these symbols, proven by
`nix build .#kernel`. Both DWC2 USB controllers are already
`status = "okay"` in `nix/dts/k230-tdisplay.dts`; USB Bluetooth binds on
the USB bus, not a device-tree node.*

<!-- UNVERIFIED: carried forward from the-handheld-talks-bluetooth. This
board has no on-board Bluetooth radio (docs/research/bluetooth-onboard.md);
a USB dongle is the only path, and this project does not yet own one, so no
boot log or console transcript has confirmed a controller node appears or
that BlueZ starts on this board. -->

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
