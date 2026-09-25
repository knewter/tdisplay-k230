## ADDED Requirements

### Requirement: The card overview shows a webOS-style fan of 2-3 cards, each with a real icon and app name

<!-- Superseded 2026-09-25 (twice): the user was shown both the
originally-planned "widen the existing single-card peek" and a richer
multi-card option (docs/design/shell-ux-critique-switcher.svg) and chose
the richer direction, on the condition that it stay the same CS_DECK mode
and gestures, not a second, separately-entered destination. A first pass
sized cards at ~46% of the panel width with a ~56% (of the leftover band)
height, which board review found too small (~45% of the panel's own
height, sitting flush under the title with about half the panel empty
below). Revised per that review to ~50% of the panel width and 60% of its
height (55-65% requested), vertically centered between the title and the
"Swipe up for apps" hint (cs_config's new card_top_offset, replacing a
fixed inset there -- inset itself, and cs_entry_target_rect which still
uses it, are unchanged). The direct-switch entry gesture's own geometry
stays decoupled via entry_card_width/entry_card_height +
cs_entry_target_rect, now also protected by a new entry_anchor_shift_y
term covering the y-offset (not just the height) mismatch between the
overview's card rect and the entry target -- see the "direct app switch
keeps its geometry independent of the overview's card size" requirement
below. Icon/name resolution is nix/card-shell/adapter.c's
desktop_identity_icon (extends the existing desktop_identity_name/
.desktop-parsing infra to also read Icon=) plus nix/card-shell/icon.c,
which resolves both PNG (Cairo) and SVG (librsvg, linked directly, no
gio/gdk-pixbuf) representations -- a board report with two real apps found
a letter badge instead of a real icon under the real installed theme,
traced to SVG-only resolution paths PNG-only decoding missed; icon.c also
now follows the active theme's own icon_theme (report.json, via
appearance_apply), not just K230_ICON_THEME. Evidence:
docs/evidence/card-shell/webos-fan-switcher/ (headless-QEMU, dark+light,
real resolved icons/names including an SVG-only one, scroll/close/open,
an "ordinary maximized" app-window fixture matching production). Real-
board/on-glass legibility remains UNVERIFIED beyond the two-real-app board
report already folded in above; no board access was used for this pass. -->

While the card overview (`CS_DECK` mode) is settled and not being dragged,
the compositor SHALL lay out its cards as a horizontal, center-selected row
sized so that 2-3 cards are visible at once on the real panel: a center card
roughly half the panel's width and 55-65% of its height, vertically
centered in the space between the title and the "Swipe up for apps" hint
(not sitting flush under the title), with a gap tight enough that each
visible neighbor's icon and part of its name are identifiable without
paging to it, matching the user's chosen webOS-fan direction over both the
prior single-card deck and a distinct, separately-entered grid Overview
mode. Each card SHALL carry a header above it containing: the app's icon at
a legible size (32-40 logical px), resolved through the same installed icon
theme the drawer uses (its `.desktop` `Icon=`, in any representation that
theme ships -- PNG or SVG -- never a letter badge when a themed icon
resolves) and following the active theme's own icon-theme selection when it
names one; and the app's name, resolved from its `.desktop` `Name=` (never
the live window title), at a size consistent with the shell's own
typography scale and legible at arm's length, truncated with an ellipsis
rather than overflowing. This requirement governs the idle overview's
static layout and header content; it does not change the two-axis drag/
quick-switch (direct bottom-edge app-switch) gesture's own geometry,
thresholds, or feel, which stays governed by the "direct app switch keeps
its geometry independent of the overview's card size" requirement below and
`the-handheld-presents-a-coherent-shell` design decision 11.

#### Scenario: Two or more apps are open and the person reaches the overview

- **WHEN** a person reaches the settled card overview with at least one
  neighboring card in the deck
- **THEN** 2-3 cards are visible at once, each with a header showing its
  resolved icon and app name, and the neighboring card(s) are identifiable
  at the screen edge without a horizontal drag

#### Scenario: An app's icon does not resolve through the installed theme

- **WHEN** a card's app has no `.desktop` entry, or its entry's `Icon=`
  does not resolve to a themed icon file
- **THEN** that card's header falls back to the existing letter badge
  (derived from the resolved app name, or a neutral glyph), never a blank
  or broken image, and the app's real resolved name (or, if that also
  fails to resolve, the existing safe fallback text) is still shown

#### Scenario: Only one app is open

- **WHEN** exactly one card exists in the deck
- **THEN** the overview shows that card at its existing (fan-sized) width
  with no neighbor peek, unchanged from the single-card case

#### Scenario: The overview is mid-drag

- **WHEN** a person is actively dragging the deck horizontally (the
  existing `cs_motion`/`cs_entry_motion` paths)
- **THEN** the live drag geometry and settle behavior are unchanged by the
  card-sizing part of this requirement; only the released, idle layout's
  card size/peek changes

#### Scenario: A released horizontal drag settles with momentum

