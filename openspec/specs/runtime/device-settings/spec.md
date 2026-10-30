# runtime/device-settings Specification

## Purpose
Defines truthful device settings and system actions that a person can understand and operate on the handheld without an external keyboard.

## Requirements

### Requirement: Settings expose only supported state and actions

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL show only controls backed by a readable or writable system capability in the installed image. It SHALL identify unavailable, read-only, and pending controls explicitly. It SHALL NOT show a battery gauge or battery-dependent action without observed battery hardware and state reporting.

#### Scenario: Network state cannot be read
- **WHEN** a person opens Settings and network state is unavailable
- **THEN** the network row says unavailable and does not display a fabricated connected state

#### Scenario: Control application fails
- **WHEN** a requested change cannot be applied
- **THEN** Settings shows failure and a Retry or contextual dismissal action while preserving the last confirmed state

#### Scenario: Settings content exceeds the panel
- **WHEN** the person drags or flicks a longer Settings list
- **THEN** the rows follow the finger and settle within bounds while the current control value and contextual return route remain understandable

### Requirement: System actions require clear completion feedback

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL label power and restart actions by effect, require confirmation for disruptive actions, and report denial or failure without trapping the person. Settings defaults SHALL be provided by the NixOS image for a fresh home.

#### Scenario: Restart is cancelled
- **WHEN** a person opens Restart confirmation and chooses Cancel
- **THEN** Settings returns to the shade or prior scene with prior focus and no restart request

### Requirement: A denied system action SHALL explain itself
*Grounding: `docs/evidence/recovery-routes/touch-capture-2026-10-11/README.md` (2026-10-11): a real-finger brightness drag after the backlight was made read-only over serial; the shell logged `brightness-denied`, and a native `grim` capture shows "That action isn't allowed · Done" under Settings' Done header.*
When a system action is refused, the shell SHALL show short person-facing copy and a visible Back or Retry action, and SHALL NOT render raw paths, helper output, or secrets.

#### Scenario: An action is denied
- **WHEN** a person requests a system action the system refuses
- **THEN** the surface says the action was not allowed and shows Back

### Requirement: Settings offers a keyboard backlight control only when the base has one

*Grounding: Board 2026-10-14: Settings shows the Key backlight row on the base and an injected tap toggles it (docs/evidence/keyboard-base/shell/board/); host renders show it hidden without the LED and, with it, a four-detent slider (Off, Low, Medium, High). The PWM LED has 255 steps (docs/evidence/keyboard-base/backlight/); Low, Medium and High are 8 %, 30 % and 100 % of it in `keyboard_based.py`. Board 2026-10-14: the slider on the glass previews each level live (operator) and the LED reads 20/76/255 within 0.5 s of each stored level (docs/evidence/keyboard-base/backlight/).*

When a `kbd_backlight` LED device exists, Settings SHALL offer a keyboard backlight control: an on/off switch while the device has one brightness step, and a level slider once it has more. The choice SHALL persist across reboots in system state, not in a home directory. Moving the slider to a lit level SHALL light the keys at that level within a fraction of a second, for a short preview, without a key press; outside that preview the keys stay lit only while typing. When no such device exists, Settings SHALL NOT show the control.

#### Scenario: Turning the key backlight off

- **WHEN** a person turns the keyboard backlight off in Settings and then types
- **THEN** the key legends stay dark, and stay dark after a reboot

#### Scenario: Choosing a level shows it live

- **WHEN** a person drags the keyboard backlight slider from Low to High
- **THEN** the key legends light at each level as the slider reaches it, and go dark again a few seconds after the drag if nobody types

#### Scenario: No keyboard base

- **WHEN** a person opens Settings on a board without the keyboard base
- **THEN** no keyboard backlight control appears

### Requirement: Settings offers a vision-accessibility text scale and high-contrast option

