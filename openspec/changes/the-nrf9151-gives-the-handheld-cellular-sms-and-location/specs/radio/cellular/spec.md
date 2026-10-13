## Purpose

Let the handheld use the keyboard base's nRF9151 for cellular status, SIM handling and SMS, through one Linux service that owns the modem's power and AT link, with the modem off until a person turns it on.

## ADDED Requirements

### Requirement: The modem link does not cost the console

<!-- UNVERIFIED: UART3's two pad groups (IO50/51 to CH342 channel 1, IO28/29 to the nRF9151) come from `docs/dts-evidence.md` and LILYGO `HARDWARE_PINMAP.md` and patch 0061; the mainline console on UART0/IO38-39 is grounded by the installed mainline images. No boot with UART3 on IO28/29 has been observed. -->
The system SHALL carry the modem's AT link on UART3 over IO28/29 and SHALL leave IO50/51 as quiet GPIO inputs. The Linux console on UART0 (CH342 channel 0) SHALL keep working: boot messages and login on the same port as before. CH342 channel 1 SHALL be documented as carrying nothing.

#### Scenario: First boot of the new device tree

- **WHEN** the board boots the device tree that moves UART3 to the modem pads
- **THEN** the console on channel 0 shows the boot log and accepts a login, and `/dev/ttyS3` exists

### Requirement: The modem is off until a person turns it on

<!-- UNVERIFIED: the enable line (IO2, high = on) and the firmware's auto-connect come from LILYGO `HARDWARE_PINMAP.md` and `serial_modem_k230/k230_serial_modem.conf`; IO2's state before Linux and the modem's current draw are not observed. -->
On every boot the system SHALL hold the modem unpowered until a person turns Cellular or Location on. That choice SHALL persist across reboots in system state. Turning both off SHALL put the modem into minimum function and then remove its power.

#### Scenario: Fresh image

- **WHEN** a fresh image boots with the keyboard base attached
- **THEN** the modem's enable line is low, the modem answers no AT command, and the shade shows no cellular indicator

#### Scenario: Turning Cellular off

- **WHEN** a person turns Cellular off while the modem is registered
- **THEN** the service sends minimum function, the enable line goes low, and the state file reports `off`

### Requirement: A single service owns the modem

<!-- UNVERIFIED: no Linux-side AT exchange with this modem has been observed. -->
Exactly one system service SHALL open the modem's UART and its enable line. Every other component, including the shell, SHALL read the modem's state from the service's published state and send requests through its local control socket, never AT commands. The service SHALL keep one AT command in flight at a time, apply a timeout to each, and handle unsolicited results between commands.

#### Scenario: A second opener

- **WHEN** another process tries to open `/dev/ttyS3` while the service runs
- **THEN** it is refused, and the service's state stays consistent

#### Scenario: The modem stops answering

- **WHEN** the modem does not answer a command within its timeout
- **THEN** the state file reports the error, the shell shows the modem as unavailable, and the service recovers by power-cycling the modem at most once per minute

### Requirement: The person sees SIM, registration and signal

<!-- UNVERIFIED: the SIM-check sequence (`AT+CFUN=1`, `AT%XSIM?`, `AT+CPIN?`) comes from LILYGO `docs/AT_COMMANDS.MD`; SIM presence and antennas on this unit are unknown. -->
With Cellular on, the service SHALL report SIM state (absent, PIN required, ready, locked), registration state, operator name, access technology (LTE-M or NB-IoT) and signal strength, updated within 30 seconds of a change.

#### Scenario: No SIM

- **WHEN** Cellular is turned on with no SIM inserted
- **THEN** Settings shows "No SIM" and the shade's indicator shows no service, without error loops in the journal

#### Scenario: Registered

- **WHEN** Cellular is on with a working SIM and antenna in coverage
- **THEN** Settings shows the operator, LTE-M or NB-IoT, and a signal level, and the shade shows matching bars

### Requirement: A SIM PIN is never stored or logged

<!-- UNVERIFIED: no SIM PIN entry has been exercised. -->
A SIM PIN SHALL reach the modem only through the control socket. It SHALL NOT appear in the journal, the AT trace, the state file, settings, or any committed evidence. The service SHALL NOT retry a rejected PIN on its own.

#### Scenario: Entering a PIN

- **WHEN** a person enters a SIM PIN in Settings
- **THEN** the SIM unlocks or reports a wrong PIN with the remaining attempts, and searching the journal and `/var/lib/k230` for the digits finds nothing

### Requirement: Text messages are received and can be sent

<!-- UNVERIFIED: SMS support (`CONFIG_SM_SMS=y`) comes from the vendor firmware configuration; no message has been exchanged on this unit. -->
With Cellular on and registered, an incoming SMS SHALL be stored in a bounded, user-readable store that a person can clear, and SHALL be raised as a shell notification. A person SHALL be able to send an SMS with `k230-modemctl sms send <number>`, with the result reported as sent or failed.

#### Scenario: Receiving a text

- **WHEN** a text is sent to the SIM's number
- **THEN** within one minute a notification appears in the shell, and the message is in the store with its sender and time

#### Scenario: Sending a text

- **WHEN** an operator runs `k230-modemctl sms send` to a test number with a short body
- **THEN** the command reports success and the message arrives at that number
