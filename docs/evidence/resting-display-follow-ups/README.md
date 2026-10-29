# Resting display follow-ups on the board, 2026-10-28

Change: `openspec/changes/the-resting-display-follow-ups/`. Build
`q8k8w3mb…` (test-activated; boot default was `lrx0026r…`), landscape panel,
on the charger throughout. The webcam was reassigned to other work, so there
is no camera evidence; nobody touched the glass during these runs.

Evidence classes:
- **unattended board:** scripts over SSH with no input;
- **injected:** `ui.py` uinput touch and keys, plus `mouse.py`, a uinput
  relative pointer that libinput treats as a USB mouse;
- **native `grim`** captures.

Window state comes from [`board/state.sh.txt`](board/state.sh.txt):
brightness, focused `app_id`, whether `k230-exhibition` is in `get_tree`, and
the dimmer state in `/run/k230-idle`.

## Idle timeout (tasks 1.1, 1.3)

- **Settings row, injected tap.** Settings shows Idle timeout, Clock
  brightness, Clock effects and Clock limit at their defaults
  ([`settings-idle-rows.png`](board/settings-idle-rows.png)). One tap on Idle
  timeout wrote `5m`. `shell-idle-timeout.path` restarted `shell-idle` 2 s
  later, and swayidle ran `timeout 150 … timeout 300`
  ([`idle-timeout-tap.txt`](board/idle-timeout-tap.txt)).
- **Timing, unattended** ([`idletime.sh.txt`](board/idletime.sh.txt),
  [`idle-timeout-arms.txt`](board/idle-timeout-arms.txt); 5 s samples).
  "Idle on charger" was set to Sleep for this run, so the clock screen did not
  hold the display on, and was restored to Clock afterwards.
  - With 5 min, the panel dimmed between 146 s and 152 s (148 → 37), and the
    output went off between 298 s and 303 s.
  - With Off, the wrapper ran no swayidle, and brightness stayed at 148 with
    the output on for all 366 s.

## Clock tile, touch and mouse (tasks 4.4, 4.3), injected

- **Clock tile.** The shade's Clock tile
  ([`shade-clock-tile.png`](board/shade-clock-tile.png)) closed the shade and
  opened the card with focus. Brightness went from 148 to 37, and the card
  stayed up 14 s with no input.
- **Mouse.** One `mouse.py move 6 3 5` closed the card. Brightness returned
  to 148 and the terminal was focused again
  ([`clock-tile-mouse.txt`](board/clock-tile-mouse.txt),
  [`mouse.py.txt`](board/mouse.py.txt)).
- **Touch.** A card opened the same way closed on one touch, with brightness
  back to 148 and the terminal in front
  ([`clock-tile-touch.txt`](board/clock-tile-touch.txt)).
- **Not yet done:** a real USB or HDMI-side mouse, and the tile on battery,
  which needs the charger unplugged.

## Notification dot (task 4.1)

- **Showing the count.** Three events went in with `k230-notifications emit`
  (the broker's own CLI, in place of `notify-send`). The card opened from the
  tile and showed "● 3" under the date
  ([`clock-dot-3.png`](board/clock-dot-3.png)).
- **Clearing it.** After `dismiss-all` the count was 0, and the next minute
  redraw had no dot ([`clock-dot-0.png`](board/clock-dot-0.png)).
- **CPU.** Over each 120 s window, the card used 60 ms with the dot and 50 ms
  without, and foot used 20 ms both times
  ([`dotcpu.sh.txt`](board/dotcpu.sh.txt), [`dotcpu.txt`](board/dotcpu.txt)).

## Clock brightness, effects, limit (task 4.2), unattended plus injected mouse

This ran on the idle path: Idle timeout 1 min, "Idle on charger" at Clock,
pre-dim brightness 148. Each card opened 33–37 s after the last input.

- **Brightness**
  ([`clockprefs.sh.txt`](board/clockprefs.sh.txt),
  [`clock-brightness-levels.txt`](board/clock-brightness-levels.txt)):

  | Clock brightness | Panel with the card up |
  |---|---|
  | Full | 148 |
  | Half | 74 |
  | Dim | 37 |

  A mouse move restored 148 each time. With Full the dimmer writes no state,
  since there is nothing to restore.
- **Effects and limit**
  ([`effectsoff.sh.txt`](board/effectsoff.sh.txt),
  [`effects-off.txt`](board/effects-off.txt)):
  - Control, Clock effects 5 min: `ttfx` was running 11 s after the card
    opened.
  - Clock effects Off with Clock limit None: no `ttfx` process in 360 s, and
    the card was still up.
  - The limit check is weak, because the default cap is 2 h. The None-to-no-cap
    mapping is covered by the host tests.
  - The defaults were restored at the end.
- **Discarded measurement.** The first effects-off attempt matched the card's
  wrapper with `pgrep -f`, so its "child" samples were the card itself. That
  part is trimmed from `clock-brightness-levels.txt`.

## Operator at the cable (tasks 2.2, 4.4), build `whdjpxg9…`

- **HDMI unplug (2.2).** The operator plugged HDMI in, let the panel dim,
  unplugged it, and reported that brightness came back.
  [`hdmi-unplug-journal.txt`](board/hdmi-unplug-journal.txt) shows HPD
  disconnected at 19:02:07, then `output * power on` and the activity signal
  `seat * cursor move 0 0` 0.5 s later.
- **Clock tile on battery (4.4).** The operator reported that tapping Clock
  "never does anything". On the charger, an injected tap on the same build
  opened the card at 37 of 148 with focus. On battery, not starting is the
  specified behaviour, but the "needs the charger" message was not visible.
  The tile now reads "Charger only", greyed, while no charger is online.
- **Mouse (4.3).** The operator accepted the injected uinput mouse in place of
  plugging in a real one.
- **Clock tile on battery, after the change** (build `37nvncgk…`, charger
  `online=0`, injected tap). The shade shows the tile greyed as "Charger
  only" ([`clock-tile-battery.png`](board/clock-tile-battery.png)).
  - A tap on it started nothing: brightness stayed 148, no
    `k230-exhibition`, and no card exec in the journal
    ([`clock-tile-battery.txt`](board/clock-tile-battery.txt)).
  - The shade showed "Clock needs the charger"
    ([`clock-tile-battery-tapped.png`](board/clock-tile-battery-tapped.png)).
    The first wording, "The clock screen needs the charger", was cut off at
    that width and was shortened.
