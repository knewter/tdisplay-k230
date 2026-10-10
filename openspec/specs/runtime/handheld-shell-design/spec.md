# runtime/handheld-shell-design Specification

## Purpose
Define coherent navigation between the card overview and transient shell
surfaces, including uniform bottom-edge escape and overlay dismissal.

## Requirements

### Requirement: A bottom-edge gesture reaches the overview from any transient surface

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/coherent.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounded: nix/card-shell/adapter.c input_down (the drawer_mapped()
bottom-edge carve-out), nix/card-shell/route.c card_shell_launch_surface's
"hide" surface, nix/rust-shell-client/src/lib.rs Route::Hide (pre-existing).
Host command: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml
--locked`. QEMU injected-touch command:
`python3 tests/test_rust_overlay_bottom_escape_runtime.py --sway <sway>
--rust <k230-shell-rust> --client <card-composition-probe-client> --output
<dir>`; see docs/evidence/coherent-shell/overlay-bottom-escape-qemu/. -->

`docs/design/shell-ux-critique.md` S1.1 found the exact cause of "swiping up
from the bottom of Settings does nothing": `nix/card-shell/adapter.c`'s
`input_down` ceded every touch to a mapped Drawer/Shade/Settings layer-shell
overlay (`drawer_mapped()`) before the compositor's own bottom-edge
recognizer (`cs_begin_entry`/`cs_edge_down`) ever ran, regardless of where on
the screen the touch started. This requirement is this change's fix for that
finding, and for `the-handheld-presents-a-coherent-shell`'s own "Home is the
live card deck" requirement's "from an app or transient surface" clause,
which this same defect left unimplemented for every transient surface.

While the Drawer, Shade, Settings, or any Settings sub-page (theme chooser,
Wi-Fi, password entry) is mapped, a touch that begins within the same
qualified bottom edge band an ordinary app already honors SHALL be claimed by
the compositor's existing bottom-edge recognizer instead of being forwarded
to the overlay, using the same thresholds and feel as from an app: a purely
upward release SHALL reach the card overview, and a qualified sideways
release (directly, or continued from an upward start without lifting) SHALL
switch directly to the adjacent running app, per `the-handheld-presents-a-
coherent-shell` design decision 11/12's already-approved two-axis mechanics,
which this requirement reuses unchanged. The overlay SHALL be dismissed as
part of claiming the gesture, so the person is never left with the overlay
still covering the destination it just navigated to. A touch that begins
outside that qualified band — including the overlay's own top-area controls
— SHALL continue to reach the overlay exactly as before.

Because this claims the gesture at the compositor's touch-routing layer
rather than inside the overlay's own page/route state, it applies uniformly
regardless of which Settings sub-page is showing, closing
`shell-ux-critique.md` S2's "dead ends three levels deep" finding (Shade →
Settings → Wi-Fi → password entry) without a separate per-page fix: the
bottom edge reaches the overview from any depth.

#### Scenario: Swipe up from Settings over a running app

- **WHEN** a person swipes up from the bottom edge while Settings (including
  a sub-page such as the theme chooser or Wi-Fi) is open over a running app
- **THEN** the app shrinks into the card overview exactly as an unmediated
  swipe up from that app would, and Settings is no longer covering the
  screen

#### Scenario: Swipe sideways from an overlay switches apps

- **WHEN** a person performs a qualified bottom-edge sideways swipe (direct,
  or curved from an upward start) while the Drawer, Shade, or Settings is
  mapped and two or more apps are running
- **THEN** the adjacent running app is focused and visibly raised, the same
  as the equivalent gesture performed directly on an app

#### Scenario: A deep sub-page still escapes to the overview

- **WHEN** a person has navigated from the shade into Settings and from
  there into a Wi-Fi network's password entry field
- **THEN** the same bottom-edge swipe up reaches the card overview in one
  gesture, without first backing out of the password entry and Wi-Fi list a
  level at a time

#### Scenario: A tap on the overlay's own controls is unaffected

- **WHEN** a person taps a control that is not within the qualified bottom
  edge band, such as Settings' own top-area Close control
- **THEN** the overlay's own touch handling receives the tap exactly as
  before, and no card-entry gesture is claimed by the compositor

### Requirement: Overlay dismiss gestures share one direction

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/coherent.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounded: nix/rust-shell-client/src/service_ui.rs panel_intent
(Route::Shade and Route::Settings arms), OVERLAY_DISMISS_ZONE_Y/
OVERLAY_DISMISS_DY constants. Host command: `cargo test --manifest-path
nix/rust-shell-client/Cargo.toml --locked
service_ui::tests::shade_and_settings_share_one_upward_dismiss_direction`.
Drawer (nix/rust-shell-client/src/navigation.rs) is unchanged; see this
requirement's rationale for why. -->

`docs/design/shell-ux-critique.md` S2 found three overlay surfaces each
recognizing a different, independently hand-tuned local dismiss gesture —
Drawer on a downward drag, Shade on an upward drag, and Settings on a
downward drag despite opening from within the shade's own downward path —
with no single stated rule governing any of them.

Each top-anchored overlay sheet's own local dismiss gesture (distinct from
the bottom-edge escape above, and from a tap on an explicit close control)
SHALL retract the sheet back toward the edge it opened from. Shade and
Settings SHALL therefore share one identical rule: an upward drag starting
near the top of the sheet dismisses it, using the same start-position zone
and displacement threshold for both. The Drawer, which rises from the bottom
edge instead, correctly keeps its own reversed convention — a downward drag
once its content is scrolled to the top sends it back toward the bottom edge
it rose from, an overscroll-to-dismiss idiom that does not conflict with
scrolling the drawer's own content — and is unchanged by this requirement.

#### Scenario: Settings dismisses the same way Shade does

- **WHEN** a person drags upward from near the top of Settings, the same
  gesture that already dismisses the Shade
- **THEN** Settings is dismissed identically; a downward drag in the same
  zone no longer dismisses it

#### Scenario: The Drawer keeps its own bottom-anchored convention

- **WHEN** a person, with the Drawer's content already scrolled to the top,
  drags downward
- **THEN** the Drawer is dismissed back toward the bottom edge it rose from,
  unchanged by this requirement

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/coherent.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->

### Requirement: Shared portrait shell language

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator accepts the installed visual result; no new per-surface physical geometry/contrast matrix was recorded. -->
The shell userspace SHALL use the active appearance generation's authored palette and section brushes, a consistent text hierarchy, spacing system, and touch vocabulary across the deck, drawer, shade, Settings, and notifications at the panel's 568×1232 portrait size. At the current output scale of 1, one logical pixel equals one panel pixel; interactive targets SHALL be at least 56 such pixels tall and later scaling SHALL preserve physical size. Essential information SHALL remain legible without color alone. The final normal session SHALL have no permanently visible Apps/Windows/Keyboard/System rail or Back/Home footer.

#### Scenario: Move between surfaces
- **WHEN** a person moves from a live card to the drawer, shade, and Settings
- **THEN** each surface retains recognizable type, focus, motion direction, and a discoverable gesture cue without permanent navigation buttons

### Requirement: Quiet shell surfaces preserve authored appearance

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: the original panel/theme-picker images ground the polish problem; the user waives further dark/light glass collection, so individual new contrast cases are not claimed. -->
The shell userspace SHALL preserve authored background gradients, alpha, foreground and accent when painting its Home, drawer, shade, Settings and theme picker. Routine app-icon plates, control rows and theme preview frames SHALL avoid unnecessary borders; focus, selection, destructive actions and drag/drop SHALL remain distinguishable. Existing gestures and interactive targets SHALL retain their behavior. The compositor SHALL continue to own live overview/card pixels and movement.

#### Scenario: Change from a dark theme to a light theme
- **WHEN** a person applies a built-in dark appearance and then a built-in light appearance
- **THEN** each shell surface follows the selected appearance without an alternate brand palette or flattening its authored background brush, and retains legible type and deliberate focus/selection cues

#### Scenario: Browse and return to an app
- **WHEN** a person opens the drawer, shade, Settings and theme picker and returns through existing gestures
- **THEN** surfaces share recognizable hierarchy and spacing, and the original navigation and app/card behavior remain available

### Requirement: Overview and pinned Home retain distinct navigation roles

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*

*Grounding: accepted Home navigation in `docs/evidence/home-screen/navigation/operator-acceptance-2026-10-01.md`, exact candidate navigation acceptance and ordinary boot in `docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/README.md`, and the operator’s additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`.*
<!-- UNVERIFIED: no new per-case cancellation, empty-deck or timing recording was collected for this closeout. -->
The shell SHALL keep the live-card Overview separate from pinned Home. A purely upward bottom-edge gesture from an app or transient shell surface SHALL reach Overview with the eligible app shrinking into its live card. An upward gesture from Overview’s bottom navigation area SHALL reveal pinned Home without closing or unmapping running apps. A new upward gesture from Home’s bottom edge SHALL reveal All apps. The same contact SHALL NOT traverse both destinations. Swiping a card itself upward SHALL retain its close action. Empty Overview SHALL retain a useful Home route, and All apps SHALL include named Terminal recovery. Repeating Home SHALL leave pinned Home stable.

