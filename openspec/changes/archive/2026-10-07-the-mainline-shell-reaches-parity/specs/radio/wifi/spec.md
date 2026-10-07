## ADDED Requirements

### Requirement: Wi-Fi joins a protected network under the mainline kernel
On the mainline full shell, the RTL8189FTV radio SHALL appear as a wireless
interface and join a protected network using the existing runtime-only secret
path; credentials never enter the system closure, evidence or logs.

#### Scenario: Interface appears
- **WHEN** the mainline full shell boots
- **THEN** a wireless interface backed by the RTL8189FTV is listed
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): SDIO card enumerates, 8189fs/cfg80211 load, wlan0 up. -->

#### Scenario: Association and reachability
- **WHEN** the operator supplies the network through the protected configuration path
- **THEN** the interface associates, obtains an address and reaches a host on that network, with each stage proven separately
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): associated, IPv4 assigned, gateway reachable, each checked separately; no identifiers recorded. -->

#### Scenario: Blocked port is recorded, not hidden
- **WHEN** the out-of-tree driver cannot be built for the mainline kernel
- **THEN** the exact build failure is recorded and Wi-Fi under mainline is carried to an explicit successor rather than claimed
