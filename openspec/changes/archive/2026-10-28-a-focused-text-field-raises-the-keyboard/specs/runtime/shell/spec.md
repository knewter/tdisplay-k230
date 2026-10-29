## ADDED Requirements

### Requirement: A focused text field raises the on-screen keyboard

*Grounding: Firefox OS raised its keyboard on field focus (operator request 2026-10-26). Sway 1.12 builds `wlr_input_method_manager_v2` and `wlr_text_input_manager_v3`, and foot 1.27 and GTK4 4.22 contain text-input-v3 client code (strings of the built store paths; design.md findings 1 to 4). On the board (build `gpgh1vx6…`, injected), a GTK4 entry raised the keyboard and switching cards hid it, and foot raised it without flapping while typing. Timer and the other touch-only terminal apps did not raise it, and the overview lowered it (docs/evidence/a-focused-text-field/README.md). Base attached, 2026-10-28, injected on the board: the drawer search, foot and a GTK4 entry took focus with no keyboard, and the two-finger gesture still raised it (docs/evidence/a-focused-text-field/README.md § Base attached).*

When a text field in the focused application becomes active for text input, the shell SHALL show the on-screen keyboard, and when it stops being active the shell SHALL hide it. The shell SHALL do so without receiving, altering or committing any text and without grabbing the keyboard.

While the keyboard base's keys are attached, a field that becomes active SHALL NOT raise the on-screen keyboard, and this includes a tap on the app drawer's search field (operator request 2026-10-28). Without the base, the shell SHALL NOT show the on-screen keyboard for a field that becomes active within 10 seconds of the last key pressed on the base. Terminal-hosted applications that take only touch or only display (Timer, Clock, Weather, Monitor, btop) SHALL NOT raise it on focus, and the card overview SHALL lower it. The on-screen keyboard SHALL remain available through its usual gesture.

#### Scenario: Tapping a text field

- **WHEN** the keyboard base is not attached and the person taps an entry in a GTK application or the foot terminal while the on-screen keyboard is hidden
- **THEN** the on-screen keyboard rises

#### Scenario: Leaving the field

- **WHEN** the on-screen keyboard is up for a focused field and focus moves to a window with no text input
- **THEN** the on-screen keyboard hides

#### Scenario: A touch-only terminal app

- **WHEN** the Timer, which runs in foot, takes focus
- **THEN** the on-screen keyboard stays hidden and the Timer keeps the whole panel

#### Scenario: Opening the overview

- **WHEN** the on-screen keyboard is up for a focused terminal and the person opens the card overview
- **THEN** the keyboard lowers and the cards keep their size

#### Scenario: The base is attached

- **WHEN** the keyboard base is attached and the person taps an entry in an application or the app drawer's search field
- **THEN** the on-screen keyboard stays hidden, the base's keys type into the field, and the keyboard's gesture still raises it

#### Scenario: Typing on the base

- **WHEN** the person has been typing on the keyboard base and a field becomes active less than 10 seconds after the last key
- **THEN** the on-screen keyboard stays hidden

#### Scenario: Keys still reach the application

- **WHEN** the on-screen keyboard was raised by field focus and the person types on the base or the glass
- **THEN** every key reaches the focused field exactly as without this requirement
