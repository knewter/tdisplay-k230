# Exhibition clock: board evidence

Board, build `fas6gqhw…` (commit `a532501f`), test-activated with
`switch-to-configuration test` and `systemctl restart shell`, 2026-10-27.
Evidence class: injected board (no touch during the idle runs), native `grim`.

## Build gate (task 3.1)

Read from the landscape-hdmi closure the board runs
(`.#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi`, not the
`.#nixosConfigurations.k230` attribute the task names):
`sw/bin/k230-exhibition` execs `…-k230-term-apps/lib/k230-term-apps/k230_exhibition.py`;
`k230-swayidle` (from `shell-idle.service`) passes
`--exhibit-exec /nix/store/lgls5dp6…-k230-exhibition-card`, and that script
names `/nix/store/9cnvvxgi…-ttfx-riscv64-unknown-linux-gnu-0.5.1/bin/ttfx`,
the task 1.1 path.

## Charger supply, docked (task 4.1, half)

`grep -H . /sys/class/power_supply/*/type /sys/class/power_supply/*/online`
at 17:12:57Z with the charger connected:

    /sys/class/power_supply/bq25890-charger-0/type:USB
    /sys/class/power_supply/bq27220-0/type:Battery
    /sys/class/power_supply/bq25890-charger-0/online:1

The battery gauge has no `online` file; the charger is the only non-Battery
supply. The undocked reading needs the operator to pull the cable; not done.

## Docked idle opens the clock (task 4.2)

A swallowed wake tap, then no input from 17:14:30Z. At 17:15:40Z (70 s):
brightness 37, from 148 (a quarter); `get_outputs` power `true`; `get_tree`
lists `k230-exhibition` and `k230-terminal`; `/run/shell/exhibition.pid`
present. `docked-idle-70s-clock.png` is the capture: block-digit clock and
the date on black. The preference file was absent (default Clock).

## CPU (task 4.6, not passed)

`cpu.sh.txt` (`/proc/stat` busy/total, the task's command) over
17:16:05–17:17:05Z, clock-only: **3.75 %** system busy (255/6798 jiffies).
That is the whole system, over the task's 1 % line, so 4.6 stays open.

`pcpu.sh.txt` attributes utime+stime per process (sleep-paced, 60 s):
17:17:22–17:18:25Z, clock-only, of 7273 jiffies: sway 62 (0.85 %),
notification_center.py 22, keyboard_based.py 21, the two
foot_color_session.py helpers (one per foot window) 20 and 19, the sampler's
own sh 18, k230-shell-rust 14. The exhibition's python3 (pid 35217) and its
foot (35213) are not in the top twelve: under 4 jiffies each (<0.05 %).

Across the 17:20:08Z effect (17:19:57–17:20:45Z, 5560 jiffies): sway 95
(1.71 %), the exhibition's foot 38 (0.68 %); ttfx had exited before the end
snapshot, so its own time is not in this table.

A baseline with no card was not sampled, so the card's share of the system
figure is inferred from the per-process table, not measured as a difference.

## First effect: top left, cursor shown (fixed in `8352919b`)

`first-effect-top-left-cursor.png`, twelve captures 17:30:07–17:30:17Z
(`grim -t jpeg` about every 0.9 s; `pgrep -x ttfx` true for nine of them):
the 12:30 clock, then the five-row `#` banner sliding in at the top left
with a gradient, a cursor block under it at the end. ttfx fitted its canvas
to the text at the default `sw` anchor and restored the cursor on exit.

## Centred block banner (build `3vk5qy3a…`, commit `8352919b`)

`centred-k230-expand-effect.png`: 24 captures 17:40:10–17:40:26Z
(`grim -t jpeg`, about 0.7 s apart; `pgrep -x ttfx` true for frames 13–16).
The clock, then the `expand` effect growing the six-row block "K230" from the
centre, the finished banner held, then the clock back.
`centred-k230-banner-174021.jpg` is one full frame of the held banner,
centred, white-to-blue gradient, no cursor.

## Touch and key over an app (task 4.4, tap and injected key; base key not run)

Readings are `date`, backlight `brightness`, and the app ids and focus in
`swaymsg -t get_tree` order (a `"focused": true` precedes its node's app id).

- 17:40:51Z, card over the terminal, brightness 37, exhibition focused. An
  injected tap at (616,300); at 17:40:57Z brightness 148, no exhibition,
  terminal focused.
- Files opened from the Home dock, left on its Home folder, no input.
  17:42:24Z: brightness 37, `k230-exhibition` focused above
  `org.gnome.Nautilus`. An injected tap at (80,232), where Files' "Starred"
  row is; 17:42:31Z: brightness 148, the exhibition gone, Nautilus focused,
  and `tap-closes-card-over-files.png` shows Files still on Home with Starred
  not selected: the touch did not reach the app.
- 17:43:33Z the card was up again over Files (brightness 37). The injected
  uinput keyboard pressed `j`; 17:43:40Z brightness 148, the exhibition gone,
  Nautilus focused, and Files showed no type-ahead search (the key did not
  reach it).

The card in front afterwards is the prior card, not Home. A key from the
physical keyboard base was not pressed, so 4.4 stays open for that.

One tap at 17:35:06Z, two seconds after the card's `exec` at 17:35:04Z, did
not close it; that card was probably not mapped yet. Not investigated further.
