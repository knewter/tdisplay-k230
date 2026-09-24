## Purpose

Defines the final gesture-led visual and navigation behavior of the NixOS handheld shell across its live-card Home, installed-app drawer, notification shade, Settings, and temporary surfaces.

## ADDED Requirements

### Requirement: Shared portrait shell language
<!-- UNVERIFIED: proposed visual contract; current panel evidence proves dimensions, not this final layout. -->
The shell userspace SHALL use one high-contrast palette, text hierarchy, spacing system, and touch vocabulary across the deck, drawer, shade, Settings, and notifications at the panel's 568×1232 portrait size. At the current output scale of 1, one logical pixel equals one panel pixel; interactive targets SHALL be at least 56 such pixels tall and later scaling SHALL preserve physical size. Essential information SHALL remain legible without color alone. The final normal session SHALL have no permanently visible Apps/Windows/Keyboard/System rail or Back/Home footer.

#### Scenario: Move between surfaces
- **WHEN** a person moves from a live card to the drawer, shade, and Settings
- **THEN** each surface retains recognizable type, focus, motion direction, and a discoverable gesture cue without permanent navigation buttons

### Requirement: Home is the live card deck
<!-- UNVERIFIED: app-to-deck entry, empty deck, and final Home behavior require implementation and real-glass proof. -->
The shell userspace SHALL treat the live card overview as Home. A bottom-edge upward gesture from an app or transient surface SHALL lead to that deck with the current eligible app shrinking into its live card. Repeating Home at the deck SHALL leave it stable. With no eligible app, Home SHALL show a useful empty deck with an upward drawer cue and a named Terminal recovery app reachable in the drawer; it SHALL NOT open a second home grid. A continued upward pull from the deck SHALL reveal the installed-app drawer from the bottom.

#### Scenario: Return from an app
- **WHEN** a person swipes up from the bottom of a running app
- **THEN** the same live app moves into a card in Home and can be tapped to expand again

#### Scenario: Empty deck
- **WHEN** no eligible app is running and a person reaches Home
- **THEN** an empty deck explains the state and visibly cues the upward drawer gesture, where Terminal remains available

#### Scenario: Pull from Home into installed apps
- **WHEN** a person continues dragging upward from the deck past the drawer threshold
- **THEN** the drawer follows the finger and settles open; releasing below that threshold restores the deck without an accidental app launch

### Requirement: Shade and contextual Back preserve the task
<!-- UNVERIFIED: final shade and edge arbitration await implementation and physical proof. -->
A downward gesture from the top edge SHALL reveal a notification shade over the current scene; the shade SHALL expose notification history and a truthful Settings entry. An inward edge Back gesture SHALL dismiss the topmost shell context in order: context sheet, shade/Settings/drawer, then keyboard when that input owns focus, returning to the prior deck or app. Back SHALL NOT synthesize a universal keypress into arbitrary Wayland application content. The bottom Home gesture SHALL remain the shell escape while a context is open.

#### Scenario: Read a notice while typing
- **WHEN** a person drags the shade down during an app task
- **THEN** the underlying app remains in place, its prior focus is recoverable, and Settings is reachable within the shade

#### Scenario: Dismiss a shell surface
- **WHEN** a person makes the contextual Back gesture in Settings or the drawer
- **THEN** only that shell surface retreats and the prior deck or app is restored without sending an unrequested Back action to the app

#### Scenario: Keyboard owns an edge
- **WHEN** the on-screen keyboard occupies the lower panel and a touch begins in its reserved region
- **THEN** keyboard input wins over a Home/drawer gesture; a tested shell escape remains available above or outside that region

### Requirement: Touch manipulation drives normal navigation
<!-- UNVERIFIED: proposed finger tracking, kinetic behavior, and long press require host traces and real-finger board proof. -->
The shell userspace SHALL follow one accepted finger during a deck drag, drawer/Settings/history scroll, or eligible section swipe. During an accepted drag, the manipulated edge or grabbed point SHALL move one logical pixel per logical pixel of finger movement within its travel bounds, including immediate reversal; a stationary held finger SHALL produce no continued movement. Recognition and release thresholds SHALL NOT multiply visible displacement. Easing, inertia, and automatic settling SHALL begin only after release or cancellation. A release SHALL resolve from the displayed position with bounded momentum and a visible settled destination; a new touch SHALL stop coasting. Tapping a card or app SHALL activate it. A deliberate long press SHALL show a context cue before an action, allow movement away or cancellation without activation, and never masquerade as a tap. Optional visible accessibility controls SHALL be available only in a deliberately opened aid view and SHALL NOT form permanent navigation chrome.