*Grounding (2026-10-16): the first implementation offered one larger step
(1.25x). On the panel (568x1232 at 4.1", about 331 ppi, 2.07 px per dp) the
default body text is 17-18 px (about 8.5 sp) and drawer labels are 14 px
(about 6.8 sp), roughly half of common phone defaults. The 1.25x step left the
drawer illegible to the operator: "the drawer is not particularly legible at
'large' text", with labels ellipsized ("Same G…") over a translucent drawer
that shows the Home clock and wallpaper through it
(`docs/evidence/coherent-shell/accessibility-scale/board/11-panel-drawer.png`).*

*Grounding (2026-10-16): the four steps and the reflow were host-tested and
rendered at every step in both orientations
(`docs/evidence/coherent-shell/accessibility-scale/README.md`, "Redesign").
On the landscape panel, native `grim` captures at 160% and 200% of Home, the
drawer, the Shade, Settings and the Vision page are in `board/13`–`23` of
that directory. The operator judged them legible on glass. Persistence across
a reboot was observed on the board with injected taps (`board/06`, `07`).
The card-shell headers' scaling is host-tested only
(`tests/test_card_shell_appearance.py`); no board capture of the card deck at
a larger step exists.*

Settings SHALL offer a person four text-size steps, 100%, 130%, 160% and 200%
of the shell's design size, and a high-contrast palette variant. Both choices
are independent of the theme currently active and of the existing
reduced-motion toggle. The 200% step follows WCAG 1.4.4 (resize text). At
every step, text SHALL reflow rather than be cut off: drawer labels wrap to
at most two lines and the drawer uses fewer columns, and Settings and Shade
cards grow to fit their text. A label is ellipsized only when it would
exceed two lines at the chosen size. With any vision option other than the
defaults, the drawer and Shade SHALL draw their text over an opaque surface,
not a translucent one that shows Home through it, and app icons and their
tap targets SHALL grow with the step up to at least 48 dp (99 px on this
panel).

The chosen scale and contrast variant SHALL apply consistently to both the
Rust-rendered surfaces (Home, drawer, shade, Settings) and the C-rendered card
deck and its labels, using the same shared theme-token mechanism that already
carries per-theme colors across that boundary, so a person does not get a
larger Settings but an unchanged card header. Home widgets keep the
proportions of their cells, so a widget's contents are not scaled by the step;
the Clock widget's date, which follows the step, is the exception. The choice SHALL persist across
restarts the same way the active theme choice already does.

#### Scenario: A person chooses a larger text size

- **WHEN** a person selects the 130%, 160% or 200% text-size step in Settings
- **THEN** Home's app labels, the drawer, the shade, Settings, and card
  headers all render at that size, not only the Settings screen itself

#### Scenario: The largest step keeps every drawer label readable

- **WHEN** the 200% step is active and the drawer is open on the panel in
  either orientation
- **THEN** every app label is shown whole on at most two lines over an opaque
  surface, with no label crossing a neighbouring tile and no icon or tap
  target smaller than 99 px

#### Scenario: A person chooses the high-contrast variant

- **WHEN** a person selects the high-contrast variant
- **THEN** the active theme's colors are overridden by the high-contrast
  palette consistently across both renderers, and the choice survives a
  reboot the same way an active theme choice does

#### Scenario: The choice is independent of other accessibility controls

- **WHEN** a person has reduced motion enabled, disabled, or has opened the
  separately planned gesture-discovery accessibility aid
- **THEN** the text-scale and high-contrast choice is unaffected by, and
  does not affect, either of those settings

### Requirement: Settings reads plainly and scrolls cleanly

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
Settings SHALL place its Vision and Themes links in the title row. While its body is scrolled, content passing under the section header SHALL meet a divider and a fade, never a bare cut through text. Control values SHALL be words a person uses: the Wi-Fi link SHALL read "Connected" or "Not connected" rather than a raw state, and the motion preference SHALL be titled "Reduce motion". The audio output SHALL show its name without an instruction suffix.

#### Scenario: Scrolled Settings
- **WHEN** Settings is scrolled so a card passes under the "Device controls" header
- **THEN** the card fades out against a divider and no half-cut line of text sits against bare background

### Requirement: Settings chooses what an idle display does on the charger

*Grounding: the preference sits beside Do Not Disturb as a one-word file under `/var/lib/k230-shell-prefs`; no board observation of this row exists.*
<!-- UNVERIFIED: the row has not been built or seen on the board. -->
Settings SHALL list an "Idle on charger" row with the values Clock and Sleep whose hit region meets the shell's 99 px floor. A tap SHALL switch between them and store the choice so it survives a shell restart and a reboot. A missing or unreadable stored choice SHALL mean Clock.

#### Scenario: Choose Sleep

- **WHEN** a person taps the row until it reads Sleep and leaves the device idle on the charger
- **THEN** the display dims and turns off as on battery

#### Scenario: Fresh home

- **WHEN** no choice has ever been stored
- **THEN** the row reads Clock

### Requirement: Settings chooses the idle timeout

*Grounding (2026-10-28): board, build `q8k8w3mb…`. An injected tap on Idle timeout wrote `5m` and restarted the idle service with 150 s and 300 s. Unattended, 5 min dimmed at 146–152 s and turned the output off at 298–303 s, and Off did neither in 366 s (docs/evidence/resting-display-follow-ups/README.md).*
Settings SHALL offer Off, 1 minute and 5 minutes for when the display turns
off when idle. The choice SHALL persist across reboots beside the other
shell preferences. The idle service SHALL apply it from its next start.
Dimming SHALL come at half the chosen time. Off SHALL disable both steps.

#### Scenario: Five minutes chosen
- **WHEN** the person picks 5 minutes and leaves the board with no input
- **THEN** the panel dims at 2.5 minutes and turns off at 5 minutes

#### Scenario: Off chosen
- **WHEN** the person picks Off
- **THEN** the panel neither dims nor turns off on its own

### Requirement: Settings tunes the clock screen

*Grounding (2026-10-28): board, build `q8k8w3mb…`, idle path on the charger. Clock brightness Full, Half and Dim held the panel at 148, 74 and 37 of 148 with the card up. Clock effects Off gave no `ttfx` in 360 s against one at +11 s with 5 min. Clock limit None did not close the card in that time; the 2 h and 8 h caps are host tests only (docs/evidence/resting-display-follow-ups/README.md).*
Settings SHALL offer three rows for the clock screen shown while idle on the
charger. Clock brightness SHALL offer Dim, Half and Full, which run the
panel at 25%, 50% and 100% of the saved brightness while the clock screen is
up; Dim is the default. Clock effects SHALL offer 5 min, 15 min and Off for
how often a text effect plays; 5 min is the default. Clock limit SHALL offer
2 h, 8 h and None for how long the clock screen stays up before it closes
itself; 2 h is the default. Each choice SHALL persist across reboots beside
the other shell preferences, and an unreadable or unrecognised value SHALL
mean the default. The brightness SHALL apply the next time the clock screen
opens, and the effect interval and limit the next time the clock screen
starts.

#### Scenario: Full brightness chosen
- **WHEN** the person picks Full and the board goes idle on the charger
- **THEN** the clock screen opens at the brightness the panel had before it dimmed, and waking restores that same value

#### Scenario: Effects off and no limit chosen
- **WHEN** the person picks Off for Clock effects and None for Clock limit
- **THEN** the clock screen plays no effect and stays up until input or the charger is removed

### Requirement: Settings destinations are reachable from the drawer search

*Grounding (2026-10-28/29): injected board runs typed `wifi`, `about` and `ti` and opened Wi-Fi, About and Timer (docs/evidence/drawer-search/board/README.md); the operator reported "drawer search works" on glass (docs/evidence/glass-checklist-2026-10-29/operator-report.md).*
*Grounding: the Settings intents `OpenWifi`, `OpenCellular`, `OpenLocation`, `OpenDateTime`, `OpenAbout`, the Themes and Vision pages and the Do Not Disturb row were read in `nix/rust-shell-client/src/service_ui.rs` and `main.rs` at cff47b1e.*

Every Settings page and inline control that exists SHALL be findable from the drawer search by its label, and a destination whose hardware is absent SHALL NOT be findable. Opening one from search SHALL show the same screen a tap through the shade would, with the row in view for an inline control, and SHALL leave every setting as it was.

#### Scenario: A page destination

- **WHEN** a person finds Date & time in the drawer search and chooses it
- **THEN** the Date & time page opens and Back returns to Settings

#### Scenario: An inline control

- **WHEN** a person finds Brightness in the drawer search and chooses it
- **THEN** Settings opens with the Brightness row visible and the brightness unchanged

### Requirement: Settings offers a Do Not Disturb switch

*Grounding: the preference sits beside Reduce motion and Key backlight as a one-setting row (`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`, gap 12); no board observation of this row exists.*
*Grounding (2026-10-27, board, injected taps): on build `zs05li2k…` the Settings row and the shade tile read and wrote the same file and agreed both ways (`docs/evidence/do-not-disturb/board/README.md`, task 3.3).*
Settings SHALL list a Do Not Disturb row with an on and off switch whose hit region meets the shell's 99 px floor. It SHALL read and write the same preference as the shade tile, so the two cannot disagree.

#### Scenario: Toggle from Settings
- **WHEN** a person turns the row on in Settings and then opens the shade on the landscape panel
- **THEN** the Do Not Disturb tile shows On and the status line shows the moon glyph

### Requirement: Settings has an About page for the installed build

*Grounding (2026-10-27/28, board, injected): grim captures of About on builds `kllh24ww…` and `vf91pbq6…` in both orientations, and About's System row matched `readlink /run/current-system` (`docs/evidence/settings-about/README.md`). The operator read both pages on glass on 2026-10-29, build `37g1magg…`: "8 good" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
*Grounding: `nix/rust-shell-client/src/device_info.rs` reads `/etc/hostname`, the `/run/current-system` link, `/proc/sys/kernel/osrelease`, `/proc/uptime` and `statvfs`; the Cellular and Location pages (`modem_ui.rs`) are the page pattern. No board observation of the values yet.*
Settings SHALL offer an About row, the last row before Power, that opens a read-only page showing the device name, the system generation as the short hash and name of its store path, the kernel release, the uptime, the storage free and total, and the shell build as its version and the short store-path hash of the running shell. A value that cannot be read SHALL show "Unavailable" rather than a guessed value. The page SHALL NOT show an IP address, MAC address, SSID, serial number or secret. It SHALL have a Back link to Settings at least 99 pixels tall, use the shell's type roles and the vision text step, and refresh while open so the uptime moves.

#### Scenario: Which build is installed

- **WHEN** a person opens Settings and taps About
- **THEN** the page shows the device name, an eight-character system hash with its name, the kernel release, the uptime, the storage free and total and the shell version with its hash

#### Scenario: A value cannot be read

- **WHEN** a source such as the system generation link is missing
- **THEN** that row says Unavailable and the other rows still show

#### Scenario: Largest text step, landscape

- **WHEN** the vision text step is 200% on the landscape panel
- **THEN** every About row fits on the panel without scrolling and Back is still tappable

#### Scenario: Leaving About

- **WHEN** a person taps Back on About
- **THEN** Settings returns with its rows where they were

### Requirement: Settings has a Date & time page

*Grounding (2026-10-27/28, board): `/run/systemd/timesync/synchronized` existed after sync on build `kllh24ww…`, and grim captures of the page in both orientations are in `docs/evidence/settings-about/`. The operator read it on glass on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). Changing the zone or network time moved to `settings-sets-the-time-zone-and-network-time`.*
*Grounding (2026-10-29): the clock format became a switch in `settings-chooses-a-12-or-24-hour-clock`; board and glass evidence in `docs/evidence/clock-format/`.*
*Grounding: `nix/rust-shell-client/src/device_info.rs` (`localtime_r`, the `/etc/localtime` link, the timesyncd stamp); `nix/k230.nix` sets the zone at build time and `nix/hardware.nix` enables timesyncd and a time-sync-ordered RTC write. No board observation yet.*
Settings SHALL offer a Date & time row, ahead of About, that opens a page showing the date, the time, the time zone with its UTC offset, whether the clock is synchronized from the network, and the clock format. The date and time SHALL come from the system's local time so they follow the installed time zone, and the time SHALL follow the chosen clock format. The clock format row SHALL be the switch that "Settings chooses a 12-hour or 24-hour clock" describes; the page SHALL NOT offer a control that changes a setting the image cannot change. It SHALL have the same Back link, type roles, vision text step and refresh as About.

