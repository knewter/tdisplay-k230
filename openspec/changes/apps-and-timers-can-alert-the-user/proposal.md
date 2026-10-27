## Why

The handheld has no speaker and no haptics, so the screen is the only way an
app can get the person's attention. Today it cannot:

- `notify-send`, and every GTK or GLib app that calls
  `g_application_send_notification`, sends to `org.freedesktop.Notifications`
  on the session bus. Nothing owns that name, so the call fails or is dropped
  and the person never sees it.
- The Timer rings the terminal bell (`\a`) when it expires. With no speaker
  that is silent. If the person has closed the Timer's card, or is in another
  app, they are never told. Closing the card also ends the countdown, because
  the countdown lives inside the card's process.

The shell already has a notification broker with a banner, history, privacy
defaults and priorities. Only a way in for apps is missing.

## What Changes

- A small `org.freedesktop.Notifications` adaptor on the application session
  bus forwards `Notify` and `CloseNotification` into the broker. Urgency
  `critical` maps to important; everything else is ordinary. The broker's
  defaults stay in force: the preview hides the text, the history shows it.
- The broker learns one new kind of trusted source, a delegate, that speaks
  for named apps. An app is shown by its own label and icon but can never
  appear as the Shell or System, never reach critical, never be pinned, and
  never point at a window.
- The Timer posts an important "Timer finished" notification when it expires.
- A running Timer leaves a small detached helper when its card closes. The
  helper sleeps to the deadline and posts the same notification. Reopening the
  Timer picks the countdown back up.
- Host tests for the adaptor, the delegate rule and the Timer path.

## Non-goals

- Notification actions, buttons, images, sound, and `NotificationClosed` for
  closes the person makes in the shade (the adaptor only reports closes an app
  asked for). The adaptor advertises the `body` capability and nothing else.
- Timers that survive a reboot, a shell restart or a force-killed card.
- Alarms at a wall-clock time, a Clock alarm app, or repeat timers.
- Changing the banner, the shade, or the broker's wire format for the shell.
- Speaker or haptic output.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/notification-center`: apps reach the broker through the standard
  desktop service, and a timer alerts without its card open.

## Impact

Userspace only: `tools/notification_center.py`, new `tools/notification_dbus.py`,
`nix/term-apps/k230_term_apps.py`, `nix/shell.nix` (a new
`shell-notification-dbus` service and two trusted-source entries) and new
`nix/handheld-notification-dbus.nix`. New runtime dependency: `jeepney`, a
pure-Python D-Bus library.

Host tests need no board. The banner on the glass, the real GTK path and the
closed-card timer need the board and stay open in `tasks.md`.
