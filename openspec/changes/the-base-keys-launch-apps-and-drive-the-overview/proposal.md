## Why

The shell spec already promises "LILYGO, type part of an app's name, Enter:
the app launches" (`runtime/shell`, "Shell navigation works from the base's
keys"). The code does not do it. The drawer's search takes keys only after a
tap on the field, that tap raises the on-screen keyboard over half the
landscape panel, and Enter only drops the keyboard. Typing after LILYGO goes
to the app behind the drawer.

The overview also has no keys. LILYGO+Tab opens it, but choosing, opening or
closing a card needs the glass. The compositor already has `card_shell
previous|next|activate|back|close`; nothing binds them. webOS's card view and
Firefox OS's task manager were both driven by their hardware keys too
(`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`, gaps 1 and 5).

## What Changes

- **LILYGO's drawer takes the keys.** The binding sends a new `drawer-keys`
  line instead of `drawer`. The drawer opens with its search focused and the
  on-screen keyboard down.
  - Typing filters the grid. The first match carries the hover outline.
  - Enter launches the first match.
  - Esc clears the query; Esc on an empty query closes the drawer.
  - A tap on the field still raises the on-screen keyboard, as now.
- **The overview has keys.** While the card deck is up, however it was
  entered, Sway is in an `overview` binding mode:
  - Left and Right (with or without Fn) choose a card; LILYGO+Tab steps on.
  - Enter opens the chosen card; Esc goes back; Backspace or Delete closes it.

  The compositor leaves the mode whenever the deck closes, so these plain
  keys reach apps again.

## Capabilities

### Modified Capabilities

- `runtime/shell`: "Shell navigation works from the base's keys" gains the
  drawer's key behaviour and the overview's keys.

## Impact

- `nix/rust-shell-client/src/service_ui.rs` (`DrawerSearch::key_action`),
  `src/main.rs` (the `drawer-keys` line, keyboard grab without the on-screen
  keyboard), `src/render.rs` (first-match outline).
- `nix/card-shell/adapter.c` (`overview_key_mode`) and `nix/shell.nix` (the
  binding and the `overview` mode).
