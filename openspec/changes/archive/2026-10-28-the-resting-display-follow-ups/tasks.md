## 1. Idle timeout setting (from idle 4.1)

- [x] 1.1 Add the Settings row for the timeout (Off / 1 min / 5 min), persisted beside the
  existing settings and read by `shell-idle` at start. Needs its own Rust service request.
  Done (host): `idle-timeout` pref, `k230-idle-dimmer timeouts` read by `k230-swayidle`, and
  `shell-idle-timeout.path` restarts `shell-idle` on a change; not yet seen on the board (1.3).
- [x] 1.2 Host: unit tests for the pref read and the swayidle arguments it produces.
  Proof: `python3 -m pytest tests/ -k idle` and `cargo test` for the settings request.
  Done (host): `python3 -m pytest tests/test_idle_dimmer.py tests/test_exhibition.py` and
  `cargo test --lib` in `nix/rust-shell-client` (see the commit message for counts).
- [x] 1.3 Board, injected: pick 5 min; the panel dims at 150 s and turns off at 300 s; pick
  Off; neither happens in 6 min. Proof: journal `output * power` and DCS brightness lines.
  Done 2026-10-28, unattended board (build `q8k8w3mb…`), `docs/evidence/resting-display-follow-ups/README.md` § Idle timeout: 5 min dimmed
  at 146–152 s and turned off at 298–303 s; Off did neither in 366 s. Read from sysfs brightness
  and `get_outputs` power every 5 s, not from the journal. The row tap was injected.

## 2. HDMI unplug wake (from idle 4.2)

- [x] 2.1 The HDMI-unplug wake in `nix/touch-trackpad/src/shell_ipc.rs` powers the display on
  without reporting activity; make it report activity so the panel does not stay
  dim. Proof: `cargo test` in `nix/touch-trackpad`.
  Done 2026-10-28 (host): it sends `seat * cursor move 0 0` after `output * power on` (see
  design.md for why the dimmer is not called directly); `cargo test`: 51 + 2 passed, and the
  direct-mapping test asserts the new command order.
- [x] 2.2 Board: dim the panel, then unplug HDMI (operator); brightness returns to the saved
  value and the next dim comes a full timeout later.
  Done 2026-10-28, operator at the cable (build `whdjpxg9…`): the operator plugged HDMI in,
  let the panel dim, unplugged, and reported that brightness came back. The journal shows HPD
  disconnected at 19:02:07 followed by `output * power on` and `seat * cursor move 0 0`
  (`docs/evidence/resting-display-follow-ups/board/hdmi-unplug-journal.txt`). The full
  timeout before the next dim was not timed.

## 3. Decisions (from idle 4.3)

- [x] 3.1 Decide whether charging should defer idle off, and whether the wallpaper video should
  stop decoding while the display is off. Record the decision and any measurement here.
  Decided 2026-10-28, from source and the existing board measurement (no new measurement):
  - Charging does not defer off. "Idle on charger" already decides it: at Clock the clock
    screen keeps the display on while docked (`idle_dimmer.py`, `off` returns early while the
    card is up on the charger); at Sleep the person asked for off.
  - The wallpaper video stops decoding while the display is off. It did not: the decoder runs
    unless `should_decode` sees reduced motion or a fresh cover file, and the compositor
    writes that file only when it renders (`nix/card-shell/adapter.c`), which a powered-off
    output never does, so the file goes stale and reads as visible. The 2026-10-21 board trial
    measured a video wallpaper at 0.87 of a core on idle Home
    (`docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`). Built in 3.2.
- [x] 3.2 The wallpaper counts as covered while every connected DRM connector reports DPMS Off
  (`video_visibility::display_off`, polled with the cover file every 500 ms).
  Host, 2026-10-28: `cargo test --offline --lib video` in `nix/rust-shell-client`, 10 passed,
  including the new connector test. Board proof still needed: with a video background on
  Home, `swaymsg 'output * power off'`; within 1 s the shell journal shows the decoder paused
  and its ffmpeg child stops using CPU (`ps`), and power on resumes it.
  *Done 2026-10-28, unattended board run (`docs/evidence/resting-display-follow-ups/README.md` § Video decoding while the display is off): the state went `playing` → `paused-covered` and the ffmpeg decoder exited, 1.165 s after `swaymsg` started (0.61 s after its reply). Decoding resumed 2.5 s after power on. The status file and `/proc` stand in for the journal, which logs no pause.*

## 4. Clock screen follow-ups (from exhibition 5.1–5.5)

- [x] 4.1 Notification-count dot on the card (needs the broker count).
  Host 2026-10-28: `k230-exhibition` asks the broker socket for `history` on each minute
  redraw and draws a dot and the count under the date (`tests/test_exhibition.py`; host-only).
  Board proof: with the card up on the charger, `notify-send test` three times; within a
  minute `grim` of the panel shows the dot and 3, `dismiss-all` removes it, and `top` shows
  the card's CPU unchanged.
  Done 2026-10-28, board (build `q8k8w3mb…`), `docs/evidence/resting-display-follow-ups/README.md` § Notification dot: "● 3" with three
  events (`k230-notifications emit`, the broker CLI, in place of `notify-send`), none after
  `dismiss-all`; card CPU 60 ms vs 50 ms per 120 s.
