## Purpose

Defines the shared appearance and navigation behavior of the NixOS handheld shell across its persistent controls, application launcher, card deck, and temporary surfaces.

## ADDED Requirements

### Requirement: Shared portrait shell language
<!-- UNVERIFIED: proposed visual contract; existing panel and shell evidence proves dimensions and controls, not this integrated design. -->
The shell userspace SHALL use one high-contrast palette, text hierarchy, spacing system, and control vocabulary across Apps, Windows, Settings, and Notifications at the panel's 568×1232 portrait size. At the current output scale of 1, one logical pixel equals one panel pixel; primary touch targets SHALL be at least 56 such pixels tall and later scaling SHALL preserve their physical size. Essential information SHALL remain legible without color alone.

#### Scenario: Move between surfaces
- **WHEN** a person moves from Apps to Windows to Settings
- **THEN** the surface title, active state, Back route, and primary controls remain recognizable and reachable

### Requirement: Routes remain visible and recoverable
<!-- UNVERIFIED: cross-surface integration awaits implementation and physical observation. -->
The shell userspace SHALL label the persistent entry actions Apps, Windows, Keyboard, and System. System SHALL expose distinct Settings and Notifications entries. Home SHALL be a separate, visible recovery action in shell overlays and land in Apps; Terminal recovery SHALL be explicitly named Terminal. Back SHALL remain separate and close the top transient surface before changing the underlying app or deck. A gesture SHALL have a visible control route to the same destination.

#### Scenario: Gesture is missed
- **WHEN** a person cannot complete a swipe from an application
- **THEN** a visible control still opens the card deck or Apps, and Back restores the prior focus

#### Scenario: Keyboard occupies the lower panel
- **WHEN** the on-screen keyboard is shown
- **THEN** the focused input and an explicit Back or Home route remain above the keyboard, and no essential action is hidden behind it

### Requirement: Touch manipulation drives normal navigation
<!-- UNVERIFIED: proposed gesture and kinetic behavior requires host traces and real-finger board proof. -->
The shell userspace SHALL follow one accepted finger during a deck drag, launcher/settings/history scroll, or eligible page swipe. A release SHALL resolve from the displayed position with bounded momentum and a visible settled destination; a new touch SHALL stop coasting. Tapping a card or app SHALL activate it. A deliberate long press SHALL show a context cue before an action, allow movement away or cancellation without activation, and never masquerade as a tap. Previous/Next controls MAY remain as secondary accessible alternatives but SHALL NOT be required for ordinary browsing.

#### Scenario: Flick and stop a list
- **WHEN** a person flicks through installed apps or notification history and then touches the moving content
- **THEN** the content coasts within its bounds, stops under the new finger, and does not activate an item until a separate tap

#### Scenario: Long press cancels
- **WHEN** a person holds an app or card until a visible context cue appears and then moves away or presses Back
- **THEN** the context action is cancelled without launching, reordering, or closing that item

### Requirement: Shell movement preserves spatial continuity
<!-- UNVERIFIED: coordinated motion is a successor to the bounded core card work, not a claim that its current direct-drag endpoints animate. -->
The shell userspace SHALL present app→card entry, adjacent deck travel, card→app expansion, app launch/return, launcher entry, and nonmodal notification movement as related positions in one scene. The selected live app SHALL keep its identity and visual content through eligible transforms; direction, scale, stacking order, and focus SHALL resolve coherently when an animation is interrupted, reversed, or retargeted. No transition SHALL show an unowned black/blank frame or another app's private pixels. Reduced motion SHALL preserve the same interactive drag, destination, focus, feedback, and recovery with shorter settling and no decorative travel.

#### Scenario: Reverse an unfinished expansion
- **WHEN** a person starts expanding a card and immediately returns to the deck
- **THEN** the visible surface continues from its current position, settles in the deck without a jump or flash, and focus follows the settled destination

#### Scenario: App closes during motion
- **WHEN** a live source disappears or refuses an upward throw while cards are moving
- **THEN** the shell cancels or retargets movement to a valid scene, names the close result, and retains a reachable Apps/Home route

### Requirement: Gesture ownership and feedback are explicit
<!-- UNVERIFIED: edge conflicts and physical feel require board checks. -->
The shell userspace SHALL arbitrate each touch at down between shell control, keyboard, app content, deck, and overlay; after ownership is accepted, another surface SHALL NOT reinterpret that sequence as a tap or swipe. App scrolling and text selection SHALL remain with the app. An app→deck edge gesture SHALL be enabled only in a tested edge region that does not conflict with app/keyboard controls; until then Windows remains the visible entry. Accepted press, long press, snap, close request, refusal, and failure SHALL have immediate visible feedback.

#### Scenario: App scroll and shell edge conflict
- **WHEN** a person begins a horizontal app scroll or text selection outside the qualified deck-entry edge
- **THEN** the app keeps that touch stream and no shell card transition starts

#### Scenario: Card snap feedback
- **WHEN** a card settles after a swipe
- **THEN** its selected/focused state is visible without relying on vibration

### Requirement: Surfaces explain their state
<!-- UNVERIFIED: proposed copy and state consistency. -->
Each shell surface SHALL distinguish loading, empty, stale, failure, and cancellation where those states apply, using short text and an available next action. Focus and pressed states SHALL have a non-color cue; a failed app action SHALL retain Apps or Home recovery.

#### Scenario: No running applications
- **WHEN** the person opens Windows with no eligible app
- **THEN** the shell explains that the deck is empty and offers Apps and Back

#### Scenario: Reduced motion
- **WHEN** reduced motion is enabled and the person enters or exits a surface
- **THEN** the same destination, focus, and recovery controls appear without decorative interpolation

### Requirement: Card deck integration respects the app-card contract
<!-- UNVERIFIED: physical live-card behavior belongs to the open app-card and composition changes. -->
The shell userspace SHALL present a consistent visual frame and navigation around the app-card interaction when that capability is available. When it is unavailable, the shell SHALL state that visual cards are unavailable and retain its working window focus route; it SHALL NOT portray metadata as a live app surface.

#### Scenario: Card composition is unavailable
- **WHEN** the deck cannot render an eligible app surface
- **THEN** the person sees an unavailable or private-content state and can focus an app or return to Apps
