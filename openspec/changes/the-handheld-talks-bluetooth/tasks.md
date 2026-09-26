## 1. Kernel: enable the Bluetooth stack

- [x] 1.1 Add `BT = module;`, `BT_HCIBTUSB = module;`,
      `BT_HCIBTUSB_RTL = yes;` to `nix/kernel.nix`'s
      `structuredExtraConfig`, in a clearly delimited, separately commented
      block (no shared lines with `feat/speaker`'s audio Kconfig edits, so
      the two merge cleanly). Proven:
      `nix build .#kernel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/78cdif47ayqwv67m7crjpawfzy2mx3af-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`
      (build proof only) — one kernel derivation shared with
      `the-panel-brightness-is-adjustable`'s driver change.

## 2. NixOS: BlueZ

- [x] 2.1 Add `hardware.bluetooth.enable = true;` in `nix/hardware.nix`
      (the real-hardware-only base; `nix/k230.nix` is the shared
      hardware+QEMU base). Proven:
      `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`
      exited 0, producing
      `/nix/store/152qrxpkagai2fahgyhkxq7sp8sk98n4-nixos-system-nixos-26.11.20260919.20b1ddd`,
      which schedules `unit-bluetooth.service`, `unit-obex.service` and a
      `dbus-broker` unit (build proof only).

## 3. Board test plan

- [x] 3.1 Add `bluetoothctl show`, `bluetoothctl scan on` (10 s),
      `btmgmt info` and `lsusb` to the combined board test plan
      (`docs/evidence/backlight-bluetooth-rtc-board-test-plan.md`), with
      expected output and failure signatures for: no dongle detected, no
      Bluetooth controller node, and a dongle visible in `lsusb` but never
      reaching `RUNNING`/powered state in `btmgmt info` (the LILYGO-quirk
      failure mode named in design.md).

## 4. Physical acceptance

- [ ] 4.1 Install the built kernel to `/boot` and reboot. Under the
      reserved board lock, plug in the USB Bluetooth dongle, confirm
      `lsusb` shows it, then run `bluetoothctl show`, `bluetoothctl scan
      on` for 10 s, and `btmgmt info`. Commit sanitized console output
      (no MAC addresses/SSIDs of nearby devices) under
      `docs/evidence/bluetooth/` (hardware proof only).