#### Scenario: Reading the clock

- **WHEN** a person opens Settings and taps Date & time
- **THEN** the page shows today's date, the time to the second, the zone name with its UTC offset, whether the clock is synchronized and the clock format

#### Scenario: Clock not yet synchronized

- **WHEN** the system has not set its clock from the network
- **THEN** the network time row says Not synchronized

#### Scenario: Portrait at the largest text step

- **WHEN** the vision text step is 200% on the portrait panel
- **THEN** every row fits the panel and Back is at least 99 pixels tall

### Requirement: The Settings rows reach the touch floor

*Grounding: host tests in `nix/rust-shell-client/src/service_ui.rs` and `render.rs` for the 99 px height. On the board, injected taps opened Date & time and About from Settings in both orientations (`docs/evidence/settings-about/`). Row heights were not measured on the board.*
Every Settings row that opens a page, including Cellular, Location, Date & time and About, SHALL be at least 99 pixels tall at every vision text step, and a tap on it SHALL open its page in both orientations whether or not the modem has answered.

#### Scenario: Rows with and without the modem

- **WHEN** Settings is shown with and without the modem rows
- **THEN** Date & time and About open their pages in both orientations and Power remains tappable below them

### Requirement: Settings chooses a 12-hour or 24-hour clock

*Grounding (2026-10-29): Settings' Date & time page shows "Clock format: 24-hour" as a fixed value (`nix/rust-shell-client/src/device_info.rs`), and the Python clocks format with `%H:%M` (`nix/term-apps/k230_term_apps.py`, `k230_exhibition.py`). The operator moved this follow-up out of `settings-has-about-and-date-time-pages` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-29): host tests and renders (`docs/evidence/clock-format/host/`); board, injected, on `p393r76c…`: the switch, every clock in 12-hour form, a shell restart and a reboot (`docs/evidence/clock-format/board/`); glass, 2026-10-29 23:54Z, the operator flipped the switch and saw the shade and Home follow (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

