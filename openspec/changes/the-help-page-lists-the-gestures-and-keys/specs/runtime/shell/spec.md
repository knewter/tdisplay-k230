## MODIFIED Requirements

### Requirement: Help explains the keyboard-free shell

<!-- UNVERIFIED: the Touch and Keys groups are verified by host tests and host renders only (docs/evidence/help-refresh/host/); board captures and the operator's reading on glass remain open (the-help-page-lists-the-gestures-and-keys task 2). Final physical-finger readability and final-glass acceptance for the new Help pages remain separate from injected native screenshots. -->
*Grounding: gesture and key behaviour from the `runtime/shell`, `runtime/handheld-shell-design` and `runtime/card-shell` specs, `nix/shell.nix` key bindings, `nix/keyboard-base/keyboard_based.py` and `nix/power-keyd/power_keyd.py`; layout in `nix/rust-shell-client/src/help.rs`.*
The shell SHALL provide an offline Help surface reachable from Apps and SHALL describe the purpose and action of Apps, Keyboard, Windows/Home, System, Back, paging, and the terminal and monitor actions. Help SHALL group its guidance as Touch and Keys. Touch SHALL cover leaving an app, switching apps along the bottom band, All apps, the drawer tile's app menu, throwing a card up in the overview to close it, the notification shade and Settings, closing a panel including the side-edge swipe that never sends Back to an app, and the two-finger keyboard gesture with its handle. Keys SHALL cover LILYGO, LILYGO with Tab, Fn with LILYGO, Esc as shell back when no app has focus, a base key hiding the on-screen keyboard, and the power key's short press and hold. On the wide (landscape) layout the groups SHALL be two columns, and on the portrait layout they SHALL stack. Help text SHALL use the shell's type roles and the vision text step, and Help SHALL scroll when its content is taller than the output. Help SHALL be readable at 568x1232 in portrait mode, support touch navigation back to Apps with targets at least 99 pixels tall, and avoid requiring a network, physical keyboard, or text entry.

#### Scenario: A new user reads the controls

- **WHEN** the user taps Help and pages through its content
- **THEN** each persistent control, launcher navigation action, gesture and base key has a concise visible explanation, under Touch or Keys

#### Scenario: Landscape Help

- **WHEN** Help opens on the landscape panel
- **THEN** Touch fills the left column and Keys sits in the right column under the Help buttons

#### Scenario: Portrait Help

- **WHEN** Help opens on the portrait panel
- **THEN** Touch is followed by Keys, then the Help buttons, in one scrolling column

#### Scenario: A user leaves Help

- **WHEN** the user taps Back from Help
- **THEN** Help closes and the user returns to the launcher or persistent shell controls without losing the existing touch actions
