## ADDED Requirements

### Requirement: The device tree the board boots reserves the splash buffer

The device tree stage 1 loads for the daily system SHALL reserve the splash
buffer's address range from the kernel's allocator, with the address and size
taken from the same flake constant that configures stage 1's splash symbol, so
that a stage 1 image survives until a display client replaces it.

*Grounding: `nix/dts/k230-tdisplay-mainline-drm-common.dtsi` carries
`framebuffer@10000000` (`0x400000`, `no-map`) from the flake's splash
constants (task 1.1, `docs/evidence/mainline-boot-splash/README.md`). On the
board (`docs/evidence/mainline-boot-splash/board/README.md`, 2026-10-12, warm
reboots): the kernel logs `reserved mem: 0x10000000..0x103fffff nomap
framebuffer@10000000`, an idle kernel with no DRM client keeps the logo on the
glass for a 90 s hold, and two filmed boots show the logo until the
compositor's first frame. Transient1–4frame scanout glitches during early userspace were subsequently
removed in two observed normal warm boots after the bounded stage1 DMA-request
correction; the final film has a reviewed±75.244ms timing bound
(`docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/README.md`).
The correction does not establish a FIFO-underrun mechanism.*

#### Scenario: The compiled device tree is inspected

- **WHEN** someone reads the daily device tree's `/reserved-memory`
- **THEN** a framebuffer node whose `reg` equals stage 1's splash address and size is present

#### Scenario: A boot carries the splash to the first display client

- **WHEN** stage 1 lights the panel and the mainline kernel boots to its first DRM client
- **THEN** the splash buffer is unmodified until that client replaces it, as recorded in a capture committed under `docs/evidence/`