#### Scenario: Return from an app
- **WHEN** a person swipes up from the bottom of a running app
- **THEN** the same live app moves into Overview and can be selected again

#### Scenario: Overview reaches pinned Home
- **WHEN** a person swipes upward from Overview’s bottom navigation area
- **THEN** pinned Home appears while the running apps remain available, without that same contact also opening All apps

#### Scenario: Home opens installed apps
- **WHEN** a person begins a new upward gesture from Home’s bottom edge
- **THEN** All apps follows the contact and opens; a short cancelled pull restores the previous scene without launching an app

#### Scenario: Overview has no eligible card
- **WHEN** no eligible app is running and a person reaches Overview
- **THEN** a useful empty state retains the route to pinned Home and All apps, where Terminal remains available

### Requirement: Bottom app switching follows both touch axes

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: two-axis/quick-switch implementation and host/QEMU checks are retained under docs/evidence/coherent-shell/two-axis-qemu/ and docs/evidence/card-shell/app-switch-swipe/; operator accepts the installed result, but no new per-case physical trace or latency measurement is claimed. -->
The compositor SHALL retain one touch owner when an app-entry gesture bends from upward to sideways movement. The manipulated point SHALL follow both finger coordinates one-to-one within declared travel bounds, with no held-contact easing, automatic progress, or axis-change jump. A qualified lateral release SHALL settle and activate the visibly selected adjacent running app directly from the current full or near-full carousel geometry, without a forced overview or second expansion stage; a purely upward release SHALL settle into Overview from its current geometry. A horizontal gesture starting anywhere along the qualified bottom edge band SHALL offer the same adjacent-app switching without requiring an upward gesture or a full card zoom, gated only by measured lateral displacement or release velocity in the swipe direction and not by where along the band the touch started. Release thresholds SHALL NOT amplify visible motion. Short/reversed gestures, and a release whose recent velocity trends back toward the start, SHALL restore the originating app without activating a neighbor. Settling on either axis SHALL begin at the displayed position and bounded measured release velocity, with smooth deceleration or spring and no initial position or derivative jump; velocity SHALL influence motion only after release and SHALL be estimated from recent samples rather than a single possibly-stale last delta. A new accepted touch SHALL stop or retarget settlement from current geometry.

