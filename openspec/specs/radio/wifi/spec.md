# radio/wifi Specification

## Purpose
Defines credential-safe wireless diagnosis and connection behavior that the
physical board must demonstrate before it is treated as network-capable.

## Requirements

### Requirement: The system reports radio readiness without a network secret
*Grounding: `docs/evidence/offline-wifi-image/final-readiness.txt` records bound RTL8189 SDIO radio, wlan0/wlan1 and regulatory state on the physical board.*
The system SHALL provide the radio driver, regulatory data, and diagnostic
commands needed for an operator at the console to determine whether the board
has a wireless interface, its driver, and its regulatory state without
scanning for or naming access points. The physical board owns proof of this
requirement; a host build only proves that the closure contains the selected
components.

#### Scenario: A driver is missing or cannot bind
- **WHEN** the operator performs the credential-free readiness check on the physical board
- **THEN** the resulting sanitized evidence identifies the SDIO function and records that no wireless interface or bound driver is available without claiming radio readiness

#### Scenario: A driver binds successfully
- **WHEN** the operator performs the credential-free readiness check after the selected driver is installed
- **THEN** the console exposes a wireless interface and its regulatory state without disclosing access-point identifiers

### Requirement: The system joins a protected network from a runtime-only secret
*Grounding: `docs/evidence/offline-wifi-image/final-wifi-network.txt` records association COMPLETED; `docs/evidence/offline-wifi-image/README.md` records the root-only runtime handoff and `wifi-cleanup.txt` records cleanup.*
The system SHALL allow the board operator to supply a protected-network
configuration at runtime from a root-readable secret file and use it to
associate. The system MUST NOT place a network name, passphrase, derived PSK,
or secret-file contents in the Nix store, tracked configuration, command-line
arguments, or committed evidence.

#### Scenario: Operator supplies a runtime secret
- **WHEN** the operator provides a root-readable runtime secret through the protected board procedure
- **THEN** the connection service can use that secret to associate and no credential is added to the system source tree or Nix closure

#### Scenario: Association is rejected
- **WHEN** the access point rejects association or authentication
- **THEN** the operator can inspect a sanitized failure state and retry or remove the runtime secret without committing network-specific information

### Requirement: The system proves each connectivity stage separately
*Grounding: `docs/evidence/offline-wifi-image/final-wifi-network.txt` separately records DHCP, Wi-Fi default/resolver routes, DNS and interface-bound outbound ping on the physical board.*
After association, the system SHALL let an operator verify address assignment,
default routing through the wireless interface, confirmation that the selected
resolver routes through that interface, DNS resolution, and an
interface-bound outbound reachability check as distinct stages. Physical-board
evidence MUST redact access-point identifiers and locally assigned addresses
before it is committed.

#### Scenario: The network supplies usable service
- **WHEN** association completes and the operator runs the staged validation on the physical board
- **THEN** sanitized evidence records successful address, route, resolver-route, DNS, and outbound-reachability stages without disclosing network-specific identifiers

#### Scenario: One connectivity stage fails
- **WHEN** association completes but address assignment, routing, DNS, or outbound reachability fails
- **THEN** the operator can identify the failed stage from credential-free command results and the system does not claim end-to-end connectivity

### Requirement: Persistent wireless setup keeps credentials outside the system closure
*Grounding: `docs/evidence/wifi-persistent/after-reboot-identity.txt` records a new boot and root-owned mode-0600 credential; `docs/evidence/wifi-persistent/after-reboot.txt` records automatic association, DHCP, Wi-Fi routing, DNS and bound ping without re-provisioning.*
If the operator elects to persist wireless configuration after a successful
live connection, the system SHALL consume the credential through a
root-controlled runtime credential mechanism rather than embedding it in Nix
source, generated world-readable configuration, or the system closure.

#### Scenario: Persistent setup is enabled
- **WHEN** the operator reboots after installing an approved root-controlled credential mechanism
- **THEN** the connection service can receive the runtime credential while source control and the Nix store contain no network secret

