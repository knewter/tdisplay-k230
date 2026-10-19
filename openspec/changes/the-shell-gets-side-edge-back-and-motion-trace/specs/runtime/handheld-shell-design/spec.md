## ADDED Requirements

### Requirement: A qualified side edge dismisses shell surfaces without touching app content

*Grounding: native-injected board cases and operator real-finger acceptance
("back works fine") recorded in task 1.3 of the archived change
`2026-10-19-the-shell-gets-side-edge-back-and-motion-trace` and
`docs/evidence/coherent-shell/side-edge-back/board-2026-10-16-injected.md`.
The context-sheet route is wired; host routing/ownership fixtures retain
sources and limits in the task results.*
An inward touch gesture from a qualified side edge SHALL dismiss the topmost
shell context in order: an open long-press context sheet; then Settings,
shade, or drawer; then the on-screen keyboard when it owns input focus. The
gesture SHALL NOT synthesize a Back/Escape/Alt-Left keypress into arbitrary
Wayland application content. This is separate from and does not replace the
existing bottom-edge overlay-escape recognizer, which remains for bottom-edge
swipes reaching the overview or switching apps from a mapped overlay.

#### Scenario: Dismiss Settings from its side edge
- **WHEN** a person makes an inward swipe from the qualified side edge while
  Settings (including a sub-page) is mapped
- **THEN** Settings dismisses into the prior deck or app, with no keypress
  delivered to any application

#### Scenario: Side edge does not touch app content
- **WHEN** a person makes the same side-edge gesture while an ordinary app,
  with no shell context open, has focus
- **THEN** the app receives no synthesized Back/Escape keypress and the
  gesture has no effect on app content

### Requirement: One arbiter owns every touch at down

*Grounding: native-injected board routing/keyboard cases in
`docs/evidence/coherent-shell/side-edge-back/board-2026-10-16-injected.md`
and host `tests/test_card_shell_route.py`. App scrolling/text-selection
contention beyond these cases has host policy coverage only; no broad
physical app-content acceptance is inferred.*
<!-- UNVERIFIED: physical app scrolling/text-selection contention beyond the
named injected routing cases retains host policy coverage only. -->
A single compositor-side arbiter SHALL decide, at touch-down, which of bottom
Home/drawer, top shade, side Back, keyboard, deck, or app content owns a
contact, using measured hit regions. Ordinary app scrolling and text selection
SHALL remain with the app outside every qualified edge region. A keyboard
region in its reserved lower area SHALL win over a Home/drawer gesture there.

#### Scenario: App scroll near an edge is not stolen
- **WHEN** a person begins a scroll or text selection inside an app, starting
  outside every qualified edge region
- **THEN** the app keeps that touch stream and no shell edge gesture starts

#### Scenario: Keyboard region wins in its reserved area
- **WHEN** the on-screen keyboard is shown and a touch begins in its reserved
  lower region
- **THEN** the keyboard receives the touch instead of a bottom Home/drawer or
  side Back gesture starting there

### Requirement: Shell motion is measured against declared budgets

*Grounding: actual-board native-injected traces and concurrent camera-visible
card motion in `docs/evidence/coherent-shell/motion-2026-10-19/camera/README.md`,
with original telemetry, video hashes, bounded clock correlation and camera
sampling limits. Both motion modes honestly fail the declared timing budgets;
reduced settling is shorter. This is measurement/reporting proof, not a
performance pass or every-refresh optical blanking proof.*
The shell SHALL produce a touch-to-scene-damage, damage-to-commit,
commit-to-frame-done, and frame-done-to-output-presented trace with stable
IDs correlating one accepted touch through to panel presentation, plus
process CPU/memory sampling. Declared p95/p99 input-to-present, frame
interval, and blank/missed-frame budgets SHALL be checked against this trace,
and a failed budget SHALL be reported honestly rather than omitted. Reduced
motion SHALL preserve the same trace stages with shorter settling.

#### Scenario: Host self-test proves the trace schema
- **WHEN** the trace tool runs its self-test without a board
- **THEN** it reports the full touch-to-present ID chain and budget format
  without claiming panel presentation proof

#### Scenario: A board run reports a failed budget honestly
- **WHEN** a board trace run measures an interval exceeding a declared budget
- **THEN** the report names the failed budget and the measured value rather
  than omitting or rounding it into a pass