Both routes SHALL use the deck's stable left/right app order, unchanged by focus-only switching, and SHALL commit at most one neighbor per release initially. Dragging the scene right SHALL reveal the left neighbor and vice versa. They SHALL NOT wrap at either end, launch a new app, throw-close an app, or substitute a newly mapped app for a disappearing target. The compositor SHALL preserve the sibling's privacy, source-lifetime, focus eligibility and visible raise behavior. Keyboard-owned regions, active overlays, side Back regions and ordinary app content outside the qualified bottom region SHALL keep their touch ownership.

#### Scenario: Curve upward into a neighboring app
- **WHEN** a person starts an upward app-entry gesture and moves sideways without lifting
- **THEN** the same visible app/card scene follows both axes, reveals its neighbor, and a qualified release expands and visibly focuses that neighbor without another tap

#### Scenario: Quick switch and reverse direction
- **WHEN** a person switches apps with a horizontal bottom-edge swipe and then performs the opposite swipe
- **THEN** the scene follows the finger in each direction and returns to the previous neighboring app in the unchanged deck order

#### Scenario: Hold and cancel a diagonal gesture
- **WHEN** the person holds a diagonal gesture still, then reverses below the commitment threshold before release
- **THEN** the held scene stays still, the return path follows the finger, and release restores the source app without activating or closing another app

