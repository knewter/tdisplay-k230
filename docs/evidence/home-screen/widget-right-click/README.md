# A right-click on a Home widget enters rearrange mode (board)

Change: `openspec/changes/home-widgets-answer-a-right-click`, commit on branch
`home-widgets-answer-a-right-click`, deployed live with
`switch-to-configuration test` on 2026-10-15 (system `yvh5nh6n…`).

## Task 2.1, right-click: injected pointer + grim

At 1280x800 on HDMI, with the board's layout (Clock 4x2 at slot 0, Video at
slot 4, Battery 2x2 at slot 5, Weather 2x2 at slot 7 on page 1):

```
ssh k230 "$PY - 1280x800 'wait 300; rclick 300 300; wait 600'" < tools/board-pointer.py
grim  ->  right-click-clock-rearrange-1280x800-grim.png
```

(300, 300) lies inside the Clock, in a cell gap. The shell logged
`home-widget-secondary-click` at 22:14:22 and the capture shows rearrange mode:
Remove and Done pills, and a remove badge at the top-left corner of every
widget (Clock, Battery, Weather) as well as the icons.

## Badge click: not yet recorded by injection

Before the scripted badge click ran, the shell logged two `pointer-down` /
`pointer-up` / `home-layout-changed` sequences at 22:14:27 and 22:14:29 from the
physical trackpad, removing the Battery and Weather widgets, followed by two
more clicks that left rearrange mode. These came from the operator's own trackpad,
not from this script; the scripted badge click (sent at about 22:15) found
rearrange mode already closed and changed nothing. That is a log of a physical
interaction, not the operator's own report, so task 2.2 stays open until they
confirm it.
