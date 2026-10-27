# Do Not Disturb: board evidence

Evidence class: board, injected touch and keys through `/var/tmp/ui.py`,
notifications injected with `busctl` on the shell bus, native `grim`.
Not glass. Build `/nix/store/f0zn5j8l5a7b7a2j26cwvpqkahg61rsv-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `7a58eb53`; Quiet runs) and
`/nix/store/zs05li2kyrnlaz3a6b4aa8z1xianxnl0-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `be58ff02`; restart and Timer runs), 2026-10-27.

    N(){ busctl --address=unix:path=/run/shell-bus/bus call org.freedesktop.Notifications \
      /org/freedesktop/Notifications org.freedesktop.Notifications Notify \
      susssasa{sv}i Probe 0 '' "$1" body 0 <hints> 5000; }

- 15:43:15Z, Quiet off: "First ordinary" showed its banner.
- `shade-quiet-off.png`, then a tap at (388, 201): `shade-quiet-on.png`
  shows the tile "Quiet / On" and the moon on the status line;
  `/var/lib/k230-shell-prefs/do-not-disturb` read `on`.
- 15:43:36Z "Quiet ordinary": no banner 1.2 s later
  (`quiet-ordinary-no-banner-top.png`); history listed it.
- 15:43:39Z "Quiet critical" (urgency 2): no banner either. The adaptor
  records D-Bus critical as `important` from a delegated source, and the
  design lets only critical events and trusted non-delegate important
  events break through, so this is the specified result.
- After `systemctl restart shell` the file still read `on` and the shade
  showed "Quiet / On".
- 16:02:22Z, Timer started for 1:00 with Quiet on; at 16:03:22Z the banner
  "Timer / Timer finished" showed (`quiet-timer-breaks-through.png`).
- Quiet was turned off again by the tile at ~16:05Z; the file read `off`.

## Settings row against the tile (task 3.3), build `zs05li2k…` (commit `be58ff02`)

`settings-row-and-tile-agree.png`, four native captures, injected taps:
16:49:02Z the Settings "Do Not Disturb" row toggled to On; 16:49:05Z the shade
opened afterwards shows the moon and "Quiet / On"; 16:49:07Z the tile toggled
off reads "Quiet / Off"; 16:49:10Z Settings reopened shows the row "Off". The
state file read `off` at the end. The red "dismissed" line in the shade
captures is the leftover message fixed later in commit `308a7091`.

Not run: the reboot (3.4), the largest vision step on the board (3.2), the
base-battery critical event.