#### Scenario: No neighboring app or disappearing target
- **WHEN** a switch points beyond a deck end, only one app exists, or the chosen target exits during the gesture
- **THEN** no wrap, invented preview or unrelated activation occurs; the source app or valid deck remains reachable with correct focus

#### Scenario: An app or keyboard owns the contact
- **WHEN** a touch starts outside the qualified bottom edge band, in a keyboard-owned region, or on an active shell overlay
- **THEN** the quick-switch recognizer does not steal the stream, and changing direction later does not reinterpret it as an app switch

### Requirement: Shade and bottom-edge escape preserve the task

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator acceptance replaces additional shade recordings; no new per-case typing/focus physical trial is claimed.
Narrowed 2026-09-28 (user-authorized scope split, "yes a-d and f"): the
inward-edge contextual Back mechanism and the keyboard/Home edge-ownership
arbitration this requirement used to state are now
`the-shell-gets-side-edge-back-and-motion-trace`'s own "A qualified side
edge dismisses shell surfaces without touching app content" and "One
arbiter owns every touch at down" requirements. This requirement keeps only
the shade-reveal scope this change actually implemented (task group 2). -->
A downward gesture from the top edge SHALL reveal a notification shade over the current scene; the shade SHALL expose notification history and a truthful Settings entry. The bottom-edge app/overlay gesture SHALL remain the escape to Overview while a context is open; its Home route SHALL retain pinned Home and running apps.

#### Scenario: Read a notice while typing
- **WHEN** a person drags the shade down during an app task
- **THEN** the underlying app remains in place, its prior focus is recoverable, and Settings is reachable within the shade

### Requirement: Touch manipulation drives normal navigation

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator accepts the implemented interaction and waives additional captures; no new physical long-press/conflict matrix or one-to-one displacement measurement is claimed. -->
The shell userspace SHALL follow one accepted finger during a deck drag, drawer/Settings/history scroll, or eligible section swipe. During an accepted drag, the manipulated edge or grabbed point SHALL move one logical pixel per logical pixel of finger movement within its travel bounds, including immediate reversal; a stationary held finger SHALL produce no continued movement. Recognition and release thresholds SHALL NOT multiply visible displacement. Easing, inertia, and automatic settling SHALL begin only after release or cancellation. A release SHALL resolve from the displayed position with bounded momentum and a visible settled destination; a new touch SHALL stop coasting. Tapping a card or app SHALL activate it. A deliberate long press SHALL show a context cue before an action, allow movement away or cancellation without activation, and never masquerade as a tap. All apps SHALL provide a Help target with gesture guidance and a deliberately opened Navigation buttons aid for Home, All apps, Notifications and Settings. The large labeled controls SHALL appear only while that aid is open; a route change SHALL dismiss the aid. The aid SHALL NOT form permanent navigation chrome.

#### Scenario: Flick and stop a list
- **WHEN** a person flicks through installed apps or notification history and then touches the moving content
- **THEN** the content coasts within its bounds, stops under the new finger, and does not activate an item until a separate tap

#### Scenario: Help exposes optional navigation controls
- **WHEN** a person opens Help in All apps and selects Navigation buttons
- **THEN** large labeled Home, All apps, Notifications and Settings controls appear with explicit return routes, and disappear when the person changes route

#### Scenario: Long press cancels
- **WHEN** a person holds an app or card until a visible context cue appears and then moves away or performs contextual Back
- **THEN** the context action is cancelled without launching, reordering, or closing that item

