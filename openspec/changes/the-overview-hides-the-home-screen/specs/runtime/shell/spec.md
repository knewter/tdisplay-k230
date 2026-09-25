## ADDED Requirements

### Requirement: The card overview hides the Home screen while active

<!-- UNVERIFIED: fixed and headless-QEMU-tested in this change (a native
Layer::Bottom fixture standing in for Home, plus debug-scene assertions);
no real-finger or real-theme board observation exists yet. -->

The shell SHALL NOT show any part of the Home screen surface while the card
overview (`card_shell`'s deck) is active, for the whole duration the
overview is entered -- including the finger-driven bottom-edge entry
gesture from its first touch-down, not only once the gesture settles -- and
SHALL restore the Home screen's normal visibility the moment the overview
hands the screen back to a focused application or to the idle/no-app state.

#### Scenario: The overview is entered while Home would otherwise be exposed

- **WHEN** a person swipes up from the bottom edge of a running application,
  or the overview is entered directly (e.g. a recovery route), regardless of
  whether the active theme's overview canvas is opaque or configured to
  reveal the wallpaper
- **THEN** no Home grid tile, dock icon, or other Home content is visible at
  any point during the entry gesture or the settled overview

#### Scenario: Dismissing the overview with nothing focused restores Home

- **WHEN** the overview is dismissed (back/close) and no application ends up
  focused
- **THEN** the Home screen becomes visible again, exactly as it would have
  been had the overview never opened

#### Scenario: An unrelated focus change while the overview is open does not reshow Home

- **WHEN** anything reassigns keyboard/seat focus while the overview
  remains open (for example an IPC `focus` command reaching an already-
  mapped card, or any other code path outside `card_shell`'s own gesture
  and button handling), and the overview's own state does not otherwise
  change
- **THEN** the Home screen stays hidden; correcting this is not limited to
  the specific moments `card_shell`'s state machine itself toggles
  visibility (entering, leaving)
