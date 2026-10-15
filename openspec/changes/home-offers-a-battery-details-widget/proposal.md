## Why

Home's Battery widget is a 2x2 ring showing a percentage and a charging bolt.
A person who plugs the handheld in cannot tell from Home how fast it is
charging, how long until full, whether the charger or the cell is warm, or how
worn the cell is. The keyboard base now carries a BQ27220 fuel gauge and a
BQ25896 charger that expose all of this through `power_supply`; none of it
reaches the screen.

## What Changes

- Add a 4x2 "Battery - Details" Home widget: large percent, state word (with
  charge type while charging) and time to full or empty, then a compact grid of
  battery current and power, voltage, stored charge against full, health, cycle
  count, temperature, and the input/charger line (source online, input limit,
  charge current and voltage targets, charger health when not Good).
- Read the metrics from one `uevent` file per supply, discovered by supply
  `type`, with every field optional and omitted when absent.
- Poll every 10 s while any Battery - Details widget is placed on Home,
  otherwise keep the existing 30 s; repaint only when a displayed value
  changes at its displayed precision.
- Leave the existing 2x2 Battery widget, the shade battery text and saved
  layouts unchanged; the new widget is a new serialized tag.

**Non-goals:** historical graphs, charge-limit or charger controls, low-battery
notifications, changing the kernel drivers, a details view in Settings.

Needs the physical board only for the final value comparison; the
implementation and host renders proceed without it.
