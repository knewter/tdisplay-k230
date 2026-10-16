# Operator trackpad verdict on Home widgets, 2026-10-15

Evidence class: operator observation, with the shell/compositor log of the
same physical interactions. No injection ran at the logged times below. The
last scripted input was at 22:41:14 for the first block, and at about 23:37
for the second.

## Operator's words

After the trackpad fixes were deployed (system `c2wxyv7h…`), and after
instructions covering two-finger page swipes, a two-finger press on a widget
to right-click it, the remove badge, dragging to move, and Done, the operator
wrote: **"works ship"**.

## What the board log independently shows

Physical trackpad, system `7csn4grb…`:

```
22:48:10.779 home-menu-secondary-click      (right-click on empty Home)
22:48:19.262 home-layout-changed            (a widget placed from the picker)
22:48:25.237 home-menu-secondary-click
22:48:29.809 home-layout-changed            (a second widget placed)
```

The layout went from Clock and Video only (after the scripted removal at
22:41:14) to Clock, Video and Battery - Details on page 1, with Weather on
page 2. Both widgets were placed by clicks on picker rows.

Physical trackpad, system `c2wxyv7h…`:

```
23:46:57 – 23:47:06  five 'card_shell trackpad begin … 2 …' / 'end' pairs, all accepted
23:47:09.006 home-widget-secondary-click   (two-finger press on a widget -> rearrange)
23:47:10.846 pointer-down / 23:47:11.025 pointer-up   (leaving rearrange)
```

Earlier, at 22:14:27 and 22:14:29 (system `yvh5nh6n…`), two physical badge
clicks removed the Battery and Weather widgets
(`docs/evidence/home-screen/widget-right-click/README.md`).

## Limits

The log does not show a widget being moved or removed on page 2 by the
operator. That part rests on the operator's verdict alone. The picker click
the operator made placed Battery - Details and Weather; the plain "Battery"
row itself was not clicked.
