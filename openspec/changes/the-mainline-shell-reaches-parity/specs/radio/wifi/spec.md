## ADDED Requirements

### Requirement: Wi-Fi joins a protected network under the mainline kernel
On the mainline full shell, the RTL8189FTV radio SHALL appear as a wireless
interface and join a protected network using the existing runtime-only secret
path; credentials never enter the system closure, evidence or logs.

#### Scenario: Interface appears
- **WHEN** the mainline full shell boots
- **THEN** a wireless interface backed by the RTL8189FTV is listed
<!-- UNVERIFIED: SDIO (mmc_sd0) is disabled in the mainline DT and the module is not built for mainline -->

#### Scenario: Association and reachability
- **WHEN** the operator supplies the network through the protected configuration path
- **THEN** the interface associates, obtains an address and reaches a host on that network, with each stage proven separately
<!-- UNVERIFIED -->

#### Scenario: Blocked port is recorded, not hidden
- **WHEN** the out-of-tree driver cannot be built for the mainline kernel
- **THEN** the exact build failure is recorded and Wi-Fi under mainline is carried to an explicit successor rather than claimed
