## ADDED Requirements

### Requirement: An HDMI unplug restores idle brightness with the display

<!-- UNVERIFIED: `nix/touch-trackpad/src/shell_ipc.rs` sends `output * power on` on HDMI unplug without reporting activity to the idle dimmer (read in source, 2026-10-28); the dim-left-behind effect has not been observed on the board. -->
When HDMI is unplugged and the shell turns the panel on, the system SHALL
treat it as activity. Brightness SHALL return to the value saved before the
idle dimmer lowered it, and the idle timer SHALL start again from zero.

#### Scenario: Unplug while dimmed
- **WHEN** the panel is dimmed or off and HDMI is unplugged
- **THEN** the panel lights at the saved brightness, and dims again only after a full idle timeout with no input

### Requirement: Pointer activity closes the clock screen

<!-- UNVERIFIED: no real mouse yet. Injected 2026-10-28: one move of a uinput relative pointer closed the card, restored 148 and refocused the terminal (docs/evidence/resting-display-follow-ups/README.md). -->
Pointer motion or a button from a mouse SHALL close the clock screen in the
same way a touch or key does, and SHALL NOT reach the app beneath it.

#### Scenario: Mouse moved while the clock shows
- **WHEN** the clock screen is up and a connected mouse moves
- **THEN** the clock screen closes, brightness is restored, and the prior card is in front

### Requirement: The clock screen starts on demand

<!-- UNVERIFIED: the battery case (tile on battery starts nothing) is host-only. Injected 2026-10-28 on the charger: the shade tile opened the card at 37 of 148 with focus, and one touch closed it and restored 148 (docs/evidence/resting-display-follow-ups/README.md). -->
A person SHALL be able to start the clock screen from the shade or Home
without waiting for the idle timeout. It SHALL then behave as if idle opened
it: input closes it, and on battery it SHALL NOT start.

#### Scenario: Start from the shade on the charger
- **WHEN** the charger is connected and the person taps the clock tile
- **THEN** the clock screen opens, and the next touch closes it without reaching an app

#### Scenario: Tap the clock tile on battery
- **WHEN** no charger is connected and the person taps the clock tile
- **THEN** the clock screen does not start, brightness does not change, and the shade stays open with a line saying the clock screen needs the charger

### Requirement: The clock screen shows how many notifications wait

*Grounding (2026-10-28): board, build `q8k8w3mb…`. Three broker events showed "● 3" under the date, and after `dismiss-all` the next redraw had no dot. The card used 60 ms of CPU with the dot and 50 ms without, per 120 s (docs/evidence/resting-display-follow-ups/README.md).*
When the notification broker holds one or more events, the clock screen SHALL
show a small dot and the number under the date, refreshed with the minute
redraw. It SHALL show nothing when there are none or the broker cannot be
read, and the read SHALL NOT add wakeups beyond the existing minute and poll
timers.

#### Scenario: Notifications wait while the clock shows
- **WHEN** the clock screen is up and the broker holds three events
- **THEN** within a minute a dot and "3" appear under the date, and no dot appears when the broker holds none
