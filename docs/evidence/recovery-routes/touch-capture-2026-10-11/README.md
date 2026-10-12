# Recovery routes by touch on glass, 2026-10-11

Task 3.1 of OpenSpec change `the-shell-proves-recovery-states-by-touch`.

Installed build: system `7s8pl7pv…`, Rust ELF `si9vd9hh…`; see
[../touch-menu-installed-2026-10-11/](../touch-menu-installed-2026-10-11/README.md).
Every tap, hold and drag was made by the operator's finger on the panel. Every
state change that is not a touch was triggered by me (the agent) over serial or
SSH, and is listed as such below. Times are UTC, with the board's local time
(CDT) in brackets where the shell log is quoted.

The bench camera (Logitech C920, `/dev/video0`) looks along the panel from
its top edge. Committed clips are trimmed and downscaled to 640 px wide at
15 fps. The raw captures stay private on the host; their SHA256 hashes are in
[raw-clips.sha256](raw-clips.sha256) and their capture manifests sit beside
this file.

Capture command, for each clip:
`python3 tools/capture-feature.py <feature> --provenance real-touch --duration <s> --description … --output-dir docs/evidence/recovery-routes`

## 1. Window list by touch hold: empty, then stale (boot `8000d79e`)

[window-list.mp4](window-list.mp4): raw clip from 01:40:35Z, trimmed to 26–64 s.

- **Setup (serial):** before recording, every app window was closed. A
  one-shot watcher was armed to close all app windows 2 s after the next
  `app-menu-ready` that found an open window.
- **01:41:04Z [20:41:04]: Files held still, then lifted.** The shell logged
  `app-menu-hold`, then `app-menu-ready rows=3`, with no `home-drag-begin`. The
  menu stayed open after the lift: Open / New Window / Add to Home. The
  operator then tapped a row, which launched Files; the menu was not dismissed
  by tapping outside. The empty list's subtitle is too small to read at this
  angle.
- **Terminal opened (01:41:18Z), then held still in the drawer (01:41:24Z).**
  The shell logged `app-menu-hold`, then `app-menu-ready rows=5`.
- **01:41:27Z, serial trigger:** the watcher closed the Terminal window.
- **01:41:33Z: the window's row tapped.** The shell logged
  `app-launch-failed window is no longer available` and showed the stale
  splash. On camera the splash reads "That window has closed"
  ([zoom](stale-splash-camera-zoom.jpg)). The next tap went to the Apps
  drawer.
- No `home-drag-begin` was logged anywhere between 20:40:30 and 20:43:10
  local.

## 2. Settings brightness refused (boot `928b8c33`)

[brightness-denied.mp4](brightness-denied.mp4): raw clip from 03:29:05Z,
trimmed to 8–24 s.

- **Serial trigger:** with Settings already open, the backlight's
  `brightness` file was set from `664 root:shell` to `644`. It was restored to
  `664` at 03:29:26Z.
- **03:29:18Z [22:29:18]:** the operator dragged the brightness slider and
  let go. The shell logged
  `service-action-action-denied brightness-denied`.
- Glare hides the message on camera.
  [settings-denied-native.png](settings-denied-native.png) is a native `grim`
  capture taken afterwards, before the next Settings refresh. It shows "That
  action isn't allowed · Done" below Power, and the Brightness card as
  read-only "100%", because Settings refreshed while writes were refused.
- An earlier attempt is not counted. A polling watcher loaded the CPU enough
  for the Settings status helper to miss the shell's 4 s deadline. Settings
  then showed "settings response exceeded bound or deadline", and the watcher
  was removed.

## 3. Video cancelled and stopped (boot `928b8c33`)

Both come from the raw clip started at 03:32:45Z.

- [video-cancelled.mp4](video-cancelled.mp4) (46–64 s): the operator opened
  Video and left during the network load (the blank screen before the first
  frame). The shell logged `recovery-video-cancelled` at 03:33:40Z
  [22:33:40]. There was no agent trigger: the armed watcher was looking at the
  wrong state-file path and never fired.
- [video-stopped.mp4](video-stopped.mp4) (176–196 s): the operator opened
  Video again. A native capture at 03:34Z showed playback (480x270). At
  03:35:47Z the session was stopped over SSH with the session's own
  `k230-video-session stop` (agent trigger). The shell logged
  `recovery-video-stopped`, and the operator tapped back.
- Glare and blur leave the splash wording illegible in both clips. The
  operator reported that the states worked. A later automated pass, meant to
  take native captures of both splashes, timed out without seeing a new
  session, so no native image of the video copy exists.

## Not covered

- The window list's **loading** state.
- **Video ended** (end of file): the demo is 10:34 long.
- The board's temporary SSH access used for these triggers is runtime-only
  (a `/run` config, a bind-mounted `passwd` entry and a runtime firewall rule)
  and does not survive a reboot.
