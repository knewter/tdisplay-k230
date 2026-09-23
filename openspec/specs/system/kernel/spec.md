# system/kernel Specification

## Purpose
Define the pinned Linux kernel and document the board-specific patches and
device-tree differences needed to support the T-Display-K230 panel and touch
controller, so kernel updates can preserve working hardware support.

## Requirements

### Requirement: The kernel is pinned, and its divergence from upstream is recorded

The kernel SHALL be built from a pinned revision of the Xuantie tree used by
Canaan's Linux SDK, and every patch this project carries on top SHALL be
recorded with what it does and why it is needed.

*Grounding: `k230_canmv_v3_defconfig` in `kendryte/k230_linux_sdk` builds
`ruyisdk/linux-xuantie-kernel` at `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`
with the `k230` defconfig.*

The kernel SHALL carry support for this board's panel and touch controller.
Panel support is configuration — a device tree describing the RM69A10 to the
generic Canaan panel support already in the tree. Touch support is a patch,
because the pinned tree predates GT9895 support.

Where this project's device tree diverges from the `k230-canmv-v3` reference,
the divergence SHALL be recorded. The reference describes a different display
— an ST7701 at 480x800 — so the divergence is expected and is the point.

#### Scenario: The kernel derivation is inspected

- **WHEN** someone asks what this project changed about the kernel
- **THEN** the pinned revision, each carried patch, and the device tree divergences from the reference board are all recorded

#### Scenario: A patch is added to the kernel

- **WHEN** a patch is carried
- **THEN** it is recorded with its origin and the reason it is needed, so a later kernel bump can tell whether it is still required
