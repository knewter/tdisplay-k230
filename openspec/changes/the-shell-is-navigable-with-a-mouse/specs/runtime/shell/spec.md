## ADDED Requirements

### Requirement: Shell navigation is complete with pointer input

<!-- UNVERIFIED: implementation and board pointer matrix pending. -->
The userspace shell SHALL allow primary clicks/drags and scrolling to navigate Home, app drawer, overview, notification shade and Settings, including theme and Wi-Fi pages. An app SHALL remain open when Home is selected from overview.

#### Scenario: Home without closing windows
- **WHEN** a person taps or clicks the Home affordance in overview, or swipes upward from its footer
- **THEN** Home is displayed and existing app windows remain available in overview

#### Scenario: Return from Home to open windows
- **WHEN** Home is visible with apps still open and a person taps or clicks its bottom gesture handle
- **THEN** overview shows those live windows without launching or closing an app
- **AND** an upward drag from that handle opens the app drawer instead

#### Scenario: Client controls remain tappable at screen edges
- **WHEN** a person taps a client control in a shell edge band, including an app header or the drawer-search keyboard Backspace key
- **THEN** the intended live client receives a balanced tap and performs its normal action
- **AND** no shade is revealed and no drawer is dismissed solely because the contact began at an edge
- **AND** a deliberate qualifying edge drag still uses the native shell gesture

#### Scenario: Pointer overview round trip
- **WHEN** a person drags upward from the bottom screen edge with the primary mouse button, then clicks a live overview card
- **THEN** overview opens and the chosen app expands and receives focus

#### Scenario: Pointer screen-edge routes
- **WHEN** a person drags downward from the top screen edge or upward from the bottom edge
- **THEN** the appropriate shell shade, overview or drawer follows the drag and settles using the existing navigation rules
- **AND** ordinary pointer interactions away from shell-owned regions remain application input

#### Scenario: Shell scrolling
- **WHEN** a person uses a mouse wheel or two-finger scrolling over scrollable drawer, notification, Wi-Fi or theme content
- **THEN** the relevant content moves within its bounds without launching an app or applying a theme

### Requirement: Four-finger spread enters the centered window

<!-- UNVERIFIED: physical four-finger recognition pending. -->
In HDMI trackpad mode the userspace shell SHALL use a four-finger outward pinch on the built-in glass to expand the centered live overview window. Inward pinch SHALL open overview. Ordinary two-finger application pinch SHALL remain available to applications.

#### Scenario: Spread from overview
- **WHEN** overview is open with a centered live, focusable window and a person spreads four fingers
- **THEN** that window expands through the existing transition and becomes focused

#### Scenario: Empty overview
- **WHEN** no live window is available and a person spreads four fingers
- **THEN** no app is closed or incorrectly focused