### Requirement: Shell movement preserves spatial continuity

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: retained host/QEMU integration checks prove their own cases; operator accepts installed behavior, but individual physical frame/blank/continuity measurements are not claimed. -->
The shell userspace SHALL present app→card entry, adjacent deck travel, card→app expansion, drawer rising from Home, shade descending over the task, and app launch/return as related positions in one scene. The selected live app SHALL keep its identity and visual content through eligible transforms; direction, scale, stacking order, and focus SHALL resolve coherently when motion is interrupted, reversed, or retargeted. No transition SHALL show an unowned black/blank frame or another app's private pixels. Reduced motion SHALL preserve interactive drag, destination, focus, feedback, and recovery with shorter settling and no decorative travel.

#### Scenario: Reverse an unfinished expansion
- **WHEN** a person starts expanding a card and immediately returns to Home
- **THEN** the visible surface continues from its current position, settles in the deck without a jump or flash, and focus follows the settled destination

#### Scenario: App closes during motion
- **WHEN** a live source disappears or refuses an upward throw while cards are moving
- **THEN** the shell cancels or retargets movement to a valid scene, names the close result, and retains a reachable Overview, Home and drawer

### Requirement: Gesture ownership and feedback are explicit

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator accepts physical feel and waives further recordings; no new per-case physical feedback matrix is claimed.
Narrowed 2026-09-28 (user-authorized scope split, "yes a-d and f"): the
general at-down touch arbitration across bottom/top/side/keyboard/deck/app
content is now `the-shell-gets-side-edge-back-and-motion-trace`'s own "One
arbiter owns every touch at down" requirement (task 4.4). This requirement
keeps only the general feedback scope this change actually implements. -->
After a gesture is accepted, another surface SHALL NOT reinterpret that sequence as a tap or swipe. Accepted press, long press, snap, close request, refusal, and failure SHALL have immediate visible feedback.

#### Scenario: Card snap feedback
- **WHEN** a card settles after a swipe
- **THEN** its selected/focused state is visible without relying on vibration

### Requirement: Installed application icons retain identity and privacy

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: icon implementation and privacy checks retain host/QEMU proof; no new per-icon/fallback/privacy physical matrix is claimed. -->
The drawer, eligible card headers, and trusted app notifications SHALL resolve an installed app's desktop-entry Icon through the image's icon theme where available, use a consistent sized fallback glyph when absent or unreadable, and keep a text label as the identifying route. Icon loading SHALL be bounded/cached so scrolling does not repeatedly decode assets. A private card SHALL show a neutral placeholder without its title or app-specific icon. Context actions SHALL use readable labels with any icon as a secondary cue.

#### Scenario: Missing installed icon
- **WHEN** an installed desktop entry has no resolvable Icon
- **THEN** its drawer row shows a neutral fallback at the same size with the app name, and can still be tapped

#### Scenario: Private running card
- **WHEN** a running app is marked private by the card owner
- **THEN** the deck shows neither its title nor an icon that identifies it

### Requirement: Surfaces explain their state

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: operator accepts installed state/recovery behavior; no new individual failure-state physical trial is claimed. -->
Each shell surface SHALL distinguish loading, empty, stale, failure, and cancellation where those states apply, using short text and a next gesture or contextual action. Focus and pressed states SHALL have a non-color cue; a failed launch SHALL retain the drawer or Home recovery.

#### Scenario: No running applications
- **WHEN** the person reaches Home with no eligible app
- **THEN** the deck explains that it is empty and cues the installed-app drawer

#### Scenario: Reduced motion
- **WHEN** reduced motion is enabled and the person enters or exits a surface
- **THEN** the same destination, focus, and recovery path appear without decorative interpolation

### Requirement: Card deck integration respects the app-card contract

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
<!-- UNVERIFIED: app-card/composition implementation is already accepted; this archive adds no new per-case physical source-loss or cost measurement. -->
The shell userspace SHALL present a consistent visual frame and navigation around the app-card interaction when that capability is available. When it is unavailable, it SHALL state that visual cards are unavailable and retain a safe task/drawer route; it SHALL NOT portray metadata as a live app surface or silently replace a failed live deck with a second Home design.

#### Scenario: Card composition is unavailable
- **WHEN** the deck cannot render an eligible app surface
- **THEN** the person sees an unavailable or private-content state and can focus an app or open the drawer
