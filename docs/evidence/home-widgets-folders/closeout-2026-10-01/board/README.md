# Home folders and widgets: board acceptance

On 2026-10-01 the user authorized “check that stuff and close it”, supplementing previous finger acceptance of Home and drawer drag placement. The coordinator ran the committed `board-probe.py` on the reserved physical board through the serial console, using an isolated runtime layout. `result.json` names the exact activated coherent system and Rust client. The normal layout was restored after the probe.

Passed: drag creates a folder, joins a third member, opens it, renames it with the actual wvkbd, releases keyboard focus while retaining Home, extracts a member to the requested cell, moves/opens the remaining folder in the dock, places a Clock through the widget picker, and retains the layout across a real UI process restart. Screenshots were visually reviewed. They show actual app icons, the requested placements and the typed public `qqqq` folder name.

Commands: reserved `flock -n /tmp/k230-board.lock python3 tools/console.py '<board Python> <staged board-probe.py>'`; native images from `grim -t jpeg -q 85`, collected through framed base64 serial transfers. The exact paired QEMU folder/member/widget checks and regression with a mapped app behind the folder editor are recorded in the sibling `qemu/` reports.

Evidence class: real board, injected kernel uinput contacts, real Wayland/system-keyboard delivery, native output captures and persisted state assertions. This is not a newly performed human-finger/daylight photograph test; the user's delegated acceptance substitutes the former repeated manual sequence, without claiming that sequence was performed. The image closure was built and activated with `switch-to-configuration test`; final boot-profile installation is recorded by the deployment handoff.

Clock/weather/battery appearance on the same installed system is recorded under `docs/evidence/home-widget-design/closeout-2026-10-01/board/`. No battery attachment is present, and no attached-battery proof is claimed.
