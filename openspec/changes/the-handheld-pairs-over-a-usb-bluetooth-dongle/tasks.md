## 1. Physical acceptance (carried from `the-handheld-talks-bluetooth` task 4.1)

- [ ] 1.1 Under the reserved board lock, install the built kernel to `/boot`
      and reboot (a Kconfig-only kernel change does not take effect from a
      plain system activation). Confirm the new kernel is running before
      judging anything below:
      `flock -w 120 /tmp/k230-board.lock python3 tools/console.py /dev/ttyACM0 --wait=3 "uname -a"`.
- [ ] 1.2 Plug in a USB Bluetooth dongle (LILYGO's bundled kit: CSR8510-clone,
      `0a12:0001`; any HCI-compliant dongle proves the same requirement).
      Run, over the reserved serial console:
      `python3 tools/console.py /dev/ttyACM0 --wait=2 "lsusb"`,
      `python3 tools/console.py /dev/ttyACM0 --wait=3 "bluetoothctl show"`,
      `python3 tools/console.py /dev/ttyACM0 --wait=12 "bluetoothctl scan on"`,
      `python3 tools/console.py /dev/ttyACM0 --wait=3 "btmgmt info"`.
      Follow `docs/evidence/backlight-bluetooth-rtc-board-test-plan.md`
      section 3 for expected output and failure signatures, including the
      LILYGO-quirk failure mode (dongle enumerates but never reaches
      `powered`/`running`).
- [ ] 1.3 Commit sanitized console output (no MAC addresses or SSIDs of
      nearby devices) under `docs/evidence/bluetooth/`, naming which of the
      documented outcomes was observed. If the LILYGO quirk is hit, record
      it and treat porting `0056`/`0057-bluetooth-btusb-*.patch` as a
      further follow-up rather than blocking this task's own recording of
      what was actually observed.

## 2. Close deliberately

- [ ] 2.1 Update `radio/bluetooth`'s "The kernel and BlueZ can drive a USB
      Bluetooth controller" requirement: resolve its `<!-- UNVERIFIED -->`
      marker against the board observation from task group 1, or restate it
      to match what was actually observed if a quirk patch was needed.
- [ ] 2.2 Run `openspec validate the-handheld-pairs-over-a-usb-bluetooth-dongle --strict`
      and `python3 scripts/render_work_board.py > /dev/null`, then archive
      and sync the `radio/bluetooth` delta, commit and push.

Proof: the committed console transcript under `docs/evidence/bluetooth/` is
the only evidence this change can produce; there is no host or QEMU
substitute (QEMU's `k230` machine models no USB host controller at all).
