## Why

The handheld cannot pair with a Bluetooth accessory today. Not because the
hardware is unreachable — Bluetooth here is a generic USB dongle over
already-working USB host, mainline `drivers/bluetooth/btusb.c` is already
present in our pinned kernel source tree — but because nobody has ever
turned on a single Kconfig symbol.
`docs/research/board-capability-inventory.md` ranks this rank 4 by
value/effort ("Present-but-not-enabled. Effort S ... pure Kconfig + a NixOS
package addition, no DT, no patch, risk low. Genuinely one of the cheapest,
highest-value gaps in this document").

## What Changes

- Enable the kernel Bluetooth stack (`CONFIG_BT`) and the USB HCI driver
  (`CONFIG_BT_HCIBTUSB`), plus the Realtek protocol support LILYGO's own
  BSP enables for the CSR8510-clone dongle their kit ships
  (`0a12:0001`, `CONFIG_BT_HCIBTUSB_RTL`).
- Add BlueZ to the system via `hardware.bluetooth.enable`, the standard
  NixOS module for it.
- Add a minimal, purely diagnostic way to check the stack came up on the
  board: `bluetoothctl show` and `btmgmt info` in the combined board test
  plan, plus `lsusb` to confirm the dongle enumerates and is powered.
- Add a status row to Settings if it is cheap; otherwise document it as
  explicit follow-up rather than silently skipping it.

## Capabilities

### New Capabilities

- `radio/bluetooth`: the taxonomy's `radio/` group already holds `wifi`
  and `lora`; Bluetooth is a third radio and gets its own capability rather
  than overloading `radio/wifi` (a different radio, different bus — a USB
  accessory, not on-board SDIO/SPI silicon — and a different kernel
  subsystem entirely).

### Modified Capabilities

None.

## Impact

The kernel (`nix/kernel.nix` — Kconfig only, kept in its own clearly
delimited hunk since `feat/speaker` is concurrently editing this same file
for audio; no device-tree change at all, matching the inventory's
"no DT, no patch" finding) and NixOS (`hardware.bluetooth.enable`, in
`nix/k230.nix`). No Rust shell changes beyond an optional cheap status row;
if that turns out not to be cheap, this change documents it as explicit
follow-up rather than silently dropping it. The dongle sits on USB host,
whose power switching this project has already validated
(`docs/uboot-usb-host*`, `docs/evidence/usb-host-validation.md`); this
change does not touch USB host configuration itself, only whether the
kernel can drive a Bluetooth device once one is plugged in and powered.
Pairing, scanning and `bluetoothctl`/`btmgmt` output against a real dongle
are hardware-only gates — QEMU's `k230` machine models no USB host
controller at all, so this whole change's functional proof is
hardware-only, same as backlight.