### Requirement: Settings permit touch Wi-Fi discovery and connection
<!-- Grounding: docs/evidence/wifi-settings/closeout-2026-10-01/README.md; operator acceptance plus independently injected board eye/keyboard checks, with explicit limits. -->
The system's shell userspace SHALL let a person open Network from Settings, refresh and scroll a bounded list of nearby networks, distinguish current and saved connections, select an open or WPA2-Personal network by touch, and return without changing connection. It SHALL show scanning, empty, unavailable, stale, and failed states without presenting a stale scan as current. It SHALL not equate association with Internet reachability.

#### Scenario: Person opens Network
- **WHEN** a person taps Network in Settings
- **THEN** the shell shows current association and saved-network state and begins a bounded scan with a visible progress state

#### Scenario: Scan fails or returns no networks
- **WHEN** scanning is denied, times out, or finds nothing
- **THEN** the shell explains that condition, retains a contextual Retry, and does not fabricate a connection

#### Scenario: Scan replies out of order
- **WHEN** an older scan finishes after a newer scan or after Network is closed
- **THEN** the old result does not replace the currently visible state or trigger a connection

### Requirement: Secure network entry is touch-operable and secret-safe
<!-- Grounding: docs/evidence/wifi-settings/closeout-2026-10-01/README.md; operator acceptance plus independently injected board eye/keyboard checks, with explicit limits. -->
The shell userspace SHALL offer masked password entry for a selected supported secured network using the same system keyboard every other text field in the shell uses (not a separate in-app keypad), mask entered characters by default, permit correction and cancellation, and show a bounded Connect pending state with a useful failure and retry route. The password field SHALL take real keyboard focus only for its own lifetime and release it immediately on Connect, Cancel, or leaving the page, so the system keyboard never contests focus with an application the rest of the time. Cancel/Connect SHALL remain reachable above the raised keyboard rather than hidden beneath it. The system SHALL pass a credential only through a private runtime channel to a privileged Wi-Fi service; neither side SHALL put the secret or a network identifier in command arguments, environment, Nix closure, tracked files, ordinary logs, or committed evidence. The shell SHALL NOT receive saved passwords back from the service.

#### Scenario: Secured network selected
- **WHEN** a person taps a WPA2-Personal network
- **THEN** a masked entry appears, the system keyboard raises from the bottom of the screen, Cancel/Connect move to sit above it, and Connect remains disabled until the entered value meets the supported format

#### Scenario: Person checks a possible typing error
- **WHEN** a person taps the password field's Show eye icon while entering an unsaved password
- **THEN** only that in-progress field becomes readable, typing and correction continue through the same system keyboard, and the eye changes to Hide
- **AND** tapping Hide or leaving the editor masks the field again; a later editor starts masked and saved credentials remain unavailable to the shell

#### Scenario: Password field is not focused
- **WHEN** an open network is selected, a saved credential needs no re-entry, or the Wi-Fi page is closed
- **THEN** the system keyboard is not raised and the overlay does not hold keyboard focus

#### Scenario: Authentication fails
- **WHEN** a connection attempt is rejected or times out
- **THEN** the shell keeps the selected network context and shows an actionable error without disclosing the entered secret

#### Scenario: Open network selected
- **WHEN** a person taps a supported open network
- **THEN** Connect needs no password and still reports progress and a confirmed outcome

### Requirement: Saved networks reconnect and can be forgotten
<!-- Grounding: docs/evidence/wifi-settings/closeout-2026-10-01/README.md; operator acceptance plus independently injected board eye/keyboard checks, with explicit limits. -->
The system SHALL save an accepted connection only in the existing root-controlled Wi-Fi credential location outside the image closure and use the existing runtime credential service to reconnect on later boots. Settings SHALL expose saved state and an explicit Forget action that removes the selected saved credential and stops automatic reconnect for that network. A failed, cancelled, or stale attempt SHALL NOT overwrite the last confirmed saved configuration.

#### Scenario: Device restarts after accepted setup
- **WHEN** a person has connected and then restarts the device
- **THEN** the system can reconnect using the root-private saved configuration without re-entering the password

#### Scenario: Person forgets a saved network
- **WHEN** the person confirms Forget for a saved network
- **THEN** Settings removes its saved status and the system no longer automatically reconnects to it

#### Scenario: Attempt fails while another network is saved
- **WHEN** a new connection attempt fails or is cancelled
- **THEN** the previously saved network remains available for automatic reconnect
