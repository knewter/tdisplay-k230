## Why

The board has no usable network path. The current system exposes the SDIO
radio to the kernel but no wireless interface, and its image does not carry
the tools needed to inspect or join a network. A person cannot use the board
away from the serial cable or transfer evidence without removing the card.

This is timely because a private board preflight found an SDIO function but no
wireless driver binding. That observation is not committed evidence and does
not establish that the radio works; the first hardware task records a
credential-free version before changing the system.

## What Changes

- Add a `radio/wifi` capability for a system that can enumerate its wireless
  interface, join a WPA network from a runtime-only secret, obtain a lease,
  and demonstrate routing and DNS.
- Establish the missing driver path for the board's SDIO radio, after a
  source/configuration audit confirms the appropriate module and its kernel
  compatibility.
- Add the smallest command-line radio tools and regulatory data needed for
  diagnosis and a one-off connection; select a persistent configuration only
  after the live connection works.
- Capture sanitized board evidence for enumeration, association, address,
  default route, DNS, and an outbound reachability check. Network names,
  passwords, BSSIDs, addresses assigned by the access point, and secret-file
  contents stay out of tracked files and command output.

**Non-goals.** This does not add Ethernet, cellular, an access point, a
network UI, saved credentials in Nix, or a claim that the shipped RT-Smart
radio stack works. It does not change stage 1, panel, touch, AtomVM, or Dozer.

**Needs the physical board.** Package and kernel-module configuration can be
audited and cross-built on the host, but QEMU models neither this SDIO radio
nor its power gate. Only a board can prove enumeration, association, DHCP,
DNS, or packet delivery.

## Capabilities

### New Capabilities

- `radio/wifi`: credential-safe wireless diagnosis, runtime connection, and
  evidence of usable network connectivity on the physical board.

### Modified Capabilities

None.

## Impact

- Likely kernel configuration or an out-of-tree, source-built RTL8189 SDIO
  module; the exact source and compatibility decision follow the audit.
- NixOS package selection for `iw`, WPA supplicant, DHCP, and regulatory data.
- A runtime-only secret handoff owned by the board operator, plus sanitized
  evidence under `docs/evidence/` after a real attempt.
