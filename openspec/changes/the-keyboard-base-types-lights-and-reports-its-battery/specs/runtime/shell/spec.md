## ADDED Requirements

### Requirement: The shell gets out of the way of a hardware keyboard

<!-- UNVERIFIED: depends on the keyboard base's keys reaching Linux, which has not been observed. -->
When a person types on the keyboard base while the on-screen keyboard is shown, the shell SHALL hide the on-screen keyboard without losing the typed key. The on-screen keyboard SHALL stay available through its usual gesture. The shell SHALL NOT grab the base's input device away from Sway.

#### Scenario: Switching from glass to keys

- **WHEN** the on-screen keyboard is open over the terminal and the person presses a key on the base
- **THEN** the on-screen keyboard hides, the key's character appears in the terminal, and the terminal regains the space

### Requirement: Shell navigation works from the base's keys

<!-- UNVERIFIED: depends on the keyboard base's keys reaching Linux. The LILYGO and Fn keys and the vendor's Fn+LILYGO screenshot come from LILYGO `ui_hardware.c`. -->
The LILYGO key SHALL open the app drawer. LILYGO with Tab SHALL open the card overview. Fn with LILYGO SHALL take a screenshot of the panel. Esc SHALL perform the shell's back action when no application has keyboard focus, and SHALL reach the application unchanged otherwise.

#### Scenario: Launching an app without touching the glass

- **WHEN** a person presses LILYGO, types part of an app's name, and presses Enter
- **THEN** the drawer opens with its search filtered and the app launches

#### Scenario: Esc in an app

- **WHEN** a terminal has focus and a person presses Esc
- **THEN** the terminal receives Esc and the shell does not navigate

### Requirement: The shade shows battery state when a battery exists

<!-- UNVERIFIED: no battery has been observed under Linux on this board. -->
When a battery `power_supply` device exists, the shade SHALL show its charge percentage and whether it is charging, updated within 60 seconds of a change. When none exists, the shade SHALL show no battery element at all.

#### Scenario: Battery present

- **WHEN** a person pulls down the shade on a board with the keyboard base attached
- **THEN** the shade shows the battery percentage matching `capacity`, and a charging mark while a cable is connected

#### Scenario: No battery

- **WHEN** a person pulls down the shade on a board without the base
- **THEN** the shade shows no battery element
