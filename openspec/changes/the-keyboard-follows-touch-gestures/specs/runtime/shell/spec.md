## ADDED Requirements

### Requirement: The coherent shell offers discoverable keyboard gestures

<!-- UNVERIFIED -->
The system's coherent shell SHALL reveal the external keyboard with a deliberate two-finger upward swipe from the bottom edge and expose a visible handle above a shown keyboard for downward dismissal. Settings SHALL retain an explicit keyboard action and describe the gestures. One-finger bottom navigation MUST remain available without opening the keyboard.

#### Scenario: Show the keyboard explicitly
- **WHEN** the keyboard is hidden and a person swipes upward with two fingers beginning at the bottom edge
- **THEN** the keyboard appears for the current app without opening the app drawer or switching apps

#### Scenario: Discover dismissal
- **WHEN** the keyboard is shown
- **THEN** a visible, touch-sized handle above its keys permits a downward dismiss drag without needing an external keyboard or permanent navigation bar

### Requirement: Keyboard motion follows contact and settles continuously

<!-- UNVERIFIED -->
During an accepted keyboard drag the system SHALL move the keyboard with direct proportional contact displacement, remain stationary while contact is held still, and reverse immediately with contact. Release SHALL settle from the displayed geometry and bounded measured velocity to shown or hidden without a position jump or abrupt end. Reduced motion SHALL preserve direct manipulation while shortening release settlement. Reserved app space MUST match the final visible keyboard and remain coherent during transition.

#### Scenario: Drag and reconsider
- **WHEN** a person drags the keyboard handle down, pauses, reverses, and releases before dismissal commits
- **THEN** the keyboard mirrors that motion and returns smoothly without losing the focused app

#### Scenario: Finish hiding
- **WHEN** a downward dismiss gesture commits
- **THEN** the keyboard smoothly leaves the output, its handle disappears and the app regains the available space

### Requirement: Keyboard gestures preserve typing and touch ownership

<!-- UNVERIFIED -->
The system SHALL claim only its explicit edge chord or handle stream and SHALL preserve ordinary key taps and application touch input. Cancelled, late, additional or lost contacts MUST NOT type keys, launch apps, or strand an invisible input surface. Keyboard failure, output change and interrupted settling SHALL restore a usable app and a reachable Settings action. The Wi-Fi editor's integrated keyboard MUST retain its own explicit cancellation and focus contract.

#### Scenario: Ordinary typing stays ordinary
- **WHEN** a person taps or moves within ordinary keyboard keys without starting on the dismiss handle
- **THEN** input remains owned by the keyboard and does not dismiss it or navigate apps

#### Scenario: A gesture is interrupted
- **WHEN** an accepted keyboard gesture loses its contact stream or the keyboard process exits
- **THEN** no residual gesture becomes a key/app action and the app remains reachable
