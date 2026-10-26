## MODIFIED Requirements

### Requirement: Home offers a 4x2 Battery - Details widget showing the gauge and charger metrics

*Grounding: the attributes come from the board's `bq27220-0` fuel gauge and
`bq25890-charger-0` charger as read from sysfs on 2026-10-15 while charging
over USB-C (`docs/evidence/keyboard-base/charger/README.md` records the gauge's
sign convention, about +600 to +700 mA charging and -400 mA discharging, and
the charger's registers). Layout legibility is a host render
(`docs/evidence/battery-details-widget/host/README.md`). Appearance and values
on the board were matched against sysfs in grim captures
(`docs/evidence/battery-details-widget/board/README.md`). The operator placed
the widget from the picker with the physical trackpad and accepted it
(`docs/evidence/home-screen/operator-trackpad-2026-10-15.md`).*

*Grounding (2026-10-26): board grim captures of the fixed build in `docs/evidence/shell-design-review/README.md` record the cut input line and the background chooser's frameless side slice; the operator accepted them as open limits (`docs/evidence/shell-design-review/operator-report.md`).*

<!-- Grounding: injected-touch grim captures in docs/evidence/design-review-leftovers/README.md, and the operator's on-glass acceptance of build qh3i7b3f on 2026-10-26 (docs/evidence/design-review-leftovers/operator-report.md). -->
Home SHALL offer a "Battery - Details" widget occupying 4 columns by 2 rows,
drawn by the shell and placeable on any grid page like the other widgets. It
SHALL show the battery percentage prominently with the state word (Charging,
Discharging, Full or Not charging) and, while charging, the charge type; the
time to full or time to empty when the gauge reports it; battery current in
milliamps with its sign (positive charging, negative discharging) and power in
watts; battery voltage; stored charge against full charge in milliamp-hours;
health as full charge over design charge; cycle count; battery temperature in
degrees Celsius; and a charger line stating whether input power is online, the
input current limit, the charge current and voltage targets, and the charger's
health when it is not Good. When the charger line is wider than the widget it
SHALL drop the charge targets first and then the input limit rather than be
cut off; the power source and a charger fault SHALL always stay. The shell SHALL find the battery and charger by
their `power_supply` type and parse one `uevent` per supply; any attribute that
is missing SHALL be omitted rather than shown as zero or a placeholder. When no
battery supply exists the widget SHALL show the same "No battery info" state as
the Battery widget. The existing Battery widget and previously saved layouts
SHALL be unaffected.

#### Scenario: Charging with a fast charge

- **WHEN** the gauge reports Charging, 55 percent, +600 mA, 4.20 V, 1627 of
  3000 mAh and a time to full of 8160 s
- **THEN** the widget shows the percentage, "Charging" with the charge type,
  "2 h 16 m to full", "+600 mA", the power in watts, "4.20 V",
  "1627 / 3000 mAh", health 100 percent and the temperature

#### Scenario: Discharging

- **WHEN** the gauge reports Discharging with a negative current and a time to
  empty
- **THEN** the widget shows the negative current with its minus sign and the
  time as "left", and the charger line reads "On battery"

#### Scenario: Attributes are missing

- **WHEN** a supply omits attributes such as cycle count or temperature
- **THEN** only those metrics are left out and the rest still render

#### Scenario: No battery

- **WHEN** no supply of type Battery exists
- **THEN** the widget shows "No battery info"

#### Scenario: Faster refresh only while the widget is on Home

- **WHEN** a Battery - Details widget is placed on any Home page
- **THEN** the battery is re-read about every 10 seconds and Home repaints
  only when a displayed value changes; with no such widget the poll stays at
  about 30 seconds

#### Scenario: Older layouts still load

- **WHEN** a layout saved before this widget existed is loaded
- **THEN** it loads unchanged

#### Scenario: The charger line is too wide

- **WHEN** "USB power · limit 3.25 A · 2.05 A @ 4.21 V" is wider than the widget
- **THEN** the line reads "USB power · limit 3.25 A", or "USB power" if that is
  still too wide, with no ellipsis
