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

<!-- UNVERIFIED: no board run with an HDMI mouse and the clock screen exists. -->
Pointer motion or a button from a mouse SHALL close the clock screen in the
same way a touch or key does, and SHALL NOT reach the app beneath it.

#### Scenario: Mouse moved while the clock shows
- **WHEN** the clock screen is up and a connected mouse moves
- **THEN** the clock screen closes, brightness is restored, and the prior card is in front

### Requirement: The clock screen starts on demand

<!-- UNVERIFIED: not built. -->
A person SHALL be able to start the clock screen from the shade or Home
without waiting for the idle timeout. It SHALL then behave as if idle opened
it: input closes it, and on battery it SHALL NOT start.

#### Scenario: Start from the shade on the charger
- **WHEN** the charger is connected and the person taps the clock tile
- **THEN** the clock screen opens, and the next touch closes it without reaching an app
