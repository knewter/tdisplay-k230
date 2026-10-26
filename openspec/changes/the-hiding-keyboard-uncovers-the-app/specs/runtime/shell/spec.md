## MODIFIED Requirements

### Requirement: Keyboard motion follows contact and settles continuously

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/keyboard.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: operator accepts keyboard gestures on 2026-10-01; see docs/evidence/proposal-closeout/2026-10-01/keyboard.md. Earlier source/QEMU/installed evidence remains distinct. Quantitative responsiveness measurement is deferred to the-shell-profiles-reported-interaction-jank; not claimed passed. -->
<!-- Grounding: the hiding keyboard uncovering app content is shown by injected-touch grim frames in docs/evidence/interaction-jank/keyboard-hide, and the operator accepted it on glass on build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
During an accepted keyboard drag the system SHALL move the keyboard with direct proportional contact displacement, remain stationary while contact is held still, and reverse immediately with contact. Release SHALL settle from the displayed geometry and bounded measured velocity to shown or hidden without a position jump or abrupt end. Reduced motion SHALL preserve direct manipulation while shortening release settlement. Reserved app space MUST match the final visible keyboard and remain coherent during transition. While the keyboard moves toward hidden, the app SHALL already hold the space the hidden keyboard releases, so the keyboard uncovers app content rather than a fill; while it moves toward shown, reserved space SHALL follow the keyboard.

#### Scenario: Drag and reconsider
- **WHEN** a person drags the keyboard handle down, pauses, reverses, and releases before dismissal commits
- **THEN** the keyboard mirrors that motion and returns smoothly without losing the focused app

#### Scenario: Finish hiding
- **WHEN** a downward dismiss gesture commits
- **THEN** the keyboard smoothly leaves the output, its handle disappears and the app regains the available space

#### Scenario: Hiding uncovers the app
- **WHEN** the keyboard starts moving down
- **THEN** the app is resized to the height it will have with the keyboard hidden, and the area the sliding keyboard uncovers shows the app's own content
