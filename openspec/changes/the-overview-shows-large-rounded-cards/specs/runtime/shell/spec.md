## ADDED Requirements

### Requirement: The card overview shows an Android-recents-sized, rounded focused card

The card overview (`CS_DECK`) SHALL render its focused card at approximately
80% of the panel's width and 80% of its height, matching the panel's own
aspect ratio, with each neighbouring card's own edge visible only as a thin
sliver (not a wide multi-card fan). A live card's content SHALL fill the
entire card slot with no visible background, border, or plate behind it —
the card IS the app content, scaled — and its four corners SHALL read as
visibly rounded. The existing webOS-fan gesture behavior — a horizontal
flick that can carry the selection past more than one adjacent card via a
velocity-projected momentum coast, an upward throw past a configured
distance/speed that requests a close, and a tap that expands the selected
card to full screen — SHALL be unchanged by this sizing; only the geometry
the same gesture formulas operate on changes.

While a card is entering the deck from a full-screen app, or expanding from
the deck to full screen, its corner radius SHALL interpolate continuously
between 0 (full screen) and its settled deck-card radius, so the transition
does not pop between square and rounded corners; cards not themselves
undergoing that size change SHALL keep their full, constant radius
throughout.

*Grounding: `nix/card-shell-policy/card-shell-policy.c`'s `cs_default_config`
(`card_width=.8*width, card_height=.8*height`) and `nix/card-shell/adapter.c`'s
matching runtime recompute; `CARD_CORNER_RADIUS=26.0` and `card_corners_sync`
(four cached `card_corner_mask_scene` patches painted over the live mirror's
own corners, no plate, no pad) in the same file, gated on `card_shown_large`
so only the actually-morphing card's radius interpolates. Non-live
(private/unavailable) cards keep the pre-existing `card_background` plate,
since they have no live pixels to protect from a background.
`tests/card_shell_policy_driver.c`'s `overview_geometry` case asserts the
75-85% width/height band, a ≤15%-of-card-width neighbour peek, and a fully
off-screen third card; 36/36 cases in `tests/test_card_shell_state.py` pass.
`docs/evidence/card-shell/android-sized-cards/README.md` records a
headless-QEMU capture of the resulting overview, scroll, close, and open
sequence in both themes, compared directly against the prior 50%/60%
webOS-fan capture, confirming no visible background/border behind a live
card. Real-finger board acceptance of the gesture feel and the radius
transition's smoothness is UNVERIFIED and tracked as this change's open
board task.*

#### Scenario: The overview is entered with more than one card open

- **WHEN** a person enters the overview with two or more cards open
- **THEN** the focused card fills roughly 80% of the panel on both axes,
  keeps the panel's own aspect ratio, shows visibly rounded corners with no
  background or border behind the live content, and each neighbouring card
  is visible only as a thin edge sliver

#### Scenario: A person flicks through the deck

- **WHEN** a person performs a fast horizontal flick starting on the focused
  card
- **THEN** the selection can land more than one card away from the start,
  the settled card is exactly centered once the momentum coast finishes,
  and the same release-velocity formula governs this regardless of the
  focused card's size

#### Scenario: A card opens or closes

- **WHEN** a person taps a card to expand it to full screen, or a
  full-screen app enters the deck as a new card
- **THEN** that card's corner radius interpolates continuously from 0 to
  its settled deck-card value (or the reverse) across the transition, with
  no visible pop between square and rounded corners, while every other
  card in the deck keeps its full, constant radius throughout
