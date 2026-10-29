# Apps and timers can alert the user: board evidence

Change: `apps-and-timers-can-alert-the-user`. Evidence class: board, with the
notifications injected over protected SSH (no finger, no operator on glass).

## Build

Test-activated `/nix/store/dhmp8mdiii13xynd0cqyhjr5mkad0mah-nixos-system-nixos-26.11.20260919.20b1ddd`
(master `8b4f7d73`), then `systemctl restart shell`. Its cross-build of the
landscape system, including `shell-notification-dbus.service` and `jeepney`,
succeeded on the host (task 2.1).

## D-Bus Notify (tasks 3.1, part of 3.2), 2026-10-27T03:37:59Z

`notify-send` (libnotify) is not on the image, so the client was `busctl`,
which sends the same `org.freedesktop.Notifications.Notify` call:

    A=unix:path=/run/shell-bus/bus
    sudo -u shell busctl --address=$A call org.freedesktop.Notifications \
      /org/freedesktop/Notifications org.freedesktop.Notifications Notify \
      susssasa{sv}i "Probe" 0 "" "Probe" "body" 0 1 urgency y 2 5000
    sudo -u shell busctl --address=$A call ... Notify susssasa{sv}i \
      "Shell" 0 "" "Impostor" "body" 0 0 5000
    sudo -u shell busctl --address=$A status org.freedesktop.Notifications
    sudo -u shell k230-notifications history

Results (bodies elided):

- The bus name's owner is `python3.14` running
  `.../python3-...-env/bin/python3 .../notification_dbus.py`, the adaptor.
- `Probe`, urgency critical: history `source "Probe"`, `priority "important"`,
  `dismissible true`. `banner-critical.png` is the preview, cropped to the
  banner.
- `Shell` claim: history `source "Application"`. `banner-shell-claim.png`.
- An earlier probe, `Probe App` with no hints, read `source "Probe App"`,
  `priority "ordinary"`. Before `8b4f7d73` the same call was recorded as
  `Unknown source`, because the trust key named the env wrapper rather than
  the base interpreter that `/proc/PID/exe` reports.

The banner reads "Notification / New notification" because the broker treats
every adaptor notification as private (`runtime/notifications`); the source
and summary appear in the shade's list, not the banner.

## Timer with the card closed (part of task 3.4)

On the earlier build `dnm09im6…`, a 1-minute Timer started and its card closed
posted one history entry, `source "Timer"`, `priority "important"`,
`summary "Timer finished"`, timestamp 1793071630 (2026-10-27T03:27:10Z), and
the detached helper exited. No banner was captured and the reopen-before-expiry
case was not run, so task 3.4 stays open.

## Timer, 2026-10-27 (tasks 3.3, 3.4)

