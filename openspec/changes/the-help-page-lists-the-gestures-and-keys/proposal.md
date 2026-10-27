## Why

Help is stale. A person who opens it learns five things, and the shell now
does much more:

- **Gestures with no entry.** Quick-switching along the bottom band, throwing
  a card up in the overview, holding a drawer tile for its menu, the side-edge
  swipe that dismisses shell surfaces, and hiding the keyboard with its handle.
- **The keyboard base.** Its LILYGO, Fn and Esc keys, and the fact that a
  base key hides the on-screen keyboard, are not mentioned.
- **The power key.** A short press toggles the display and a hold opens the
  power sheet. Nothing says so.

## What Changes

- Help's guide becomes two groups, **Touch** and **Keys**.
  - On the wide (landscape) layout they are two columns: Touch on the left,
    and the Help buttons with Keys under them on the right.
  - On the portrait layout they stack: Touch, then Keys, then the buttons.
- Touch lists: leaving an app, switching apps along the bottom band, All apps,
  the drawer tile's app menu, throwing a card up to close, the shade, closing
  a panel (including the side-edge swipe, which never sends Back to an app),
  and the two-finger keyboard gesture with its handle.
- Keys lists: LILYGO, LILYGO + Tab, Fn + LILYGO, Esc, typing on the base, and
  the power key.
- Help is longer than a screen, so it scrolls with its existing model. The
  navigation aid keeps fitting one screen.

Every entry is stated only as far as the code and specs read for this change
support it. The Help hit regions and the 99 px touch floor do not change.

## Non-goals

- No change to any gesture or key. Help only describes them.
- Not documented: drawer search keys. The brief proposed "LILYGO opens the
  drawer with search taking the keys; Enter launches the first match; Esc
  clears, then closes". In `nix/rust-shell-client/src/service_ui.rs`, search
  takes keys only after its field is tapped, Enter and Esc only dismiss the
  keyboard and keep the query, and nothing launches a first match. The
  keyboard-base spec's Enter scenario therefore has no matching code. Help
  says only that LILYGO opens the drawer.

## Capabilities

### Modified Capabilities

- `runtime/shell`: Help explains the gestures and keys (touch and keys groups).

## Impact

- `nix/rust-shell-client/src/help.rs` (guide text, two-group layout, tests)
- `nix/rust-shell-client/src/render.rs` (the Help paint call site draws the
  group headings)
- `nix/rust-shell-client/examples/render_help_refresh.rs` (host renders)

Needs the physical board only for the final glass check (task 2).
