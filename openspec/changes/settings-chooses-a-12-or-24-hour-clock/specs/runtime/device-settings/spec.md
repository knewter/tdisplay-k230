## ADDED Requirements

### Requirement: Settings chooses a 12-hour or 24-hour clock

*Grounding (2026-10-29): Settings' Date & time page shows "Clock format: 24-hour" as a fixed value (`nix/rust-shell-client/src/device_info.rs`), and the Python clocks format with `%H:%M` (`nix/term-apps/k230_term_apps.py`, `k230_exhibition.py`). The operator moved this follow-up out of `settings-has-about-and-date-time-pages` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

<!-- UNVERIFIED: nothing in this requirement is built yet. -->

Settings' Date & time page SHALL offer the clock format as a choice between
24-hour and 12-hour, with a hit region that meets the shell's 99 px floor. The
choice SHALL persist across a shell restart and a reboot, and SHALL default to
24-hour when it has never been set or cannot be read. Every clock drawn by the
shell and by the shell's own apps SHALL follow it within a minute of a change,
without a restart.

#### Scenario: Switching to a 12-hour clock

- **WHEN** a person sets the clock format to 12-hour at 21:05
- **THEN** the shade, Home and the Date & time page show 9:05 PM, and the
  idle clock screen shows it the next time it draws

#### Scenario: No preference yet

- **WHEN** the shell starts and the clock-format preference has never been set
- **THEN** every clock is 24-hour, as before this change
