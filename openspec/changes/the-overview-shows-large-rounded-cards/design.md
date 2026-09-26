## Context

Layer: userspace, the C compositor's card policy
(`nix/card-shell-policy/card-shell-policy.c`) and its adapter/renderer
(`nix/card-shell/adapter.c`, `nix/card-shell/render.c`). No device tree,
kernel, or Nix packaging change.

`the-shell-behaves-as-one-coherent-system`'s `design.md` decision 1 already
records one revision of this same number (an original small pass, then a
50%/60% webOS-fan pass "after board/real-glass review"). This change is a
second, operator-directed revision of the same decision, not a new decision
axis — recorded here rather than by editing that other change's still-open
`design.md`, since that document belongs to a different in-flight change and
this repo's worktree discipline says not to edit another change's files.

## Decisions

**1. Card size: 80% of panel width AND 80% of panel height, not independent
fractions.** The prior pass used two different fractions (50% width, 60%
height) picked to fit a specific vertical budget, which left the card's own
aspect ratio not matching the panel's. Using the *same* fraction on both
axes guarantees `card_width/card_height == width/height` exactly — the card
is phone-shaped by construction, not by a second, separately-tuned number.
80% sits at the low end of the operator's own "roughly 80-85%" framing,
chosen to leave enough vertical budget for the header (icon + app name,
44px + 14px gap) and the existing 56px footer/hint band without needing to
shrink either past this repo's own minimums (`footer_height>=56`); see
`card-shell-policy.c`'s `valid_config`.

**2. Reduce `title_height` from 100 to 70, not the footer or inset.** The
80%-height card needs slightly more vertical budget than the 100px title bar
left available. `footer_height` and `inset` already sit at this repo's
declared minimums (56 and 24); `title_height`'s own minimum is lower (56),
and the title bar's only content (a short "Home"/app-name string plus a
status cue) does not need 100px to read comfortably. This is also a small,
independent win in the same direction as
`docs/design/shell-polish-review-2026-09.md`'s dead-space findings, though
it is not itself one of that document's numbered findings.

**3. No plate, no pad, for live cards — a coordinator correction after
review.** The first pass of this change kept the existing content plate
(a themed, filled, stroked rounded rect drawn *behind* the live mirror,
inset from the card slot by a 32px pad so its rounded corner would peek
out around the square content). Reviewing the resulting screenshots, the
coordinator identified that this reintroduced exactly what the operator
had separately, explicitly rejected: "when i swipe up to see active
windows the cards have some background behind them that's no good they
should just be cards." A 32px pad with a themed fill is a visible
background/border, regardless of how small the number sounds. **Live
cards now have no plate at all.** The mirrored content fills the entire
card slot (`sync_card`'s box computation drops the pad term entirely —
`box_x/box_y/box_width/box_height` are now exactly the content's own
aspect-fit rect, full stop), which also directly satisfies the "use the
space" ask: content now genuinely reaches ~80% of the panel width, where
the padded version only reached ~69% (`card_width - 2*32px`).
Non-live placeholder cards (private/unavailable content, which has no
live pixels of its own to round) are the one remaining user of a plate
(`card_background`/`card_plate_scene`), unchanged in kind, since there is
nothing else to draw for those and no live content to protect from a
background.

**4. Rounding a live card: four small corner-mask patches painted OVER the
content, not a mask/clip underneath it.** With no plate, the live mirror's
own four corners are square. `card_corner_mask_scene` (`render.c`) paints
a small (`radius`×`radius`) patch per corner, in the deck's own backdrop
colour, opaque everywhere except within a quarter-circle arc curving
toward the card's centre — placed on top of the mirrored content
(`wlr_scene_node_place_above`, the inverse of the old plate's
`place_below`). Visually this "erases" the content's true square corner
back to whatever colour is already behind the card, reading as a rounded
corner without touching the mirrored pixels, clipping the whole card, or
drawing a frame around it. Each card caches its own four patches
(`struct card`'s new `corner[4]`/`corner_radius_px`/`corner_color` fields)
and only rebuilds them when its own quantised (whole-pixel) radius or the
canvas's colour changes — the same "compare, then rebuild only if
changed" discipline `card_background` already used for the plate, just
keyed on a much smaller (4×26×26px, ~10.8KB total) raster instead of one
card-sized one. In steady state (every card not currently morphing) nothing
rebuilds at all, ever; only the one or two cards actually growing/shrinking
between full screen and deck size pay any Cairo cost, and only for as long
as their own radius keeps changing.

*Rejected within this corner-mask design:* rotating one shared cached
raster via `wlr_scene_buffer_set_transform` to serve all four corners of
every card from a single buffer, cutting the raster count from "up to 4
per card" to "up to 4 total, ever." This is very likely also correct and
cheaper, but the transform math for a *decorative* (non-output-related)
buffer is unfamiliar territory for wlroots' scene API in this codebase,
and it cannot be verified without a board or a much deeper wlroots read
than this change's time budget allows; a demonstrably-correct, slightly
less-shared per-card cache was chosen over a plausibly-more-clever one
that could not be verified here. Left as a documented, easy follow-up
optimisation, not attempted.

**5. Radius interpolation only for the card(s) actually changing size, not
every card in the deck.** `sync_card`'s `entering` flag is mode-wide (true
for every card, including ordinary stationary neighbours, for the whole
duration of any app-switch gesture), but only the dragged card (and its
`full_clip` companion during a shared full-frame entry) or the tap-expanded
card actually grow/shrink between full-screen and deck size —
`card_shown_large(c)`, already defined in this file for exactly this
distinction, is reused to gate the interpolation. A card for which
`card_shown_large` is false always uses the full `CARD_CORNER_RADIUS`
(steady, cheap, cache hits every frame); a card for which it is true gets
`CARD_CORNER_RADIUS * entry_progress` (entering) or
`CARD_CORNER_RADIUS * (1 - expand_progress)` (expanding), 0 at full screen
rising to the full radius once settled. **This corrects a latent gap in
this change's own first pass:** that pass computed an equivalent
interpolated value but fed it to a plate that was unconditionally hidden
for the *entire* duration of any entering/expanding transition (the
pre-existing `hidden = entering || expanding` gate on the old
`card_background` call), so the interpolation, while present in the code,
was never actually visible in any capture. Corner masks are not hidden
during the transition — they are the only rounding a live card has, and
the whole point is to see the radius grow in as the card grows into the
deck — so this version of the interpolation is the first one that is
actually observable.

