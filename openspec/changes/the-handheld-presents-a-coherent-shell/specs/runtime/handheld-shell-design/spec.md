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
