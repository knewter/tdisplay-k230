## ADDED Requirements

### Requirement: Settings changes the time zone and network time

*Grounding (2026-10-29): the zone is build-time (`time.timeZone = "America/Chicago"` in `nix/k230.nix`), and Settings' Date & time page shows the zone and synchronization read-only (`nix/rust-shell-client/src/device_info.rs`; board captures in `docs/evidence/settings-about/`). The operator moved this follow-up out of `settings-has-about-and-date-time-pages` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-30): `nix/time-settings.nix` and `tools/k230_time_helper.py` (host tests in `tests/test_time_helper.py`); the chooser in `nix/rust-shell-client/src/device_info.rs` (host renders in `docs/evidence/time-zone/host/`). Board, injected, on `sqd58h8c…`: Europe/London applied and followed by the shade and Clock app without a restart, network time off, both held across a switch and a reboot, and other requests refused (`docs/evidence/time-zone/board/`). The glass step was replaced by injected checks on the operator's instruction. The page shows network time switched off as "Off". The zone change was observed in daylight time, a 5-hour move, not the scenario's standard-time 6 hours.*

Settings' Date & time page SHALL let a person choose the time zone from a list
and turn network time on or off. The change SHALL take effect without a
reboot, SHALL persist across a reboot and a switch to a new build, and SHALL
be applied by a privileged path that accepts only these two settings, so that
the shell user gains no other root access.

#### Scenario: Changing the zone

- **WHEN** a person in Settings chooses Europe/London while the clock reads
  15:00 in America/Chicago during standard time
- **THEN** the clocks read 21:00, and the Date & time page shows Europe/London
  with its UTC offset

#### Scenario: The choice survives a reboot

- **WHEN** the person has chosen a zone and the handheld reboots
- **THEN** the clocks still use that zone

#### Scenario: Turning network time off

- **WHEN** a person turns network time off
- **THEN** the page says the clock is not synchronized from the network, and
  stays that way after a reboot until it is turned back on
