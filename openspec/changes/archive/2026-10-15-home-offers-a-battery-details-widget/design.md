## Context

Home's 2x2 Battery widget shows a percent ring and a charging bolt. The
keyboard base exposes a BQ27220 fuel gauge (`bq27220-0`, type Battery) and a
BQ25896 charger (`bq25890-charger-0`, type USB) through `power_supply`, with
current, voltage, charge, health, cycles, temperature, input limit and charge
targets. None of it reaches Home.

## Goals / Non-Goals

**Goals:** one Home widget that shows every useful battery and charger metric
the drivers expose, read cheaply and without breaking saved layouts.

**Non-Goals:** history graphs, charger controls, notifications, driver
changes, a Settings details page.

## Decisions

1. **New widget kind, not a mode of the old one.** `WidgetKind::BatteryDetails`
   serializes as `battery_details`, so existing `home.json` files and the 2x2
   Battery widget are untouched. It is 4x2 so the metric grid fits at panel
   and HDMI sizes.
2. **One `uevent` read per supply.** `home_widgets::battery::read_details`
   parses `/sys/class/power_supply/*/uevent`, picking supplies by
   `POWER_SUPPLY_TYPE`. Every field is optional; a missing field drops its
   cell rather than showing a placeholder.
3. **Derived values.** Power is |current| x voltage; time to full or empty
   is computed from charge and current when the gauge gives no time field;
   health is `CHARGE_FULL / CHARGE_FULL_DESIGN`. Current is rounded to 10 mA
   so noise does not force repaints.
4. **Polling.** 10 s while a Battery - Details widget is placed, else the
   existing 30 s. Repaint only when a displayed string changes.

## Risks / Trade-offs

- The gauge's `CURRENT_NOW` reads 0 when idle or full, so power shows 0.0 W
  in that state; this matches the hardware rather than hiding the cell.
- The discharging host fixture is invented; only the full/idle/unplugged
  state has been observed on the board
  (`docs/evidence/battery-details-widget/board/README.md`).
