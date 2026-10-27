## 1. Host

- [x] 1.1 Add the broker's delegate rule (namespaced id, sanitised label, reserved names, theme-name icons, priority cap, no ongoing or target, always-private preview), the `withdraw` operation, and interpreter-plus-script trusted keys. Proof: `python3 tests/test_notification_center.py && python3 tests/test_notification_dbus.py` (host; includes a private bus, the real broker and the real adaptor).
- [x] 1.2 Add the `org.freedesktop.Notifications` adaptor (`tools/notification_dbus.py`, jeepney). Proof: `python3 tests/test_notification_dbus.py`.
- [x] 1.3 Post "Timer finished" on expiry and leave a detached helper when a running timer's card closes; reopening adopts the countdown. Proof: `python3 tests/test_term_apps.py`.
- [x] 1.4 Wire `shell-notification-dbus.service`, the delegate and Timer trusted-source entries, and the jeepney interpreter in Nix. Proof: `nix-instantiate --parse nix/shell.nix` (syntax only; see 2.1 for evaluation).
- [x] 1.5 Add the new test to the host CI list in `.github/workflows/spec-site.yml`. Proof: `python3 tests/test_notification_dbus.py`.

## 2. Build

- [x] 2.1 Evaluate and cross-build the landscape system with the new service and jeepney, and record that `jeepney` builds under the cross toolchain. Proof (QEMU/host, not hardware): `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel --out-link <scratch>/result`, then `systemctl cat shell-notification-dbus.service` equivalent via `nix eval` of the unit text. Not run in this worktree.
  Done 2026-10-27: the landscape system built on the host with `shell-notification-dbus.service` and `jeepney` (store path `dhmp8mdi…`, master `8b4f7d73`); see `docs/evidence/apps-alert/README.md`.
- [ ] 2.2 Run the adaptor and `notify-send` under the QEMU shell, if `libnotify` is added to the test closure, and record the history entry. Proof (QEMU, not glass): the QEMU smoke harness, with the exact command recorded under `docs/evidence/apps-alert/`.

## 3. Board (hardware-only)

Each of these needs the reserved board, the installed build and, for 3.1 and 3.2, grim captures of the glass (injected input is acceptable; do not assume the person is touching).

- [x] 3.1 `notify-send` shows a banner. Operator command, as the `shell` user over protected SSH: `sudo -u shell env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus notify-send -a Probe -u critical "Probe" "body"`; capture the preview with `grim`, then `k230-notifications history` for the app name, `important` priority and `dismissible: true`. Also confirm `busctl --user --address=unix:path=/run/shell-bus/bus status org.freedesktop.Notifications` names the adaptor. Record under `docs/evidence/apps-alert/`.
  Done 2026-10-27T03:37:59Z on the board (injected over SSH). `notify-send` is not on the image, so `busctl ... Notify` made the same call; history showed `Probe`, `important`, `dismissible: true`, and `busctl status` named the adaptor. `docs/evidence/apps-alert/`.
- [ ] 3.2 A GTK app's notification arrives (for example a GTK app that calls `g_application_send_notification`), and an app naming itself "Shell" appears as "Application". Same capture method.
- [x] 3.3 Timer expiry with the card open shows a banner. Start the Timer for 10 s with injected touch, capture with `grim`.
  Done 2026-10-27T15:20:53Z (injected keys, build `iw96wr9d…`): banner "Timer / Timer finished" with the Timer icon. `docs/evidence/apps-alert/`.
- [x] 3.4 Timer expiry with the card closed shows a banner. Start a 20 s timer, close the card with the shell's close gesture, wait, capture the banner with `grim`, and confirm one History entry only. Then repeat with a reopen before expiry and confirm the countdown resumes and no second alert arrives.
  Done 2026-10-27 (injected keys): closed-card banner at 15:22:40Z with one history entry and the helper gone; reopened at 0:31 and it resumed, with one entry at expiry. Limit: Timer alerts share a replacing tag, so the count alone cannot exclude a replaced second post. `docs/evidence/apps-alert/`.
- [x] 3.5 Measure idle cost: with the adaptor running and no timer, `/proc/<pid>/stat` utime+stime over 60 s for `k230-notification-dbus` shows no growth beyond a post. Record under `docs/evidence/apps-alert/`. Measurement only.
  Done 2026-10-27 15:17:09-15:18:09Z: utime+stime delta 0 ticks over 60 s. `docs/evidence/apps-alert/`.
- [ ] 3.6 The operator sees both banners on glass. Physical proof: a timestamped operator report tied to the installed build.

## 4. Open

- [ ] 4.1 The Timer alerts late if the board suspends with a timer pending (monotonic clock stops). Decide, with a board observation of whether this image suspends, whether the helper must use `CLOCK_BOOTTIME`.
- [ ] 4.2 A shell restart ends a pending timer silently. Decide whether the helper should move out of `shell.service`'s cgroup, or the restart should say so.
- [ ] 4.3 `NotificationClosed` for closes the person makes in the shade, and `ActionInvoked`, are not delivered. Open a successor change if an app needs either.