**6. The direct-switch (bottom-edge) entry gesture's own target rect
(`entry_card_width`/`entry_card_height`) is untouched.** This repo already
decoupled that gesture's anchor/travel geometry from the overview's own
card size for exactly this reason (a design goal from the prior pass,
restated in `card-shell-policy.h`'s field comments); this change keeps that
decoupling and does not touch `cs_entry_target_rect`.

**7. Test fixtures that hardcoded absolute pixel drag distances are
rewritten as fractions of the pitch (`card_width + gap`), not scaled by a
one-off constant.** Several existing `card_shell_policy_driver.c` cases
(`horizontal`, `scroll_catch_mid_coast`, `stream_cancel`,
`stream_cancel_multitouch`) used a fixed `180`px drag to exercise "drag well
past half a card and commit to the next one." With the pitch now ~58%
wider, that same absolute distance no longer crosses half the new, wider
pitch — not a regression in the gesture's *formula* (unchanged), but a
fixture tuned to the old geometry. Rewriting these as `pitch * .6` (a
fraction already used elsewhere in the same file, e.g.
`scroll_slow_release_snaps_nearest`) keeps the same *relative* intent ("a
firm drag past half a card") and makes the fixture correct for any future
card-size revision, not just this one. `scroll_fling_multi_card` and
`scroll_end_clamp_soft` needed their *velocity* samples recalibrated for
the same reason (a fixed flick speed now projects proportionally less
distance across the wider pitch); their fixed dx-clamp-based reach
(`scroll_end_clamp_soft`'s "land on the last card" case) was rewritten as a
two-sample flick, since a single drag's raw position is capped at `2 *
width` regardless of pitch and can no longer alone reach the last card of a
4-card deck at this wider pitch — this is a real, if narrow, structural
note: a single **drag** (no velocity) genuinely cannot span an arbitrarily
wide deck in one gesture on this panel; a **flick** (drag + velocity)
always can, because the velocity term is not subject to that same
position-space cap. No production code enforces or needs a "reach the far
end via drag alone" guarantee; only this test assumed it.

## Rejected alternatives

- **A per-frame per-pixel rounded-rect mask (e.g. redrawing/re-clipping the
  live mirror content itself every frame).** Rejected: the existing plate
  mechanism already renders the rounded rect once per unique
  (brush, size, radius) into a cached `wlr_scene_buffer`, reused unchanged
  across ordinary frames; a per-pixel mask would cost strictly more for no
  visual benefit, and the hardware constraint (one slow RISC-V core, no
  extra full-screen passes) rules it out directly.
- **A separate `card_radius` field on `cs_config`.** Rejected: radius is a
  rendering-only concern, matching this codebase's existing separation of
  policy (geometry, gesture math) from rendering (colours, radii, fonts) —
  `card-shell-policy.h`'s own header comment states this policy struct
  "never stores... " rendering concerns. Keeping `CARD_PLATE_RADIUS` in
  `adapter.c` alongside `CARD_PLATE_PAD` preserves that boundary.
- **Keeping the neighbour peek at its prior ~46%-of-card-width fraction.**
  Rejected: at 80% card width there is only ~14% of the panel left for both
  neighbours combined (7% each side before the gap), so a peek anywhere
  near the old fraction is geometrically impossible without shrinking the
  card back down — which is the change being reverted. The resulting ~10%
  peek is deliberately thin, matching Android recents' own edge-sliver
  convention rather than the webOS multi-card-fan convention the prior pass
  chose.

## Migration / rollout

No data migration. The change is a set of policy/rendering constants plus
their propagation through the one runtime recompute site
(`adapter.c`'s `card_shell_prepare`-adjacent config block) that already
existed for the prior revision. No feature flag: the overview always uses
the new size once this change lands, matching how the prior 50%/60% pass
also had no flag.

## Open questions

- Whether 80% (the low end of the operator's "80-85%" framing) or a value
  closer to 85% reads better once seen on real glass is a real-finger
  question, not a formula question — left to the board task in `tasks.md`.
- Whether `title_height`'s reduction from 100 to 70 needs any Rust-side
  companion change (the Rust overlay client renders its own, separate
  Settings/Drawer/Shade chrome and is not affected by this C-side constant,
  confirmed by grep: `title_height` is a `cs_config` field, never read by
  `nix/rust-shell-client/src/*.rs`) — not expected, not verified further
  here.
