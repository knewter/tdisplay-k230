## ADDED Requirements

### Requirement: Settings offers Cellular and Location only when the modem exists

<!-- UNVERIFIED: modem presence detection has not been exercised on this unit. -->
When the keyboard base's modem has answered at least once since the image was installed, Settings SHALL offer:

- a Cellular page with an on/off switch, SIM state, PIN entry when the SIM asks for one, operator, access technology and signal;
- a Location page with an on/off switch and searching or fix state;
- a control to clear stored text messages.

Every switch SHALL take effect through the modem service and persist across reboots. Without the modem, Settings SHALL NOT show these pages.

#### Scenario: Turning Location on

- **WHEN** a person turns Location on in Settings
- **THEN** the modem powers on, the page shows searching, and the choice is still on after a reboot

#### Scenario: Board without the base

- **WHEN** Settings opens on a board without the keyboard base
- **THEN** neither page appears