Build `/nix/store/iw96wr9dykpm19a3zhjfrh9rgjw1xijs-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `93dc4efb`), test-activated. Timer launched with the drawer keys
(LILYGO, `ti`, Enter), set to 1:00 with four `-` presses, started with Space;
all injected. `grim` ran once a second around the expiry.

- **Card open:** started 15:19:52Z; the banner "Timer / Timer finished" with
  the Timer icon was on screen from 15:20:53Z (`banner-timer-card-open.png`).
- **Card closed:** started 15:21:40Z, card closed with the overview's
  Backspace; the same banner at 15:22:40Z (`banner-timer-card-closed.png`);
  history held one Timer entry, `important`, 15:22:40; the detached helper
  process was gone afterwards.
- **Reopen before expiry:** started 15:23:24.6Z, closed, Timer reopened at
  15:23:54Z, which showed `00:31 Running` (`timer-reopened-resumes.png`); at
  expiry history held one Timer entry, 15:24:24. Timer alerts carry a tag
  that replaces the previous entry, so the count alone cannot exclude a
  second post that replaced the first.

## Idle cost (task 3.5)

`/proc/<MainPID of shell-notification-dbus>/stat` utime+stime over
15:17:09-15:18:09Z with no timer running: 86 ticks before and after
(CLK_TCK 100), a delta of 0.

## A GTK app's notification (task 3.2), 2026-10-29

Build `/nix/store/1lpsniwgxxz9bqk83261lbb0k8q6hpqz-nixos-system-nixos-26.11.20260919.20b1ddd`,
the boot default. Evidence class: the board, with the client run over SSH as
the `shell` user and the screen kept awake with injected taps. Nobody touched
the glass.

`scripts/gnotify_probe.py` is a `Gio.Application`
(`org.k230.GNotifyProbe`) that calls `send_notification` (that is,
`g_application_send_notification`) with a title, a body and
`G_NOTIFICATION_PRIORITY_HIGH`, on the shell's session bus
(`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus`). No
`org.gtk.Notifications` service runs, so GLib used its
`org.freedesktop.Notifications` backend, which the adaptor serves.

- Every send produced a history entry with `source "GNotifyProbe"`,
  `icon "org.k230.GNotifyProbe"`, the title and body, `priority "ordinary"`
  and `dismissible: true`. GLib sends `HIGH` as urgency normal, and only
  urgency critical maps to `important`.
- Send at 20:54:02Z, history id 11 at 20:54:03Z: the shell logged
  `notification-banner-map-request` a second later and unmapped the banner
  5 s after that. `board/banner-gnotification.png` is a grim capture from 2 s after
  the send: "Notification / New notification" over Files, the private form
  every adaptor event takes. `board/shade-gnotification-history.png` is the shade
  with the earlier GNotifyProbe entries listed.
- `busctl … Notify` with app name `Shell` (summary "Impostor"): history id 12,
  `source "Application"`.

Two things held back banners during this run:

1. **Do Not Disturb** was on (`/var/lib/k230-shell-prefs/do-not-disturb`
   read `on`, written 00:32 local). Ordinary events do not break through, which
   is correct. Quiet was turned off with the shade tile for the test.
2. **A shell bug.** After the shade had been open, no banner appeared,
   whatever the priority: the broker returned a preview, but the shell never
   logged `notification-banner-map-request`. `sync_banner` hides the banner
   while `route == Route::Shade`, and `hide()` unmaps the overlay without
   resetting `route`. So after the shade closes, by gesture or by
   `--surface hide`, the shell still treats it as open. The prediction held:
   after opening and closing the drawer, so that `route` became `Drawer`, a
   critical `busctl` notification at 20:53:44Z mapped a banner at once. The fix
   and its board check are in the next section.

## Banners after the shade closes: fix, 2026-10-29

`nix/rust-shell-client/src/main.rs` `sync_banner` now counts the shade as
open only while the overlay's layer is mapped
(`self.route == Route::Shade && self.layer.is_some()`). Host:
`cargo test --offline --lib` in `nix/rust-shell-client`, 678 passed. Board:
build `/nix/store/ql630glmr9j0smkf5b0l14y0cxlmsjhg-nixos-system-nixos-26.11.20260919.20b1ddd`,
test-activated (not the boot default). Evidence class: injected touch and
`busctl` over SSH.

The steps match the failing run on `1lpsniwg…` at 20:52:52Z: a swipe down
from the top edge opened the shade, and a swipe up closed it, which also
showed the compositor's overview. Then, at 21:09:50Z, a critical `busctl`
notification. This time the shell logged `notification-banner-map-request`
and unmapped the banner about 4.6 s later. `board/banner-after-shade-closed.png`
is the banner over the overview. Quiet was off for the test, then turned back
on with the tile.

### Boot default and ordinary boot

On the operator's decision ("Promote it", 2026-10-29T22:03Z,
`docs/evidence/glass-checklist-2026-10-29/operator-report.md`), with the
charger online and the same kernel, initrd and dtbs as `1lpsniwg…`, `init=` in
`/boot/bootargs.txt` was set to `ql630glm…` (backup
`/var/tmp/bootargs.txt.before-ql630glmr9j0smkf5b0l14y0cxlmsjhg`), the system
profile was set to it, and the board rebooted at 22:04Z.
`/run/booted-system` was `ql630glm…`, `shell.service` and `shell-ui.service`
were active, and no units had failed. The same shade-then-notify steps
(shade opened by swipe, Quiet turned off with the tile, shade closed by
swipe, critical `busctl` at 22:06:20Z) mapped a banner
(`board/banner-after-shade-ordinary-boot.png`). Quiet was turned back on
afterwards.

## Not covered

The operator's glass check (3.6).
