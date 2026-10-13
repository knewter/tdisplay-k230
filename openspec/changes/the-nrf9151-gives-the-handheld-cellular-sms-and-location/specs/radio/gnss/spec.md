## Purpose

Give the handheld a location from the keyboard base's nRF9151 GNSS receiver, through `gpsd`, only while a person has Location turned on.

## ADDED Requirements

### Requirement: Location is available through gpsd while turned on

<!-- UNVERIFIED: the GNSS-only recipe and `#XGNSSNMEA:` URCs come from LILYGO `docs/AT_COMMANDS.MD` and `CONFIG_SM_GNSS_NMEA_URC=y`; no fix has been observed on this unit, and the GNSS antenna is unknown. -->
With Location on, the system SHALL feed the modem's NMEA output to `gpsd`, so that a `gpsd` client reports the receiver's state: no fix, then 2D or 3D fix with position and time. With Location off, GNSS SHALL be stopped and `gpsd` SHALL report no device.

#### Scenario: A fix under open sky

- **WHEN** Location is on, Cellular is off, and the board has sky view for up to 10 minutes
- **THEN** `gpspipe -w` reports a 3D fix whose position is consistent with the operator's known location to within 100 m

#### Scenario: Indoors

- **WHEN** Location is on without sky view
- **THEN** the shell shows "searching" and `gpsd` reports no fix, and nothing presents a stale or invented position

### Requirement: Location sharing with Cellular is honest

<!-- UNVERIFIED: GNSS and LTE share the nRF91 radio; behavior with system mode `1,1,1,0` has not been observed. -->
With both Cellular and Location on, the system SHALL keep the cellular registration and run GNSS when the modem allows it. It SHALL report "searching" while no fix is available, rather than turning Cellular off on its own.

#### Scenario: Both on

- **WHEN** Cellular is registered and the person turns Location on
- **THEN** Cellular stays registered, and Location reports searching or a fix

### Requirement: Positions are not recorded by the system

<!-- UNVERIFIED: depends on the service implementation. -->
The modem service and `gpsd` SHALL NOT write positions to persistent storage or the journal. Recording a track is left to a client the person runs.

#### Scenario: After a session

- **WHEN** Location has produced fixes and is then turned off
- **THEN** no file under `/var` and no journal entry contains a latitude or longitude from that session
