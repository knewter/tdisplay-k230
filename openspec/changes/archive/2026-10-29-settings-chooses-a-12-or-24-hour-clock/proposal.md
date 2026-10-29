## Why

A person who reads time on a 12-hour clock cannot get one. Every clock on the
handheld (the shade, Home, the idle clock screen, the Timer's and Weather's
status lines) is 24-hour, and Settings' Date & time page says so, but nothing
lets the person change it.

This is task 4.1 of `settings-has-about-and-date-time-pages`, moved here on
the operator's decision of 2026-10-29 ("Split them out",
`docs/evidence/glass-checklist-2026-10-29/operator-report.md`) so that change
could archive. That task read: "A 24/12-hour preference: state in the
settings broker and every clock consumer reading it. Needs its own proposal."

## What Changes

- A clock-format preference, `24-hour` (the default) or `12-hour`, stored
  like the other shell preferences (one word in a file under
  `/var/lib/k230-shell-prefs/`; missing or unreadable means 24-hour).
- The Date & time page's "Clock format" row becomes a switch between the two.
- Every clock the shell and its own apps draw follows the preference. In
  12-hour form, the time is drawn without a leading zero and with an AM or PM
  marker.

## Non-goals

- Time zone and network time changes. They are
  `settings-sets-the-time-zone-and-network-time`.
- Date-order or locale formats, seconds on clocks that do not show them, and
  third-party apps (GTK apps format time themselves).

## Capabilities

### Modified Capabilities

- `runtime/device-settings`: Settings chooses a 12-hour or 24-hour clock.

## Impact

- `nix/rust-shell-client/src/device_info.rs` (the row, now a switch),
  `shell_prefs.rs` (the preference), and the shell's clock drawing (shade
  and Home).
- `nix/term-apps/k230_term_apps.py` and `k230_exhibition.py`, which format
  times with `%H:%M` today.
- Host-verifiable for the logic and renders. The physical board is needed for
  the glass check and to confirm that each running clock picks up a change.
