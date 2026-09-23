## 1. Prepare safe observation

- [ ] 1.1 Confirm the known-good image hash, serial device, J3 data cable, J2 console cable, and host USB logging commands.
- [ ] 1.2 Record the current UMS/card-reader recovery instructions and define the rollback image before any destructive test.

## 2. Characterise BootROM entry

- [ ] 2.1 Run `./tools/console.py /dev/ttyACM0 --wait=3 "help"` for the baseline, power off, remove the TF card, power through J3, and capture `lsusb -d 29f1:0230 -v`, `dmesg --since ...`, and serial output; record whether a BootROM device appears.
- [ ] 2.2 Power off, reinstall the card, hold SW3/BOOT0 during power-on, and repeat `lsusb -d 29f1:0230 -v`, `dmesg --since ...`, and `./tools/console.py /dev/ttyACM0 --wait=3 "help"`; record whether a BootROM device appears.
- [ ] 2.3 Review both raw captures and identify the observed VID/PID, interface, connector, and exact entry condition, or record a negative result.

## 3. Characterise the recovery tool conditionally

- [ ] 3.1 If a BootROM device appears, pin and document the `k230_flash` source/tool version and inspect its help and target-selection behavior.
- [ ] 3.2 After confirming the target identity, copy the known-good image, deliberately make only the stage-1 region nonbootable, and write it with the pinned tool; record input hash, command, duration, and tool output. If safety prerequisites are absent, leave this task incomplete and record why.
- [ ] 3.3 Reboot and verify serial boot plus image/hash evidence from the recovered card; a successful tool exit without a boot is insufficient. If the write was unsafe or unattempted, leave recovery verification incomplete.

## 4. Reconcile the specification

- [ ] 4.1 Add raw evidence and a concise result report under `docs/evidence/` without rewriting failed attempts into success.
- [ ] 4.2 Update the `image/boot-chain` requirement grounding and preserve an explicit limitation when BootROM recovery is unavailable.
- [ ] 4.3 Run `openspec validate --all` and the site/docs checks; review that UMS and BootROM claims remain distinct.
