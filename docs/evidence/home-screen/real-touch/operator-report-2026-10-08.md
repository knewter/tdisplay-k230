# Home screen: operator real-finger report (task 8.1)

2026-10-08, America/Chicago. Evidence class: **operator real-finger report**
on the physical AMOLED, with shell log corroboration. There is no camera
capture: the operator asked for their report to stand in its place ("don't
worry about capture just trust me").

Installed system: mainline 7.3.0-rc5 coherent shell `kp6ldmdx…`, shell
executable `q2rxmp98…-k230-shell-rust` (`docs/evidence/mainline-sd-throughput/postboot.json`).

Operator reports:
- "i can swipe between home pages and tap the icons" (Home page swipe, icon taps).
- After being asked to long-press and pin, unpin and rearrange an icon, tap a
  dock icon, and check launch-vs-focus (launch a closed app, return Home, tap
  it again): "worked."
- On the dark/light theme repeat: "don't bother with the other theme it's fine".
  The report therefore covers **one theme only** (the active theme at the time).

Shell log (`journalctl -u shell-ui`) during the session showed
`app-launch-requested` → `app-launch-process-exited` (a deliberate failing test
entry, removed afterwards), then `app-launch-focused` at 16:37:28 and 16:37:40.
Those two lines are the second-tap focus of an already running app.

Not covered: a second theme, and the right-click/New Window acceptance
(task 11.4, HDMI and mouse, scheduled separately).
