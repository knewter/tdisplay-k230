## Context

The board's data connector J3 is the U-Boot UMS connector. The charging
connector J2 carries the CH342 console bridge. Existing UMS evidence identifies
VID `29f1`, PID `0230`, but that is evidence from a running U-Boot gadget and
cannot establish what the BootROM does before stage 1. SW3 is wired to BOOT0.
No BootROM test is currently claimed.

## Goals / Non-Goals

**Goals:**

- Make the two entry conditions reproducible and observable from host USB and
  serial capture.
- Preserve negative results with the same evidentiary weight as success.
- If available, verify the complete vendor-tool write and reboot path without
  corrupting the only known-good image.
- Keep UMS, card-reader, and BootROM recovery claims separate.

**Non-Goals:**

- Changing BootROM straps, U-Boot, kernel, or automatic boot commands.
- Treating a USB device seen after U-Boot starts as BootROM evidence.
- Performing a destructive corruption experiment before a safe known-good
  rollback image and readback plan exist.

## Decisions

1. Use the data connector J3 for host USB and retain J2 for serial capture.
2. Run no-card and SW3 tests as separate power cycles, recording exact card,
   button, cable, and host conditions.
3. Capture `lsusb`, kernel hotplug logs, serial output, and timestamps together.
4. Use the vendor tool only after the device identity is established; record
   its version, command, input hash, output/readback hash, and subsequent boot.
5. Update the main spec only after reviewing raw evidence. A negative result
   leaves the requirement grounded as an explicit limitation.
