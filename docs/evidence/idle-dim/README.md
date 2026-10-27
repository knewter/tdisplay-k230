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
