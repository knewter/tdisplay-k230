## ADDED Requirements

### Requirement: A qualified side edge dismisses shell surfaces without touching app content

<!-- UNVERIFIED: side-edge contextual Back is not implemented; only the different bottom-edge overlay-escape fix (the-shell-behaves-as-one-coherent-system slice E) has landed. -->
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

<!-- UNVERIFIED: general touch-ownership arbitration across bottom/top/side/keyboard/deck/app-content is not implemented as a single decision point. -->
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

<!-- UNVERIFIED: tools/shell-motion-trace.py and tests/test_shell_motion.py do not exist; no budget has been measured under this schema. -->
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
