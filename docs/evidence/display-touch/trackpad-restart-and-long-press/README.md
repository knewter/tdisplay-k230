# HDMI trackpad: first swipe after a restart, and long two-finger presses (board)

Change: `openspec/changes/the-hdmi-trackpad-survives-restarts-and-long-two-finger-presses`.
Evidence class for everything here: injected raw touch + shell/daemon log +
grim. No finger touched the glass.

## Method

`tools/fake-touchscreen.py` creates a uinput protocol-B touchscreen with the
GT9895's axis ranges. `tools/trackpad-fake-run.sh` starts a second
`k230-touch-trackpad` instance (the installed binary, `--device=` pointed at
the fake panel, `--log-events`). That exercises the real gate, relay,
virtual touchpad, libinput, compositor and shell path. The service's own
instance keeps serving the real panel. Pointer placement used
`tools/board-pointer.py`.

## Before the fix (system `4ad02cm5…` and earlier, 2026-10-15)

- 22:48:36: the operator's first two-finger swipe after a live deployment
  logged `k230-touch-trackpad: shell IPC phase=begin error=BrokenPipe` and
  was dropped.
- A 1 s still two-finger press with the cursor on a widget produced no
  secondary click on page 1 or page 2. The daemon output a valid two-finger
  down and up, but with the source timestamps 1 s apart, which is past
  libinput's tap timeout.

## After the fix (system `c2wxyv7h…`, deployed live 2026-10-15)

1. Restart (with the first fixed daemon build, `4sr6kyyw…`, which has the same
   IPC code): a fake-panel instance swiped, then `systemctl restart
   shell.service` restarted sway, then the same instance swiped again. Its
   log shows `shell IPC phase=begin error=BrokenPipe` followed by
   `shell fingers=2 accepted=true`, and
   `first-swipe-after-sway-restart-page2-1280x800-grim.png` shows Home on
   page 2.
2. Cursor on the Clock, `hold2 0.6 0.3 1000` (two still fingers for 1 s):
   the shell logged `home-widget-secondary-click` and
   `long-two-finger-press-clock-1280x800-grim.png` shows rearrange mode.
3. Done, then `swipe2 0.5 0.15 0.5 0.85 400` (accepted, Home to page 2),
   cursor on Weather, `hold2 0.6 0.3 1000`: `home-widget-secondary-click`,
   with the Weather badge visible in
   `long-two-finger-press-page2-after-swipe-1280x800-grim.png`.
4. Cursor on Done, one-finger `tap`: `pointer-down`, `pointer-up`, and
   rearrange mode closed.
