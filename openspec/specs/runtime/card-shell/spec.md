# runtime/card-shell Specification

## Purpose
The card shell decides which mapped application windows become ordinary,
switchable, closable cards in the touch-first overview deck, and how each
card's small deck thumbnail stays live without paying unbounded
recomposition cost. This capability's requirements describe that
eligibility, close-signaling and thumbnail-cost behavior as observed in
`nix/card-shell/adapter.c` and `nix/shell.nix`, independent of which
concrete application is running.

## Requirements

### Requirement: The card overview shows a webOS-style fan of 2-3 cards, each with a real icon and app name

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/coherent.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

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
an "ordinary maximized" app-window fixture matching production). The later operator accepts coherent shell behavior and waives additional
recordings; see docs/evidence/proposal-closeout/2026-10-01/coherent.md. No newly measured legibility or latency trial
is claimed by that acceptance. -->

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

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/coherent.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

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

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/coherent.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

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

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/coherent.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: Card eligibility, close, and deck-preview cost do not vary by app identity

The card shell SHALL decide whether a window becomes an ordinary,
closable card, how closing it is signaled, and how its deck thumbnail is
kept live, without inspecting the window's app_id or otherwise
special-casing any particular application. A window that reports a
fixed, non-resizable size (as mpv's `--geometry=WxH` does) MUST NOT be
excluded from ordinary-card treatment on that basis alone; only a real
transient/popup (a toplevel with a parent set) is excluded. Closing any
card SHALL send only the window's ordinary close request; the compositor
MUST NOT spawn an app-specific helper process as part of closing a card.

*Grounding: `nix/card-shell/adapter.c`'s `ordinary` command handler and
`cmd_card_shell`'s `CS_CLOSE` handling (source read); this generalizes
and replaces the app_id-keyed behavior proposed in
`video-windows-become-ordinary-cards` (its task 2.1
`card_shell_video_stop`/`SWAY_K230_CARD_VIDEO_STOP` hook is removed by
this change). Physical-board injected close/live-preview proof: `docs/evidence/card-shell/live-card-cost/README.md`. Real-finger functional acceptance: `docs/evidence/proposal-closeout/2026-10-01/ordinary-cards.md`.*

#### Scenario: A fixed-size window becomes an ordinary card like any other

- **WHEN** an application window reports a fixed (non-resizable) size and
  has no toplevel parent
- **THEN** it receives the same ordinary-maximized, switchable, closable
  card treatment as any other application window, regardless of its
  app_id

#### Scenario: Closing a card sends only the ordinary close request

- **WHEN** a user closes any card (video or otherwise) by the swipe-up
  gesture or the persistent Close control
- **THEN** the compositor sends that window's ordinary close request and
  nothing else app-specific; whether the underlying process exits, and
  whether it relaunches anything, is entirely that application's own
  concern

### Requirement: Every card's small deck thumbnail stays live at a bounded cost

A card not currently shown at full panel size SHALL continue reflecting
its source's real, current content -- never a frame frozen indefinitely
-- while bounding the compositing cost of doing so, for every
application equally. The card shell MAY refresh such a thumbnail at a
capped rate (about 15 times per second) instead of on every single
client commit, and MAY use a cheaper resampling filter while the
overview is actively animating or being dragged, reverting to the
higher-quality filter once settled. A card currently shown at full panel
size (focused full-screen, mid-entry, or expanded) MUST always reflect
its most recent content with no rate cap.

*Grounding: `nix/card-shell/adapter.c`'s `scaled_mirror` (source read);
this generalizes and replaces the video-only frozen-thumbnail behavior
proposed in `video-windows-become-ordinary-cards` (its task 3.1). Physical-board injected live-preview proof: `docs/evidence/card-shell/live-card-cost/README.md`; operator functional acceptance: `docs/evidence/proposal-closeout/2026-10-01/ordinary-cards.md`. Quantitative entry and acknowledgement targets remain UNVERIFIED and are retained in `the-shell-profiles-reported-interaction-jank` task 4.1.*

#### Scenario: A busy non-video card's thumbnail never freezes

- **WHEN** a card whose application commits frequently (a game, a busy
  scrolling terminal, or a playing video) sits in the deck as a small,
  unselected thumbnail
- **THEN** the thumbnail keeps showing real, recent content -- capped to
  about 15 refreshes per second, never frozen on a single stale frame

#### Scenario: The overview stays responsive with a fast-committing card present

- **WHEN** the overview is entered, browsed, or exited while a
  frequently-committing card (video or otherwise) is present
- **THEN** the entry animation and touch handling proceed at essentially
  the same speed as with no such card present, rather than being
  dominated by that one card's recomposition cost

### Requirement: Card entry and recovery do not depend on the launcher

*Grounding: `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md` records functional operator acceptance, supplemented by injected-board proof in `docs/evidence/card-shell/injected/README.md`. No new camera or per-case physical trial is claimed.*
The card shell SHALL be enterable from an arbitrary eligible running
application through a dedicated edge gesture. It SHALL also provide a
persistent button route for entry or recovery, without requiring the Apps
launcher to be open. While the card shell is active, dismissed, unavailable,
or recovering from a close request, Apps, Windows/Home, Keyboard, System,
Help, terminal, monitor, and Back SHALL remain usable through their existing
shell routes.

#### Scenario: A person enters cards from a running application

- **WHEN** an eligible application is active and a person performs the card
  entry edge gesture
- **THEN** the card shell opens without first opening Apps or the launcher

#### Scenario: Gesture entry is unavailable

- **WHEN** card entry cannot proceed or a person chooses the persistent button
- **THEN** the person can enter or recover from the card shell through the
  persistent route and retain the existing shell controls

### Requirement: A person can manipulate a live application card deck

*Grounding: `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md` records functional operator acceptance, supplemented by injected-board proof in `docs/evidence/card-shell/injected/README.md`. No new camera or per-case physical trial is claimed.*
The card shell SHALL present eligible running applications as live visual cards,
not title-only substitutes. Entering the card shell SHALL shrink the active
application into a card, keep a horizontal deck of eligible cards, move the
selected card with a single finger, and expand the tapped card back to the
active application.

#### Scenario: A person resumes another running application

- **WHEN** the card shell contains two eligible running applications and a
  person drags to and taps one card
- **THEN** that application's live card is visible during selection and the
  application expands to become active

### Requirement: The card shell handles unavailable and private content safely

<!-- UNVERIFIED: Injected-touch board evidence: docs/evidence/card-shell/injected/README.md (private/unavailable card state and recovery). UNVERIFIED: a separate per-case real-finger privacy trial; functional operator acceptance does not invent it. -->
The card shell SHALL identify an application whose live surface is unavailable,
protected, or excluded by the session privacy policy without exposing its
content. It SHALL provide a clear non-live card state and a route back to the
existing Apps or Windows/Home controls.

#### Scenario: A live surface cannot be presented

- **WHEN** an application is not eligible for live card presentation
- **THEN** the person sees a non-live state rather than stale, unrelated, or
  private pixels and can leave the card shell through an existing control

### Requirement: An upward throw requests a recoverable close

<!-- UNVERIFIED: Injected-touch board evidence: docs/evidence/card-shell/injected/README.md and docs/evidence/card-shell/throw-sampling/README.md (close refusal and timeout recovery). A later repeat missed one upward throw (docs/evidence/card-shell/repaint-stages/README.md). UNVERIFIED: quantified real-finger throw reliability; functional operator acceptance does not erase the historical failed trials. -->
The card shell SHALL treat an intentional upward throw of an eligible card as a
request for that application to close gracefully. If the application refuses,
times out, or fails to close, the shell SHALL retain or restore a usable card
and make an existing recovery route available; it SHALL NOT silently discard
application state.

#### Scenario: An application refuses to close

- **WHEN** a person throws a card upward and the application remains running
- **THEN** the card shell reports the unsuccessful close without losing the
  card or the Apps and Windows/Home recovery routes

### Requirement: Card interaction has an explicit measured budget decision

<!-- UNVERIFIED: Board measurements are recorded and FAIL the declared CPU and tracking budgets: docs/evidence/card-shell/board-cost/long-trace/README.md through docs/evidence/card-shell/scaled-cache-board/README.md. UNVERIFIED: budget acceptance, now owned by the explicitly authorized the-card-deck-still-misses-its-frame-budget successor; see docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md. -->
The card shell SHALL record input-to-visible-update latency, frame/update cost,
and incremental memory use at the panel's native portrait mode on the default
Pixman path. If a declared interaction budget is missed, the implementation
SHALL record the result. A reduced-refresh or optimized path is acceptable only
when it still preserves live visual cards, finger-following, deck selection,
tap-to-expand, and recoverable throw-close. If it cannot, the change SHALL
remain open or move to an explicitly authorized successor; it SHALL NOT be
archived as accepted card-shell behavior.

#### Scenario: A card workload misses its declared budget

- **WHEN** a measured card interaction exceeds its declared frame, input, or
  memory budget
- **THEN** the evidence records the workload and measured result, and any
  accepted mitigation retains every required core card interaction; otherwise
  the work remains open or moves to an explicitly authorized successor
