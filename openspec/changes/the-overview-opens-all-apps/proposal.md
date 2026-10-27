## Why

webOS's card view always offered a way to every app, not only to the ones
already running. Our overview shows open cards, a "Home · tap or swipe up"
footer, and nothing else: a person who opens the overview to start
something new has to go Home and then swipe up again. The shell UX review
(`docs/design/shell-ux-review-webos-firefoxos-2026-10.md`, gap 8) ranks
this as a missing entry point.

## What Changes

- The overview's title row gains an **All apps ›** label at its right,
  aligned to the right margin.
- A tap there settles Home and then opens the app drawer.
- The target is at least 99 px tall and never overlaps a card: it is tested
  only on backdrop taps, the same taps that otherwise go Home.

## Non-goals

- No change to the deck, the cards or the footer.
- No new key; LILYGO already opens the drawer from anywhere.

## Capabilities

### Modified Capabilities

- `runtime/card-shell`: the overview offers an entry to All apps.

## Impact

- `nix/card-shell/adapter.c` (`overview_apps_hit`, `overview_open_apps`, the
  label in `rebuild_chrome`, the backdrop tap paths, and the deferred drawer
  request at the end of the Home settle).