#### Scenario: Flick and stop a list
- **WHEN** a person flicks through installed apps or notification history and then touches the moving content
- **THEN** the content coasts within its bounds, stops under the new finger, and does not activate an item until a separate tap

#### Scenario: Long press cancels
- **WHEN** a person holds an app or card until a visible context cue appears and then moves away or performs contextual Back
- **THEN** the context action is cancelled without launching, reordering, or closing that item

### Requirement: Shell movement preserves spatial continuity
<!-- UNVERIFIED: coordinated motion succeeds the bounded core card work; current endpoints do not prove it. -->
The shell userspace SHALL present app→card entry, adjacent deck travel, card→app expansion, drawer rising from Home, shade descending over the task, and app launch/return as related positions in one scene. The selected live app SHALL keep its identity and visual content through eligible transforms; direction, scale, stacking order, and focus SHALL resolve coherently when motion is interrupted, reversed, or retargeted. No transition SHALL show an unowned black/blank frame or another app's private pixels. Reduced motion SHALL preserve interactive drag, destination, focus, feedback, and recovery with shorter settling and no decorative travel.

#### Scenario: Reverse an unfinished expansion
- **WHEN** a person starts expanding a card and immediately returns to Home
- **THEN** the visible surface continues from its current position, settles in the deck without a jump or flash, and focus follows the settled destination

#### Scenario: App closes during motion
- **WHEN** a live source disappears or refuses an upward throw while cards are moving
- **THEN** the shell cancels or retargets movement to a valid scene, names the close result, and retains a reachable deck and drawer

### Requirement: Gesture ownership and feedback are explicit
<!-- UNVERIFIED: bottom/top/side edge conflicts and physical feel require board checks. -->
The compositor and shell userspace SHALL arbitrate each touch at down between bottom Home/drawer, top shade, contextual Back, keyboard, app content, deck, and overlay. After a gesture is accepted, another surface SHALL NOT reinterpret that sequence as a tap or swipe. Ordinary app scrolling and text selection SHALL remain with the app outside qualified edge regions. Accepted press, long press, snap, close request, refusal, and failure SHALL have immediate visible feedback.

#### Scenario: App scroll and Home conflict
- **WHEN** a person begins an app scroll or text selection outside the qualified bottom region
- **THEN** the app keeps that touch stream and no shell card transition starts

#### Scenario: Card snap feedback
- **WHEN** a card settles after a swipe
- **THEN** its selected/focused state is visible without relying on vibration

### Requirement: Installed application icons retain identity and privacy
<!-- UNVERIFIED: final icon loading, theme fallback and private-card behavior await implementation. -->
The drawer, eligible card headers, and trusted app notifications SHALL resolve an installed app's desktop-entry Icon through the image's icon theme where available, use a consistent sized fallback glyph when absent or unreadable, and keep a text label as the identifying route. Icon loading SHALL be bounded/cached so scrolling does not repeatedly decode assets. A private card SHALL show a neutral placeholder without its title or app-specific icon. Context actions SHALL use readable labels with any icon as a secondary cue.

#### Scenario: Missing installed icon
- **WHEN** an installed desktop entry has no resolvable Icon
- **THEN** its drawer row shows a neutral fallback at the same size with the app name, and can still be tapped

#### Scenario: Private running card
- **WHEN** a running app is marked private by the card owner
- **THEN** the deck shows neither its title nor an icon that identifies it

### Requirement: Surfaces explain their state
<!-- UNVERIFIED: proposed state copy and cross-surface consistency. -->
Each shell surface SHALL distinguish loading, empty, stale, failure, and cancellation where those states apply, using short text and a next gesture or contextual action. Focus and pressed states SHALL have a non-color cue; a failed launch SHALL retain the drawer or Home recovery.

#### Scenario: No running applications
- **WHEN** the person reaches Home with no eligible app
- **THEN** the deck explains that it is empty and cues the installed-app drawer

#### Scenario: Reduced motion
- **WHEN** reduced motion is enabled and the person enters or exits a surface
- **THEN** the same destination, focus, and recovery path appear without decorative interpolation

### Requirement: Card deck integration respects the app-card contract
<!-- UNVERIFIED: physical live-card behavior belongs to the open app-card and composition changes. -->
The shell userspace SHALL present a consistent visual frame and navigation around the app-card interaction when that capability is available. When it is unavailable, it SHALL state that visual cards are unavailable and retain a safe task/drawer route; it SHALL NOT portray metadata as a live app surface or silently replace a failed live deck with a second Home design.

#### Scenario: Card composition is unavailable
- **WHEN** the deck cannot render an eligible app surface
- **THEN** the person sees an unavailable or private-content state and can focus an app or open the drawer
