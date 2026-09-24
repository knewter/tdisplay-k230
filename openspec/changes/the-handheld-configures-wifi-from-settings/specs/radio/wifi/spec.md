## ADDED Requirements

### Requirement: Settings permit touch Wi-Fi discovery and connection
<!-- UNVERIFIED: physical scan, association and glass interaction remain to be observed; existing evidence proves only operator-managed protected Wi-Fi. -->
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
<!-- UNVERIFIED: masked password entry and protected broker on physical glass remain to be observed. -->
The shell userspace SHALL offer an on-screen password keyboard for a selected supported secured network, mask entered characters by default, permit correction and cancellation, and show a bounded Connect pending state with a useful failure and retry route. The system SHALL pass a credential only through a private runtime channel to a privileged Wi-Fi service; neither side SHALL put the secret or a network identifier in command arguments, environment, Nix closure, tracked files, ordinary logs, or committed evidence. The shell SHALL NOT receive saved passwords back from the service.

#### Scenario: Secured network selected
- **WHEN** a person taps a WPA2-Personal network
- **THEN** a masked entry and on-screen keyboard appear, and Connect remains disabled until the entered value meets the supported format

#### Scenario: Authentication fails
- **WHEN** a connection attempt is rejected or times out
- **THEN** the shell keeps the selected network context and shows an actionable error without disclosing the entered secret

#### Scenario: Open network selected
- **WHEN** a person taps a supported open network
- **THEN** Connect needs no password and still reports progress and a confirmed outcome

### Requirement: Saved networks reconnect and can be forgotten
<!-- UNVERIFIED: Settings-driven persistence, forget and reboot reconnect require physical-board proof. -->
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
