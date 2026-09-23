## Purpose

Defines credential-safe wireless diagnosis and connection behavior that the
physical board must demonstrate before it is treated as network-capable.

## ADDED Requirements

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