<!-- Revised 2026-09-25 after a real-glass report ("i can't flick to swipe
through multiple cards quickly, it snaps to each card as i go"): a fling's
resting card is now projected from the release velocity (a physics coast,
card-shell-policy.c's CS_SCROLL_OMEGA), not limited to the adjacent card,
using the same recency-windowed velocity estimator
(touch_window_span/entry_release_velocity's shared helper) the direct
bottom-edge app switch already uses for its own release velocity -- a
separate scroll_history buffer, not shared state, and the direct-switch
gesture's own numeric behavior is unchanged (see the sibling requirement
below). Verified by
tests/card_shell_policy_driver.c's scroll-fling-multi-card,
scroll-slow-release-snaps-nearest, scroll-catch-mid-coast and
scroll-end-clamp-soft cases. -->

- **WHEN** a person drags the overview row horizontally and releases with a
  decisive flick velocity
- **THEN** the resting card is projected from that release velocity and may
  be several cards away, not limited to the adjacent one, reached by a
  continuous momentum coast (not an instant jump) whose duration scales
  with the distance it travels
- **WHEN** a person drags the overview row horizontally and releases slowly,
  with no measurable flick velocity
- **THEN** the drag settles on whichever card is nearest to the released
  drag distance, the same "distance decides" behavior a fling's velocity
  term reduces to at zero velocity
- **WHEN** a fresh touch lands while a momentum coast is still in progress
- **THEN** it catches the coast at its exact current position (no visual
  jump) and continues tracking the finger 1:1 from there, as an ordinary
  held drag, rather than cancelling to the coast's eventual rest position
- **WHEN** a fling's projected resting position would go past the first or
  last card
- **THEN** the overview clamps to that first/last card, and the coast
  settles with a visibly softer, shorter motion than an equal-velocity
  fling that lands within the deck -- a light give, not a hard stop at
  full magnitude

### Requirement: The direct app switch keeps its geometry independent of the overview's card size

<!-- Grounded in nix/card-shell-policy/card-shell-policy.c (entry_card_width/
entry_card_height, cs_entry_target_rect) and nix/card-shell/adapter.c (both
cs_entry_set_geometry call sites use cs_entry_target_rect, not
cs_card_rect); tests/card_shell_policy_driver.c's two-axis-entry/
two-axis-conflicts/direct-carousel/app-switch-swipe/tracked-entry/
tracked-expansion cases keep their pre-existing numeric assertions
unchanged under the new overview card sizing, which is the proof this
holds. -->

The direct bottom-edge app-switch gesture (swiping sideways along the
bottom edge from inside an app) SHALL keep its existing feel — a 30% of
panel width distance-or-flick threshold, 1:1 finger tracking, and a
full-size neighbor visible mid-switch — regardless of the card overview's
own card size. The policy's entry-gesture geometry (the anchor/travel
computation `cs_entry_set_geometry` establishes, and the vertical/
horizontal finger-tracking correction terms that depend on it) SHALL be
computed from a fixed, near-full-screen target independent of the
overview's `card_width`/`card_height`, so a future change to the overview's
card sizing cannot silently perturb this gesture's thresholds or tracking
accuracy.

#### Scenario: The overview's card size changes

- **WHEN** the overview's card width/height (`card_width`/`card_height` in
  `cs_config`) changes
- **THEN** the direct app-switch gesture's distance-or-flick threshold,
  release-velocity gate, and mid-drag 1:1 tracking (both axes) are
  unaffected, verified by the policy driver's direct-switch test cases
  requiring no assertion-value changes

### Requirement: Settings is not represented as a card in the overview

<!-- Design decision, not a code change: Settings is architecturally a
layer-shell overlay (namespace k230-shell-drawer), never a CS_LIVE toplevel
card, so this requirement documents and tests the existing construction
rather than changing behavior. See design.md's "Settings behaves like an
app without being a card" decision for the full webOS/M3 comparison this
requirement's rationale summarizes. -->

Reaching the card overview from Settings (per this change's bottom-edge
escape requirement above) SHALL dismiss Settings and reveal the overview's
existing cards; Settings itself SHALL NOT appear as a selectable card in the
deck, before or after that dismissal. Settings is reached through the shade,
not launched as a running application, and carries no backgroundable
process or live source a card could represent — unlike webOS's own Settings,
which ran as an ordinary card-switchable application, and unlike Android's
standalone Settings app, which is a real backgroundable Activity with its
own task. Architecturally, this shell's Settings is closer to Android's
Quick Settings panel (attached to, and dismissed with, the notification
shade) than to either of those standalone apps, and Quick Settings is not
represented in Android's recents/overview either. The bottom-edge escape
requirement above already gives Settings the touch-routing behavior a person
expects from "acting like any app" — leaving the overview's cards to
represent only actual running, focusable applications keeps the overview's
existing live-source/focus/privacy contract (owned by the sibling live-card
implementation) unextended to a surface that has none of those properties.

#### Scenario: Settings is dismissed into an unchanged overview

- **WHEN** a person reaches the card overview by swiping up from Settings
- **THEN** the overview shows the same cards it would show had Settings
  never been open, with no additional card representing Settings itself
