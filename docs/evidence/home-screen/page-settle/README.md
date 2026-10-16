# Home settles onto a whole, existing page (board)

Change: `openspec/changes/home-pages-settle-after-a-cancelled-swipe`.

## Before the fix (system `yvh5nh6n…`, 2026-10-15)

- At 22:15 the operator's two-finger trackpad presses on page 2 each ended in
  `touch-cancel` in the shell log, and a grim at that time showed Home frozen
  about 44% of the way between pages 1 and 2. None of their presses there
  reached a widget.
- At 22:29 a scripted right-click and badge click
  (`tools/board-pointer.py`) removed the only widget on page 2.
  `before-fix-blank-vanished-page-1280x800-grim.png`: Home stayed on the
  deleted page, blank and with no page dots, while still in rearrange mode.

## After the fix (system `7csn4grb…`, deployed live 2026-10-15 22:40)

Battery - Details was put back alone on page 2 by writing
`~shell/.local/state/k230-shell/home.json` before the switch restarted the
shell. Then:

```
ssh k230 "$PY - 1280x800 'wait 300; swipe 1000 520 300 520 250; wait 1200; rclick 300 300; wait 800'" < tools/board-pointer.py
grim -> page2-right-click-1280x800-grim.png
ssh k230 "$PY - 1280x800 'wait 300; click 46 136; wait 1500'" < tools/board-pointer.py
grim -> after-removing-last-page-widget-1280x800-grim.png
```

The log shows `home-widget-secondary-click` (22:41:06), then `pointer-down`,
`pointer-up` and `home-layout-changed` (22:41:14). `home.json` no longer
contains `battery_details`. The second capture shows Home back on page 1
(Clock and Video) in rearrange mode. With one page left, no page dots are
drawn. Evidence class: injected pointer + grim.

The cancelled-trackpad-pan path was not injected: `tools/board-pointer.py`
drives a pointer, not the two-finger trackpad adapter. It is covered by host
tests and by the operator's task 2.2.
