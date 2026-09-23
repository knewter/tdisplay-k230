# Current and recommended portrait frames

The left side describes the accepted native composition. The right side is a
contract for successors; it is not an implementation preview.

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
shows the current title/card/footer hierarchy; the shown keyboard changes the
usable height rather than proving every target is physically reachable.

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
