# Current and recommended portrait frames

The diagrams are current schematics traced from the cited native captures, not screenshots. The proposed side is a contract for successors, not an implementation preview.

## Apps, keyboard hidden

```text
CURRENT (native evidence)                 RECOMMENDED CONTRACT
+--------------------------------+         +--------------------------------+
| Apps | Windows | Keyboard | Sys | 56px   | Apps | Windows | Keyboard | Sys |
+--------------------------------+         +--------------------------------+
|            Applications        |         | title + one state line          |
|       7 installed · Page 1/4   |         | clearly distinct hierarchy      |
|                                |         |                                |
|      [ Terminal            ]   |         | [ primary card, 56px+ target ] |
|      [ Monitor             ]   |         | [ title + short hint ]          |
|      [ New terminal        ]   |         | [ visible focus/status ]        |
|                                |         |                                |
| [ Previous ] [ Back ] [ Next ] |         | [ Previous ] [ Back ] [ Next ] |
+--------------------------------+         +--------------------------------+
```

Reference: [Apps with keyboard](../../evidence/launcher-gestures/integrated-injected/keyboard-visible.png)
(captured 2026-09-23) shows the current title/card/footer hierarchy; the shown keyboard changes the usable height rather than proving every target is physically reachable.

## Overview / transient state

```text
+--------------------------------+
| persistent controls remain     |
+--------------------------------+
| Windows · 2 running · Page 1/1 |
| [ terminal title · normal   ]  |
| [ Monitor · focused          ] |
|                                |
| loading / empty / stale / fail |
| must name what happened and    |
| expose Back or Apps/Home       |
+--------------------------------+
```

The current two-card composition is visible in
[overview.png](../../evidence/launcher-gestures/integrated-injected/overview.png).
A future live-card surface follows the card proposals; it must not hide the
persistent recovery route.

## Reviewable SVG sheets

- [Apps comparison](apps-comparison.svg) ties the generic endpoint/card finding
  to UX-01 and UX-03.
- [Keyboard-visible comparison](keyboard-comparison.svg) ties the reserved
  lower viewport and recovery route to UX-04.
- [Live-card overview comparison](live-card-overview.svg) ties global recovery
  controls and normalized failure states to UX-02 and UX-05. Its right-hand
  panel is conceptual and awaits the card architecture decision.
