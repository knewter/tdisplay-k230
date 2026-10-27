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
