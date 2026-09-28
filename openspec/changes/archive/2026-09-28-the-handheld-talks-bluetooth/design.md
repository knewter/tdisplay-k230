## Context

See proposal.md. Grounding, read directly from the pinned tree's own
unpacked source
(`/nix/store/bjgv1xn5b66gbz2kxv2aqzr1szp7dk7c-linux-xuantie-k230-src` at
the time of writing):

- `net/bluetooth/Kconfig`'s `menuconfig BT` is `tristate`, depends only on
  `!S390` and `RFKILL || !RFKILL` (always satisfied) — nothing about this
  SoC blocks it.
- `drivers/bluetooth/Kconfig`'s `BT_HCIBTUSB` `depends on USB` (already
  enabled: `CONFIG_USB_DWC2=y`, `CONFIG_USB_DWC2_DUAL_ROLE=y` in our pinned
  `k230_defconfig`) and `select BT_INTEL`. `BT_HCIBTUSB_RTL` is `bool
  "Realtek protocol support" ... default y` once `BT_HCIBTUSB` is on —
  matching the inventory's citation of LILYGO's own
  `CONFIG_BT=m CONFIG_BT_HCIBTUSB=m CONFIG_BT_HCIBTUSB_RTL=y` and their two
  quirk patches (`0056`, `0057-bluetooth-btusb-*.patch`) for the specific
  CSR8510-clone dongle (`0a12:0001`) their kit bundles.
- No device-tree node is needed: USB Bluetooth binds purely on the USB bus
  (vendor/product ID), and both DWC2 USB controllers are already
  `status = "okay"` in `nix/dts/k230-tdisplay.dts`.
- `nix/kernel.nix`'s `structuredExtraConfig` sets no `CONFIG_BT*` symbol at
  all today (checked directly against the current file) — this is the one
  and only kernel gap.

## Goals / Non-Goals

**Goals:** `hci0` (or equivalent) appears once a Bluetooth USB dongle is
plugged into USB host and powered; `bluetoothctl show` and `btmgmt info`
report a controller; BlueZ is present and its service starts; scanning
finds nearby devices.

**Non-Goals:** pairing UI in the shell beyond an optional cheap status row;
audio profiles (A2DP/HSP — out of scope, and would additionally interact
with `feat/speaker`'s in-flight audio routing, which this change does not
touch); BLE peripheral/central application code; the on-board nRF52840
base's own BLE stack (a separate MCU with its own firmware, out of scope
per the inventory's UART-only Linux-side treatment of that accessory).

## Decisions

1. **Kconfig only, no device tree, no kernel patch.** This matches the
   inventory's own effort/risk assessment exactly
   ("Present-but-not-enabled ... Effort S ... no DT, no patch, risk low").
   `CONFIG_BT`, `CONFIG_BT_HCIBTUSB` as modules (`module`, matching this
   kernel's general preference for loadable Bluetooth so it is absent from
   a board with no dongle attached) and `CONFIG_BT_HCIBTUSB_RTL` as `yes`
   (it is a plain bool once `BT_HCIBTUSB` is set, and matches the
   inventory's specific citation for the bundled test dongle). Rejected:
   porting LILYGO's two `btusb` quirk patches (`0056`/`0057`) speculatively
   — those exist to paper over one specific dongle's `HCI_QUIRK_RESET_ON_CLOSE`
   behavior; whether *our* dongle needs them is a board observation this
   change's task group makes, not an assumption to patch in before ever
   testing the base upstream driver.
2. **`hardware.bluetooth.enable = true`, the standard NixOS module**,
   rather than hand-rolling a `bluez` package addition and systemd unit.
   This is the same "add a real, boring, unadapted upstream mechanism"
   choice `radio/wifi` and `system/nixos-config` already make elsewhere
   (`environment.systemPackages` additions require a recorded reason; this
   module *is* the recorded, standard reason for BlueZ specifically).
3. **A Settings status row is deferred, not added.** The existing
   `SettingsSnapshot`/`Control` plumbing
   (`nix/rust-shell-client/src/service_data.rs`) is a fixed struct with
   four named fields (`network`, `brightness`, `keyboard`, `motion`), each
   threaded through `tools/device_settings.py`'s `status()`,
   `service_ui.rs`'s touch-routing tests and `render.rs`'s row layout —
   adding a fifth field touches all three call sites and their existing
   test literals (`grep -n "brightness:" nix/rust-shell-client/src/*.rs`
   shows nine occurrences across three files just for one existing
   control). That is not "cheap" by any reasonable reading, and the
   working agreement is explicit that scope creep here is expensive
   because one change can reach from a device tree to a running app.
   Rejected: adding a bare read-only row anyway — a half-integrated status
   row (no pairing action, no device list) would create exactly the kind
   of "the-panel-brightness-is-adjustable"-style follow-up debt this
   inventory already tracks explicitly, better tracked as its own named
   follow-up than folded silently into a Kconfig change.
4. **The physical proof is `bluetoothctl show`, `bluetoothctl scan on`,
   `btmgmt info` and `lsusb`, run from the console, not a shell UI
   interaction.** This matches the "no DT, no patch" scope: the claim being
   proved is "the kernel and BlueZ can drive a real dongle," not "the shell
   has Bluetooth UI."

## Risks / Trade-offs

- [The bundled dongle needs the same quirks LILYGO patched] → the physical
  test in the combined board test plan is designed to surface exactly this
  (a dongle that enumerates in `lsusb` but never reaches `RUNNING` in
  `btmgmt info` is the failure signature); porting `0056`/`0057` becomes a
  follow-up change if and only if that is observed, not assumed here.
- [USB host power switching does not actually energize the dongle] → the
  inventory names this as the real risk, not the Bluetooth stack itself;
  `lsusb` showing the device at all is the fast, cheap way to separate
  "no power" from "power but no Bluetooth stack," and this project's
  existing USB host validation (`docs/uboot-usb-host*`,
  `docs/evidence/usb-host-validation.md`) already establishes host mode and
  UMS work on this exact port.
- [Deferring the Settings row leaves Bluetooth invisible to a person using
  the handheld normally] → explicitly named as follow-up in this design
  rather than silently dropped, per the working agreement's instruction to
  preserve scope rather than let it evaporate.

## Migration Plan

Enable the Kconfig symbols and `hardware.bluetooth.enable`; cross-build the
kernel and the full system closure. Install the built kernel to `/boot`
and reboot (a kernel config change, not just activation). Physical
acceptance is: plug in the dongle, confirm `lsusb`, run
`bluetoothctl show`/`scan on`/`btmgmt info` from the console. Rollback is
reverting this commit; no device-tree or userspace behavior outside
Bluetooth is touched.
