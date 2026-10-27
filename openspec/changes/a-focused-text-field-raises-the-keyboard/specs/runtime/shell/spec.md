## ADDED Requirements

### Requirement: A focused text field raises the on-screen keyboard

*Grounding: Firefox OS raised its keyboard on field focus (operator request 2026-10-26). Sway 1.12 builds `wlr_input_method_manager_v2` and `wlr_text_input_manager_v3`, and foot 1.27 and GTK4 4.22 contain text-input-v3 client code (strings of the built store paths; design.md findings 1 to 4).*

<!-- UNVERIFIED --> When a text field in the focused application becomes active for text input, the shell SHALL show the on-screen keyboard, and when it stops being active the shell SHALL hide it. The shell SHALL do so without receiving, altering or committing any text and without grabbing the keyboard.

The shell SHALL NOT show the on-screen keyboard for a field that becomes active within 10 seconds of the last key pressed on the keyboard base. The on-screen keyboard SHALL remain available through its usual gesture.

#### Scenario: Tapping a text field

- **WHEN** the person taps an entry in a GTK application or the foot terminal while the on-screen keyboard is hidden
- **THEN** the on-screen keyboard rises

#### Scenario: Leaving the field

- **WHEN** the on-screen keyboard is up for a focused field and focus moves to a window with no text input
- **THEN** the on-screen keyboard hides

#### Scenario: Typing on the base

- **WHEN** the person has been typing on the keyboard base and a field becomes active less than 10 seconds after the last key
- **THEN** the on-screen keyboard stays hidden

#### Scenario: Keys still reach the application

- **WHEN** the on-screen keyboard was raised by field focus and the person types on the base or the glass
- **THEN** every key reaches the focused field exactly as without this requirement
