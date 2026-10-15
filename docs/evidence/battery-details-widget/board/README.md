# Battery details widget on the board (HDMI, 1280x800)

Evidence class: injected pointer + operator swipe + native grim capture.
Not a camera recording.

System: `/nix/store/ppwzss1aydag4iacqrzw1ba0ilyycrrd-nixos-system-nixos-26.11.20260919.20b1ddd`
(bundle `lh8k1i2ab0byh5w8vrf3zvnsx17j17bj-k230-coherent-shell-boot-files`), 2026-10-15.

## Steps

1. Injected `swaymsg seat - cursor` right-click on empty Home at (640,400)
   opened the Home menu; a click on Widgets showed the picker
   (`picker-widgets-page-1280x800-grim.png`, "Battery - Details" in the second
   column).
2. Injected click on the "Battery - Details" row (940,435). Page 1 had no free
   4x2 space, so the widget was placed at slot 0 of a new page 2
   (`home.json` page 2 slot 0 = `battery_details`); page 1 stayed in view.
3. The operator swiped to page 2 on the board's trackpad. Injected
   press-and-move via `swaymsg cursor set`/`cursor move` did not deliver
   motion to the client, so the scripted page turn was not possible.
4. grim at 17:18 CDT: `home-page2-battery-details-1280x800-grim.png`.

## Values shown vs sysfs (read 2026-10-15 17:18:15 CDT)

| Widget | sysfs |
|---|---|
| 100%, Full | bq27220-0 `CAPACITY=100`, `STATUS=Full` |
| Current 0 mA, Power 0.0 W | bq27220-0 `CURRENT_NOW=0` |
| Voltage 4.07 V | bq27220-0 `VOLTAGE_NOW=4069000` |
| Temp 35.1 °C | bq27220-0 `TEMP=351` |
| Charge 2991 / 3000 mAh | `CHARGE_NOW=2991000`, `CHARGE_FULL=3000000` |
| Health 100% | `CHARGE_FULL` / `CHARGE_FULL_DESIGN` = 3000000 / 3000000 |
| Cycles 0 | `CYCLE_COUNT=0` |
| On battery | bq25890-charger-0 `ONLINE=0` |

## Limits

- Only the full, idle, unplugged state was observed; the charging and
  discharging lines (time to full/empty, USB input line) are covered by host
  renders only.
- The placement used an injected click, not a physical trackpad click.
- A widget that does not fit the page in view lands on another page without
  bringing it into view; observed here, left for a follow-up change.