- [x] 4.2 A separate Exhibition brightness, and a setting for the two-hour cap and the effect
  interval. Host done: Clock brightness / Clock effects / Clock limit rows, the dimmer applies
  the brightness at open and the card reads the other two at start (unit tests). Board proof:
  on the charger pick Full, idle 30 s, `cat $D/brightness` equals the pre-dim value while
  `get_tree` shows `k230-exhibition`; pick Half (about half) and Dim (about a quarter); pick
  Clock limit None and Clock effects Off and confirm no `ttfx` child in 6 min and no cap close
  in the journal, then restore the defaults.
  Done 2026-10-28, board (build `q8k8w3mb…`), `docs/evidence/resting-display-follow-ups/README.md` § Clock brightness: Full 148, Half 74,
  Dim 37 of 148; effects Off gave no `ttfx` in 360 s against `ttfx` at +11 s with 5 min;
  defaults restored. The limit check only shows no close in 6 min.
- [x] 4.3 Close the card on pointer-only activity (HDMI mouse) as well. Board proof with a
  mouse: the card closes and the app beneath gets nothing.
  Host, 2026-10-28: the card turns on any-motion reports (mode 1003) and motion is input, so a
  moved mouse closes it the way a press does; `needs_release` ignores motion reports
  (`tests/test_exhibition.py`, 20 passed). Board proof with a mouse still open.
  Injected board, 2026-10-28: one move of a uinput relative pointer closed the card, restored
  148 and returned focus to the terminal (`docs/evidence/resting-display-follow-ups/README.md` § Clock tile). A real mouse is still needed.
  Accepted 2026-10-28 by the operator without a real mouse ("consider it accepted or verify
  with faux mouse"); the proof is the injected uinput relative pointer above.
- [x] 4.4 A shade tile or a Home action to start the exhibition on demand.
  Host 2026-10-28: a "Clock" tile (last in the wide shade's grid) closes the shade and runs
  `k230-idle-dimmer exhibit-now`, which on the charger dims and opens the card with
  `--on-close ... resume`, so input restores brightness though swayidle never went idle. On
  battery the tile stays on the shade with a line saying it needs the charger (inert with
  feedback, not absent). Host-only: `tests/test_idle_dimmer.py`, `cargo test`.
  Board proof: on the charger, open the shade and tap Clock; the card shows and brightness
  reads a quarter in `$D/brightness`; one touch closes it without reaching an app and
  brightness returns to the saved value. Unplug and tap again: nothing starts.
  Injected board, 2026-10-28: the tile opened the card at 37 of 148 with focus; one touch
  closed it and restored 148 (`docs/evidence/resting-display-follow-ups/README.md` § Clock tile). The battery half (unplug, tap, nothing
  starts) still needs the operator.
  Operator 2026-10-28, charger unplugged: tapping Clock did nothing, which is the battery
  behaviour, but the battery message was not visible, so the tap looked dead. The tile now reads
  "Charger only", greyed, while no charger is online, and "Start" on the charger.
  Done 2026-10-28, injected board on battery (build `37nvncgk…`): the tile read "Charger only"
  greyed, a tap started nothing (brightness 148, no card) and showed "Clock needs the charger"
  (docs/evidence/resting-display-follow-ups/README.md § Operator at the cable).
- Dropped, not performed: 4.5 Camera (exhibition 4.7, moved 2026-10-28 when the operator reassigned the webcam;
  optional, gates nothing): the webcam on the panel records a clock minute change, one
  position drift and one effect. Look at consecutive raw frames first. Camera evidence, not
  glass, not injected.
  *The user dropped this on 2026-10-28 ("no recording"). No camera evidence exists. The task was never performed and is not ticked.*

## 6. Defects found on the board, 2026-10-28

- [x] 6.1 Restarting `shell.service` while the panel is dimmed loses the dimmer's state, and the
  new session dims again from the dimmed value: 37 went to 9, and a wake restored only 37
  (`/run/shell/idle-dimmer.json` read `{"saved": 37, "dimmed": 9}`). Keep the state across a
  shell restart, or restore the saved brightness when `shell-idle` stops. Proof: restart the
  shell while dimmed, wake, and read `cat $D/brightness` back at the pre-dim value.
  *Done 2026-10-28, injected on the board: the state moved to `/run/k230-idle` and `shell-idle` resumes on start; 37 → 148 after the restart, without a wake.*
- [x] 6.2 An exhibition card stays alive behind other cards when focus moves without input
  (`swaymsg focus`, a surface opening): `get_tree` kept `k230-exhibition` after the panel was in
  use again. Close it whenever it loses focus. Proof: open it, move focus by IPC, and check
  `get_tree`.
  *Done 2026-10-28, injected on the board: `docs/evidence/idle-dim/README.md` § Follow-up defects.*

## 5. Closeout

- [x] 5.1 Archive when every task above is done, or after an explicit, user-approved split.
  Proof: `openspec validate the-resting-display-follow-ups --strict`.
