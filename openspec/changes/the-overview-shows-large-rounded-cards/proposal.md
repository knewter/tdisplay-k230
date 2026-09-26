## Why

The operator asked directly: "have a design agent review our whole shell
setup and make it polished af also i think the cards should have a border
radius and fill a lot of the screen not be tiny idk more like android
does." `docs/design/shell-polish-review-2026-09.md` (this change's
companion review) covers the whole shell; this change implements the one
piece of that ask the operator stated as an explicit, concrete requirement
rather than a general "make it nicer": the card overview.

Before this change, the overview's focused card (`cs_default_config`,
`nix/card-shell-policy/card-shell-policy.c`) was 50% of the panel's width
and 60% of its height, with an 8px corner radius on its content plate
(`CARD_PLATE_RADIUS`, `nix/card-shell/adapter.c`) — a webOS-style "fan" of
2-3 small cards, chosen and recorded in the still-open
`the-shell-behaves-as-one-coherent-system` change's `design.md` decision 1
after an earlier round of board/real-glass feedback. That decision is not
wrong on its own terms, but it is not what the operator is asking for now:
Android's recents carousel shows one focused, near-full-panel,
phone-aspect-ratio card with only a thin sliver of neighbours peeking at
the edges, and a visibly rounded corner radius proportional to that larger
card.

## What Changes

- The overview's focused card grows from 50%/60% of the panel to 80%/80%
  (matching the panel's own aspect ratio, so the card is phone-shaped, not
  a mismatched rectangle), with the neighbour peek shrinking from ~46% of a
  card's width to ~10% — Android-recents proportions, not a webOS fan.
- **Live cards drop their content plate and pad entirely.** A first pass of
  this change kept the existing plate (a themed, filled, stroked rounded
  rect behind the mirrored content, inset by a pad so its rounded corner
  showed around the square content) and only raised its radius/pad. The
  coordinator, reviewing that pass's screenshots, identified that this
  reintroduced a visible background/border behind live cards — exactly what
  the operator had separately, explicitly rejected ("the cards have some
  background behind them that's no good they should just be cards"). Live
  cards now have **no plate**: the mirrored content fills the entire card
  slot, and rounding is achieved by four small corner-mask patches painted
  *over* the content's own square corners, in the deck's backdrop colour,
  cheap enough to cache per card and rebuild only when a card's own radius
  or the canvas colour changes. Non-live placeholder cards (private/
  unavailable, no live pixels of their own) keep a plate, since there is
  nothing else to draw for them.
- The corner radius (26px, up from the prior pass's 8px, sized for the new,
  much larger card) still interpolates from 0 at full screen to 26px in the
  settled deck, but now only for the card(s) actually changing size
  (gated on the existing `card_shown_large` predicate) — the first pass
  computed this interpolation but fed it to a plate that was hidden for the
  whole transition, so it was never actually visible; this pass's version
  is the first one a capture can actually show.
- The existing webOS-fan interaction — flick through multiple cards via a
  velocity-projected coast, flick up to close, tap to open — is preserved
  exactly (same formulas, same code paths); only the pitch (card width plus
  gap) that those formulas operate on has grown, which the updated policy
  test suite accounts for explicitly (see `tasks.md`).

## Non-goals

- This does not implement the rest of `docs/design/shell-polish-review-2026-09.md`'s
  findings (shade quick-toggle tiles, Settings pressed-state feedback,
  velocity-aware expand/collapse easing, the touch-target physical-size
  gap). Those are recorded in that review as quick wins, medium, or
  structural work for separate changes.
- This does not reopen or amend `the-shell-behaves-as-one-coherent-system`'s
  own open slices (B, C) or its `design.md` decision 1 record of the prior
  webOS-fan choice; it supersedes that one number (card size), the same way
  that change's own decision 1 already superseded an earlier, smaller pass,
  and says so in both files.
- This does not touch the Rust overlay client (Drawer/Shade/Settings). The
  operator's card-size/radius ask is specifically about the C compositor's
  card deck.

## Impact

- Affected capability: `runtime/shell` (the Sway/Pixman handheld session;
  see `openspec/specs/runtime/shell/spec.md` — no existing requirement
  there specifies overview card proportions or corner radius, so this adds
  one rather than modifying the stale, generation-1 "metadata-only window
  overview" requirement already in that file, which describes a different,
  no-longer-shipped launcher mode).
- Affected code: `nix/card-shell-policy/card-shell-policy.{c,h}`,
  `nix/card-shell/adapter.c`, `nix/card-shell/render.{c,h}`,
  `tests/card_shell_policy_driver.c`.
- Evidence: `docs/evidence/card-shell/android-sized-cards/` (headless-QEMU
  before/after screenshots).
- Board/real-finger acceptance of the new card size and the radius
  transition's felt smoothness remains open (see `tasks.md`); this proposal
  claims host-build and headless-QEMU evidence only.
