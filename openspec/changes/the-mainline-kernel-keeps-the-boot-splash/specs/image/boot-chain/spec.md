## ADDED Requirements

### Requirement: The device tree the board boots reserves the splash buffer

The device tree stage 1 loads for the daily system SHALL reserve the splash
buffer's address range from the kernel's allocator, with the address and size
taken from the same flake constant that configures stage 1's splash symbol, so
that a stage 1 image survives until a display client replaces it.

*Grounding: the vendor tree `nix/dts/k230-tdisplay.dts` carries a
`reserved-memory` framebuffer node (task 3.5 of the archived
`the-screen-lights-before-linux`); the mainline trees under
`nix/dts/k230-tdisplay-mainline-drm*.dts*` carry none (read 2026-10-12).*

<!-- UNVERIFIED in full: no reservation exists in the mainline tree yet, and
 no boot has shown the buffer surviving to a display client on the mainline
 kernel. Proven by tasks 1.1 and 2.1 to 2.4 of
 the-mainline-kernel-keeps-the-boot-splash. -->

#### Scenario: The compiled device tree is inspected

- **WHEN** someone reads the daily device tree's `/reserved-memory`
- **THEN** a framebuffer node whose `reg` equals stage 1's splash address and size is present

#### Scenario: A boot carries the splash to the first display client

- **WHEN** stage 1 lights the panel and the mainline kernel boots to its first DRM client
- **THEN** the splash buffer is unmodified until that client replaces it, as recorded in a capture committed under `docs/evidence/`
