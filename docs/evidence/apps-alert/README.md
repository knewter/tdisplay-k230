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

## Not covered

A GTK app's `g_application_send_notification` (3.2), Timer with the card open
(3.3), idle cost (3.5) and the operator's glass check (3.6).
