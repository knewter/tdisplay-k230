# The display dims and sleeps when idle: board evidence

Change: `the-display-dims-and-sleeps-when-idle`. Evidence class: board, read
over protected SSH, with wake taps injected through `/var/tmp/ui.py`. No
webcam check and no glass interaction yet.

Build `/nix/store/prk64sjwhxf7r1lfgw1vbjxfssk0lx3r-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `2cc67965`), test-activated, `shell` restarted 2026-10-27 ~03:39Z.
`D` is the panel's `/sys/class/backlight/*` directory, `SM` is `swaymsg` on
the shell's socket.

## Dim and off (tasks 3.1, 3.2)

After the last injected input at ~03:39:30Z, unattended:

    t0  03:40:39  brightness 37  "power": false     shell-idle active
    t36 03:41:15  brightness 37  "power": false
        idle-dimmer.json {"saved": 148, "dimmed": 37, "off": true}

After a wake tap at 03:41:57Z (below), unattended again:

    t0  03:42:01  brightness 148 "power": true    (idle-dimmer.json removed)
    t32 03:42:33  brightness 37  "power": true    (dimmed to 148 // 4)
    t62 03:43:03  brightness 37  "power": false
        idle-dimmer.json {"saved": 148, "dimmed": 37, "off": true}

The terminal card stayed in `get_tree` throughout (`app_id k230-terminal`).

## Wake by touch (part of task 3.4)

- 03:41:57Z, panel off: injected tap at (616, 300) on Home's empty area. The
  compositor logged `Handling command 'output * power on'`, brightness read
  148 and power true.
- 03:43:18Z, panel off (`"power": false` read just before): injected tap at
  (616, 170), on Home's Video icon. `after-wake-tap-on-video.png` is grim
  4 s later: Home, with Video not launched. `get_tree` listed only
  `k230-terminal` and no `mpv` process ran, so the tap that woke the panel
  was not delivered.

Limits: the taps are uinput touches, so this shows that Sway receives touch
on the off output for injected input; a webcam check that the physical panel
lights, and a glass tap, are still open. The power key (3.3), video and
Timer inhibit (3.5), slider while dim (3.6) and base key (3.7) were not run.

## Inhibit (task 3.5), build `iw96wr9d…` (commit `93dc4efb`), 2026-10-27

- **Timer focused:** last injected input 15:13:39Z; brightness 148 and power
  true at 15:14:19, 15:14:41, 15:15:02 and 15:15:22 (103 s), while the
  Timer counted down and expired.
- **Video focused:** Video opened from Home at 15:28:31Z; brightness 148 and
  power true at 15:29:08, 15:29:43 and 15:30:09. `get_tree` showed
  `k230-video-software` focused with `inhibit_idle: true`;
  `video-focused-playing.png` is the playing window (Big Buck Bunny test
  clip).
- **Back at Home (fails):** after LILYGO+Tab and a tap on the footer at
  15:30:53Z, Home showed with nothing focused, but brightness stayed 148
  with power true at 15:31:27 and 15:31:57, and `get_tree` still reported
  the unfocused video's `inhibit_idle: true`. Sway re-evaluates inhibitors
  only on some transactions, and the card shell's Home restore did not
  trigger one. Commit after `5a1da698` calls
  `sway_idle_inhibit_v1_check_active()` at the end of `restore()`; the
  Home part of 3.5 is to be re-run on that build.

## Inhibit at Home, fixed (build `zs05li2k…`, commit `be58ff02`)

The `restore()` re-check alone did not help (build `f0zn5j8l…`, 15:41Z: the
unfocused video still reported `inhibit_idle: true`). mpv holds its own
application idle inhibitor, which Sway counts while it believes the view is
visible. `be58ff02` makes that check also ask `card_shell_view_hidden()`.

Run at 15:45-15:47Z: Video playing, a Timer started, then Home through the
overview footer (last input 15:46:19Z). `get_tree`: video and Timer
unfocused, both `inhibit_idle: false`. Brightness 37 at 15:46:55, and the
compositor logged `output * power off` at 15:47:17.

## Slider while dim (task 3.6, build `3vk5qy3a…`, 2026-10-28)

Injected board run, `board/slider-while-dim.sh.txt` with its output in
`board/slider-while-dim.txt`. The charger was in, so the idle-on-charger
preference was set to `sleep` for the run, which kept the exhibition from
opening on dim. It was removed afterwards. An injected key woke the panel
(148). At 18:15:42Z the panel was dimmed to 37, with state `saved 148,
dimmed 37`. `k230-settings brightness 80` then wrote 204. This is the
command the shade's Brightness request runs (`ServiceRequest::Brightness`
in `service_data.rs`). Dragging the slider on the glass was not used,
because the touch would itself wake the panel. An injected key at 18:15:51Z
woke it: brightness stayed 204 and did not return to 148, and the state file
was cleared. Brightness was then set back to 58 % (148).

## Glass wakes: finger, keyboard base, power key (tasks 3.3, 3.4, 3.7)

Evidence class: glass. The operator did the touching and said what they did.
Each input is timed by `board/wakelog.py.txt` and the journal, in
`board/glass-wakes.txt` (CDT). Build `3vk5qy3a…`, 2026-10-28. The charger
was in, and the idle-on-charger preference was `sleep` from 13:43:49 to
13:50, so the panel went dark instead of opening the exhibition. Each wake
started from `output * power off` (brightness 0).

- **Finger (3.4).** Dark from 13:44:24. Touch down at 13:44:32.967, and
  `output * power on` at 13:44:32.966. Brightness went to 37, then 148 (the
  prior value) at 13:44:34. The terminal was in front and was focused after
  the wake. The no-delivery part rests on the headless proof
  (`headless/README.md`, 0 probe events for the waking sequence) and on the
  injected tap on Home's Video icon above. It was not observed for this
  glass tap. No webcam was used: the operator reassigned it on 2026-10-28.
- **Keyboard base (3.7).** Dark from 13:45:34. A base key went down at
  13:45:49.687 and the output came on at 13:45:50.49, with brightness 148.
  The key is accepted to reach the app.
- **Power key (3.3).** Dark from 13:46:50. Power came on at 13:49:10.51,
  with no touch or base key logged, and the operator reported pressing the
  power key. `wakelog.py` cannot read the PMU key, because the power-key
  daemon appears to hold it exclusively. Brightness went to 148, equal to
  the prior value. With no further input, it dimmed to 37 at 13:49:42.48
  (32 s) and the output went off at 13:50:12.48. This shows the re-arm.

The preference file was removed afterwards, so the default is Clock again.

## Follow-up defects 6.1 and 6.2 (build `lrx0026r…`, 2026-10-28)

Evidence class: injected over SSH on the board. Nobody touched the glass.

- **6.1, shell restart while dimmed.** swayidle had dimmed the panel to 37
  on the charger. The dimmer's state now lives in `/run/k230-idle`, which
  `shell.service` does not own, and `k230-swayidle` runs `resume` before
  starting swayidle. After `systemctl restart shell` the state still read
  `{"saved": 148, "dimmed": 37}`; 25 s later the brightness was back at 148,
  and the state file had been cleared
  ([`board/restart-while-dim.txt`](board/restart-while-dim.txt)). Before the
  fix, the same restart took the panel from 37 to 9.
- **6.2, exhibition loses focus without input.** The card now turns on
  terminal focus reporting (mode 1004) and quits on a focus-out report.
  [`board/focus-loss-closes-exhibition.sh.txt`](board/focus-loss-closes-exhibition.sh.txt)
  opened the card, then moved focus with `swaymsg '[app_id="k230-terminal"]
  focus'`. Within 4 s, `get_tree` no longer listed `k230-exhibition`
  ([`board/focus-loss-closes-exhibition.txt`](board/focus-loss-closes-exhibition.txt)).
  The one process still counted afterwards was swayidle, whose command line
  contains `--exhibit-exec`; `ps` showed no card process.
  The card did not quit on its own focus-in report when it opened.
