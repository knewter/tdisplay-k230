## Why

Every time we change the image, a person has to power the board down, pull
the TF card out of it, carry it to a reader, wait for 2.21 GB to be written,
carry it back and power the board up. We did that several times in one
evening. The loop cannot run unattended, it cannot run while nobody is at the
desk, and it makes a one-line kernel change cost the same as a full rebuild.

Stage 1 could hand the card to the host itself. U-Boot's `ums` command
presents a block device over USB, so the host writes the card while it stays
in the slot. The board already has the hardware for it — the data USB-C at
J3 goes straight to the SoC's `usbotg0` — and Canaan already ships a working
USB-gadget configuration for this SoC in the same U-Boot tree we build. See
`docs/uboot-ums.md`.

## What Changes

- Stage 1 gains a USB device mode. At the U-Boot prompt, `ums 0 mmc 1`
  presents the TF card to a host connected to J3 as a mass-storage device.
- `tools/flash-latest.sh` gains a target that writes to that device instead
  of to a card reader. The reader path stays; it is the recovery path.
- The U-Boot configuration we build changes: USB gadget support on, the
  `ums` command on, and `usbotg0` enabled in the board device tree.
- **BREAKING (within stage 1):** in the first variant, U-Boot's USB *host*
  support is turned off, because in U-Boot 2022.10 the dwc2 host and gadget
  drivers both claim `snps,dwc2` nodes and the gadget wins. The board's
  onboard RTL8152 Ethernet therefore stops being reachable *from U-Boot*.
  Nothing in the current boot path uses it — `bootcmd` is `run blinux`, which
  touches only `mmc`. Linux is unaffected. A follow-up restores both.
- We record, as a property of this board rather than a hope, that the TF card
  is its only boot medium, so a stage 1 that does not boot is always
  recoverable in a reader.

Non-goals, named because each is a tempting adjacent thing:

- **Not** replacing vendor U-Boot with mainline. Mainline K230 support landed
  in v2025.04 but is U-Boot proper only — no SPL, no DDR init — and carries
  no gadget support either. Separate change, different payoff.
- **Not** building the BootROM USB recovery path (`k230_flash`) into the
  flake. This change only *records* whether it works, because that determines
  how safely we can iterate on stage 1.
- **Not** rewriting what we write. Making `flash-latest.sh` copy 60 MB into a
  mounted boot partition instead of dd-ing 2.21 GB is the larger speedup and
  it depends on this change, but it is not this change.
- **Not** touching the kernel, the panel, the rootfs or the boot environment.

This change **needs the physical board**. QEMU's `k230` machine models no
block device and no USB controller, so nothing here can be proven under
emulation beyond "U-Boot still compiles".

## Capabilities

**New Capabilities**

- None.

**Modified Capabilities**

- `image/boot-chain` — gains three requirements, about what stage 1 offers a
  host over USB and about how a stage 1 that does not boot is recovered. The
  capability is in `openspec/specs/` (introduced by
  `the-board-boots-what-we-built`, revised by
  `every-blob-is-built-from-source-or-named`, both archived by 2026-09-22).
  The delta is ADDED requirements only; no existing requirement is modified
  or renamed — see design.md, "Why this is an ADDED delta and not a MODIFIED
  one". The requirement this change would once have had to overturn —
  "Stage 1 … SHALL NOT be built from source by this project" — is gone: it
  now reads "Stage 1 is built from source this project can read", and this
  change is the first to use that.

## Impact

- **Stage 1.** A defconfig delta and a one-line device-tree override in the
  Canaan U-Boot tree. No new vendor blob; no change to the SPL, the DDR
  training firmware or OpenSBI.
- **Where U-Boot is compiled: `nix/uboot-k230.nix`.** Written when
  `tools/gen-stage1.sh` packaged a tree built elsewhere; since
  `every-blob-is-built-from-source-or-named` landed, the flake compiles
  U-Boot from pinned sources, so the configuration change is a Kconfig
  fragment (`nix/uboot-k230-ums.config`) and a patch file
  (`nix/patches/uboot-k230/`) that derivation applies, and `nix build
  .#stage1` is the whole rebuild.
- **`tools/flash.sh` / `tools/flash-latest.sh`.** `flash.sh` refuses anything
  that is not a `/dev/disk/by-id` path, for good reasons recorded in its
  header. A `ums` target is a different by-id path, not an exception to that
  rule.
- **`docs/blob-inventory.md`.** Nothing enters or leaves the blob inventory
  — the sources are the same pinned sources, only the configuration
  changes — and `tools/blob-scan.py` says so. There is no committed binary
  whose hash needs refreshing any more; the built hashes live in
  `nix build .#stage1`'s `SHA256SUMS` and in the evidence.
- **Risk to the board: none that a card reader does not fix.** The TF card is
  this board's only boot medium.
