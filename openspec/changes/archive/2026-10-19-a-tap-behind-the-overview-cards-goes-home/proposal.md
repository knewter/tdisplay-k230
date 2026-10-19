## Why

In the card Overview, only the footer ("Home · tap or swipe up") or an
upward swipe from it takes a person Home. A tap on the backdrop around a
card — above it, beside it, or in the title band — does nothing; the
touch is swallowed until it lifts. On glass the operator expected any tap
behind the card to go Home (2026-10-19: "on overview tapping anywhere
behind the card should go home not just the bottom area").

## What Changes

- A tap (released within the tap slop) on the Overview backdrop that is
  not on a card, a Close button or the footer goes Home, the same way the
  footer tap does: Home slides in and every app stays open in Overview.
- A contact that starts on the backdrop and then moves, or that is joined
  by a second contact, still does nothing.
- Taps on a card, the footer gestures and the Close button are unchanged.

## Non-goals

- No new drag or scroll gesture from the backdrop; dragging the deck still
  starts on a card.
- No change to how Home is shown, nor to Overview's look.

## Hardware

The policy change is proved by the host policy driver
(`tests/card_shell_policy_driver.c`). The behaviour on glass needs the
board: an injected tap on the backdrop with a `grim` capture before and
after, then the operator's own tap.