Settings' Date & time page SHALL offer the clock format as a choice between
24-hour and 12-hour, with a hit region that meets the shell's 99 px floor. The
choice SHALL persist across a shell restart and a reboot, and SHALL default to
24-hour when it has never been set or cannot be read. Every clock drawn by the
shell and by the shell's own apps SHALL follow it within a minute of a change,
without a restart.

#### Scenario: Switching to a 12-hour clock

- **WHEN** a person sets the clock format to 12-hour at 21:05
- **THEN** the shade, Home and the Date & time page show 9:05 PM, and the
  idle clock screen shows it the next time it draws

#### Scenario: No preference yet

- **WHEN** the shell starts and the clock-format preference has never been set
- **THEN** every clock is 24-hour, as before this change

### Requirement: Settings changes the time zone and network time

*Grounding (2026-10-29): the zone is build-time (`time.timeZone = "America/Chicago"` in `nix/k230.nix`), and Settings' Date & time page shows the zone and synchronization read-only (`nix/rust-shell-client/src/device_info.rs`; board captures in `docs/evidence/settings-about/`). The operator moved this follow-up out of `settings-has-about-and-date-time-pages` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-30): `nix/time-settings.nix` and `tools/k230_time_helper.py` (host tests in `tests/test_time_helper.py`); the chooser in `nix/rust-shell-client/src/device_info.rs` (host renders in `docs/evidence/time-zone/host/`). Board, injected, on `sqd58h8c…`: Europe/London applied and followed by the shade and Clock app without a restart, network time off, both held across a switch and a reboot, and other requests refused (`docs/evidence/time-zone/board/`). The glass step was replaced by injected checks on the operator's instruction. The page shows network time switched off as "Off". The zone change was observed in daylight time, a 5-hour move, not the scenario's standard-time 6 hours.*

Settings' Date & time page SHALL let a person choose the time zone from a list
and turn network time on or off. The change SHALL take effect without a
reboot, SHALL persist across a reboot and a switch to a new build, and SHALL
be applied by a privileged path that accepts only these two settings, so that
the shell user gains no other root access.

#### Scenario: Changing the zone

- **WHEN** a person in Settings chooses Europe/London while the clock reads
  15:00 in America/Chicago during standard time
- **THEN** the clocks read 21:00, and the Date & time page shows Europe/London
  with its UTC offset

#### Scenario: The choice survives a reboot

- **WHEN** the person has chosen a zone and the handheld reboots
- **THEN** the clocks still use that zone

#### Scenario: Turning network time off

- **WHEN** a person turns network time off
- **THEN** the page says the clock is not synchronized from the network, and
  stays that way after a reboot until it is turned back on
