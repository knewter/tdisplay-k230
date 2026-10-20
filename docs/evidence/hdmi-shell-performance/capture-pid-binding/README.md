# Capture binds to the live compositor — 2026-10-20 UTC

The HDMI helper queried `k230-card-shell.service`, while the installed coherent
system runs the compositor in `shell.service`. It now selects the exact PID
from the existing Sway IPC peer credentials for every bounded journal read,
including arming, physical polling and final cleanup/export. This also avoids
mixing two compositor instances after a service restart. Numeric PID validation,
time/row/byte bounds and diagnostic allowlisting remain in place.

`python3 tools/hdmi-shell-capture-board.py --self-test` exits0:10 tests pass.
The journal regression checks the live PID selection and rejection before
spawning a process for invalid PIDs; the existing capture/cleanup fixture also
requires every read to use its actual IPC peer. `host-tests.txt` and
`identity.json` preserve the result and exact helper hash. This is host proof.

The read-only reserved-board preflight in `output-preflight.json` observes
only DSI-1, logical1232×568, transform270, running the qualified j30 system.
The brief reservation was released without changing outputs. A connected
1920×1080 transform90 monitor is needed before the portrait capture. No new
HDMI latency, gestures, pixel or default-selection acceptance is claimed.

The older `impl/portrait-hdmi` worktree atcbf52a2c has10 uncommitted/staged
paths. Those files were inspected read-only and preserved. Current work is
isolated in `.claude/worktrees/portrait-hdmi-proof`, branch
`perf/portrait-hdmi-proof`, baseff4ee705. The existing proposal stays3/12 tasks
complete; the remaining hardware/profile requirements are unchanged.
