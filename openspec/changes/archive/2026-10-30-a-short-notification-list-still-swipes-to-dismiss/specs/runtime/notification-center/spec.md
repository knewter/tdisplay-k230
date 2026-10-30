## MODIFIED Requirements

### Requirement: Actions and dismissal are explicit

*Grounding: operator acceptance and explicit additional-proof waiver in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`; prior host/QEMU/board evidence retains its original provenance. This is acceptance of the installed result, not a newly recorded individual-case test or timing measurement.*
*Grounding (2026-10-30): on the board, with injected touch, sideways swipes dismissed rows of a one- and a two-row landscape list with `NotificationClosed(id, 2)`, and an upward drag on the short list still closed the shade (`docs/evidence/short-list-swipe/board/README.md`).*
<!-- UNVERIFIED: operator acceptance and the proof waiver do not supply a new individual-case physical confirmation/failure/focus/priority recording. Existing implementation and host/QEMU results keep their original limits. -->
The shell userspace SHALL offer only actions whose target is currently available and SHALL distinguish opening an event from dismissing it. A failed action SHALL leave the event reachable with a short error and Retry or contextual dismissal route. Dismiss All SHALL require a clearly labeled control and SHALL NOT dismiss an ongoing critical system event.

#### Scenario: Target app is gone
- **WHEN** a person selects an event whose action target has exited
- **THEN** the shell reports the unavailable target and keeps the event until the person dismisses it

#### Scenario: Swipe an event sideways
- **WHEN** the person swipes a dismissible history item sideways
- **THEN** the item follows the finger and exposes a Dismiss cue; a short or reversed swipe returns it without dismissal, while a completed swipe removes only that event from history

#### Scenario: Swipe a row when the list does not scroll
- **WHEN** the landscape shade holds one or two notifications, so the list fits without scrolling, and the person swipes a dismissible row sideways
- **THEN** the row follows the finger and a completed swipe dismisses it, while an upward drag from the same place still closes the shade

