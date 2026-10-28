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
supply. The undocked reading is under "Charger cable runs" below.

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

## Charger cable runs (tasks 4.1, 4.3, 4.5 unplug half)

Times in this section are the board's local time (CDT, UTC-5), as the
journal and the logger print them. The operator pulled and replugged the
cable on request; nobody touched the panel during the timed parts. Build
`3vk5qy3a…` (commit `8352919b`) throughout, test-activated. Logger:
`plugwatch.sh.txt`, a sleep-paced 1 s loop on the board reading each supply's
`type`/`online` and the backlight, plus `get_outputs` power and a
`k230-exhibition` count from `get_tree` every third sample. Evidence class:
injected board, with the operator at the cable (not glass, not camera).

**First unplug, unlogged** (`unplug-while-exhibiting-journal.txt`). The card
opened at 16:01:46 (brightness 148 to 37); at 16:03:49 sway was told
`output * power off` and the panel went to brightness 0, with no other idle
step due. A wake followed at 16:03:53 and, after the cable went back, a new
card at 16:04:55. The unplug moment was not recorded, so no latency is
claimed from this run.

**Battery, preference Clock** (`battery-idle-no-exhibition.txt`). Charger out
(`bq25890-charger-0/online:0`, type USB; `bq27220-0` is the Battery and has
no `online` file). A tap at 17:20:13 closed the card (brightness 148) and left
the Clock app in front; then no input. 17:20:43 (30 s) brightness 37 and no
`k230-exhibition`; 17:21:13 (60 s) `output * power off`, the logger reading
power `false`, exhibition 0, at 17:21:16 (63 s after the last input).

**Unplug while exhibiting, logged** (`replug-then-unplug-while-exhibiting.txt`).
Cable in at 18:01:06 (display woke), card at 18:01:37. Charger `online` was
1 at 18:01:50.57 and 0 at 18:01:53.08. `output * power off` at 18:02:02;
logger power `false`, exhibition 0, at 18:02:04. Unplug to blank: 9–11.5 s,
under the 15 s bound. The power-key half of 4.5 was not run.

The cable then stayed out: the battery policy warned at 7 % (18:24:44),
5 % (18:31:14) and critical (18:34:45), and powered off cleanly at 18:35:52.
Replugging booted the boot default (`qh3i7b3f…`) at 19:28:26; `3vk5qy3a…`
was test-activated again and the shell restarted at 19:30:35.

**Charger in, preference Sleep** (`sleep-preference-on-charger.txt`).
`sleep` written to `/var/lib/k230-shell-prefs/idle-on-charger` at 19:30:55,
no input after the shell restart. 19:31:09 brightness 37, no exhibition;
19:31:39 `output * power off`, logger power `false`, exhibition 0. The file
was then removed (default Clock again).

The webcam was low and side-on to the panel during these runs; its frames
show reflections, not the clock, so there is no camera record (4.7).

## Operator glass report (task 4.8)

Evidence class: glass, operator report (not injected, not camera). The
operator used the board on 2026-10-27 while build `3vk5qy3a…` (commit
`8352919b`) was test-activated (13:09–18:35 and from 19:30 CDT) and the
exhibition was showing. Asked on 2026-10-28 whether they had tapped the
exhibition and pressed a key, with the app beneath not reacting and the prior
card returning, they answered: "it seems all good", "it works fine", and, to
that exact question, "yup go". The report does not say which key or which
app was beneath; the injected runs above cover those details.

## CPU against a no-card baseline (task 4.6)

`cpuab.sh.txt` ran on the board on 2026-10-28, build `3vk5qy3a…`, charger in.
It stopped `shell-idle` so the display stayed on with no idle steps, waited
60 s, then took three 60 s `/proc/stat` samples with `cpu.sh`. Output is in
`cpu-baseline-vs-clock.txt`.

| Window (UTC) | State | System busy |
|---|---|---|
| 17:43:24–17:44:24 | terminal only, no card | 7.20 % (486/6752) |
| 17:45:15–17:46:15 | exhibition up, clock-only (exec 17:44:24, no `ttfx` running) | 5.78 % (390/6752) |
| 17:46:35–17:47:35 | card killed, no card again | 6.82 % (459/6731) |

The clock-only phase lies inside the spread of the two no-card samples, so
the card's increment is below what these 60 s samples can resolve. That bound
is roughly ±1 %. The task's pass line of under 1 % for the whole system is
not met, because the system floor without the card is 6–7 %. The `ps` `%CPU`
column is a lifetime average and is not used here. A rerun at 17:38Z did not
launch the card (empty card path) and is not counted.

On 2026-10-28 the operator changed the pass line to the clock-only phase's
increment over a no-card baseline. Under that line the result passes: the
increment is not distinguishable from zero, and is at most about 1 %.

**Across one effect** (`cpueffect.sh.txt`, `cpu-effect-window.txt`). The card
was exec'd at 17:54:00Z with `shell-idle` stopped. A 1 s `pgrep -x ttfx` log
shows ttfx running 17:54:12–17:54:19Z, so the effect ended within 20 s. Over
the 45 s window from exec, which includes card start-up, the system was
21.87 % busy (1092/4994 jiffies). The effect does not pin the CPU, so the
frame rate and the effect rotation are unchanged.

## Operator reports: keyboard-base key and power key (tasks 4.4, 4.5)

Evidence class: glass, operator report, build `3vk5qy3a…`, 2026-10-28.
With the exhibition up, the operator pressed Space on the physical keyboard
base and reported: "i pressed space and the terminal came up" (the terminal
was the prior card, so this is the prior card, not Home). For the power-key
half of 4.5 (blank while exhibiting, then wake), they reported "power works
fine". Neither was read alongside `get_tree` or a logger.
