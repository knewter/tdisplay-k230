## Context

LILYGO is Super_L on the base's own input device. Sway runs
`k230-shell-rust --surface drawer` on its release. The drawer search is a
`DrawerSearch` whose `focused` flag makes the layer surface take exclusive
keyboard focus and signals the on-screen keyboard to show.

## Decisions

- **A separate request line.** `drawer-keys` keeps the touch and test paths
  (`--surface drawer`) unchanged. Only the base's key focuses the search.
- **Keyboard grab without the on-screen keyboard.** The layer's exclusive
  keyboard focus and the on-screen keyboard signal are tracked separately, so
  a key focus takes the grab and leaves the keyboard down. A tap on the field
  afterwards raises it as before.
- **Enter launches the first match.** The first match carries the hover
  cursor's outline while keys type, so Enter's target is visible.
- **Esc clears, then closes.** Esc on a query is the cheap undo; Esc on an
  empty field leaves.
- **A binding mode that follows the deck.** Plain arrows, Enter, Esc and
  Backspace must never be taken from apps. The compositor sets Sway's mode to
  `overview` when the deck becomes active and back to `default` in `restore`,
  the one path every exit takes. A missing mode is ignored.
- **Fn arrows.** The base sends arrows with Fn (Mod5) held, so each arrow is
  bound with and without Mod5.

## Risks

- A deck exit that bypasses `restore` would leave the mode on. Every exit
  found goes through it. The board check includes leaving by touch, by
  Enter and by Esc, then typing in a terminal.
