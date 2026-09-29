## ADDED Requirements

### Requirement: Portrait HDMI interactions stay within a measured frame budget

<!-- UNVERIFIED: desired performance; the existing rotated board trial fails it. -->
The system-owned shell SHALL preserve full-resolution portrait HDMI layout,
live app contents, backgrounds, alpha and rounded cards while keeping p95
frame-build CPU time at or below 33.3 ms and p95 contact-to-present time at or
below 100 ms for one- and two-Foot-card workloads of at least 24 drags each.
Results SHALL identify format, transform, resolution, runtime revision and input
evidence class. Injected input SHALL NOT be represented as real-glass acceptance.
Grounding for the current failure: `docs/evidence/shell-responsive/board/README.md`.

#### Scenario: The operator drags a portrait HDMI card
- **WHEN** the operator opens ordinary apps and performs the recorded bottom-edge
  and overview drag workloads on the reserved board at 1920×1080, transform 90
- **THEN** portrait content remains correct and live, and a committed physical
  trace meets both budgets without lowering resolution or removing visual content

#### Scenario: A changing client is shown during a transition
- **WHEN** an app updates its content while its card moves or changes size
- **THEN** the visible card updates correctly without stale cached pixels,
  corrupt corners, lost frame callbacks or unreleased buffers

### Requirement: Portrait HDMI app-edge gestures preserve touch ownership

<!-- UNVERIFIED: the operator reports this fails while an app is open. -->
The system-owned shell SHALL recognize a real bottom-edge swipe from an ordinary
app into the live overview at the portrait HDMI size. It SHALL preserve ordinary
app touch input away from reserved gesture edges and retain usable keyboard and
shade dismissal. Required proof SHALL pair physical contact/route observations
with operator confirmation, rather than substitute compositor IPC injection.
Grounding for the current failure: `docs/evidence/shell-responsive/board/README.md`.

#### Scenario: A real finger leaves an ordinary app
- **WHEN** the operator swipes upward from the device glass's bottom edge with
  Foot or another ordinary app open in absolute-touch HDMI mode
- **THEN** the focused app follows the gesture into the overview and remains
  selectable, and the committed observation records physical input acceptance

#### Scenario: App touches and shell overlays coexist
- **WHEN** the operator touches the app interior, opens and dismisses the
  keyboard, and opens and dismisses the notification shade
- **THEN** interior contacts continue reaching the app and each overlay can be
  dismissed without leaving touch ownership stuck or resetting the shell
