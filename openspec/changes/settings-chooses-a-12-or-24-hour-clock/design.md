## Context

The layer is userspace: the Rust shell client and the Python terminal apps.
The shell already keeps one-word preferences in `/var/lib/k230-shell-prefs/`
(`do-not-disturb`, `idle-timeout`, `clock-effects` and others), read through
`nix/rust-shell-client/src/shell_prefs.rs`. The Date & time page
(`device_info.rs`) shows "Clock format: 24-hour" as a fixed value. The
Python clocks format with `time.strftime("%H:%M", …)`.

## Goals / Non-Goals

**Goals:** one preference that every clock drawn by the shell and its own
apps follows, changed from Settings, with no restart.

**Non-Goals:** locale-driven formats, time zone and NTP, GTK apps.

## Decisions

- **Store it as a shell preference file**, like Do Not Disturb, so the shell
  and the Python apps read one source. Missing or unreadable means 24-hour,
  the current behaviour.
- **Readers pick up a change without a restart.** The exhibition clock and
  the Timer already redraw at least once a minute; they reread the file then.
  The shell updates its own state when the switch is tapped.
- **12-hour form:** no leading zero, a space, then "AM" or "PM" (for example
  "9:05 PM"). The large digit clock may draw the marker smaller beside the
  digits. The exact layout is settled by host renders in task 2.

Rejected:

- **Reading `LC_TIME` from the environment.** The image sets no user locale,
  and a locale switch would change more than the clock.
- **A Settings-only label change.** It would leave the clocks disagreeing
  with the page that claims to set them.

## Risks / Trade-offs

- [A clock that reads the file only at start stays 24-hour after a change] →
  task 1 lists every consumer, and the board check in task 3 changes the
  setting with each clock visible.
- [The 12-hour digits are wider on the idle clock] → host renders at 100% and
  200% before any board work.

## Migration Plan

None. The default is the current behaviour.
