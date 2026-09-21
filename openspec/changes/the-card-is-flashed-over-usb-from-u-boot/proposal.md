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

- `image/boot-chain` — new requirements about what stage 1 offers a host over
  USB, and about how a stage 1 that does not boot is recovered. The
  capability does not yet exist under `openspec/specs/`; it is introduced by
  `the-board-boots-what-we-built` and revised by
  `every-blob-is-built-from-source-or-named`, both in flight. This change
  adds to it rather than modifying it — see design.md, "Why this is an ADDED
  delta and not a MODIFIED one".

**Modified Capabilities**

- None. The requirement this change would have had to overturn — "Stage 1 …
  SHALL NOT be built from source by this project" — is already being
  reversed by `every-blob-is-built-from-source-or-named`, which renames it to
  "Stage 1 is built from source this project can read". This change depends
  on that one landing first and conflicts with nothing once it has.

## Impact

- **Stage 1.** A defconfig delta and a one-line device-tree override in the
  Canaan U-Boot tree. No new vendor blob; no change to the SPL, the DDR
  training firmware or OpenSBI.
- **Wherever U-Boot is compiled.** `tools/gen-stage1.sh` packages an
  already-built tree and does not run `make`, so the configuration change has
  to reach the compile step. That step is being moved into the flake by
  `every-blob-is-built-from-source-or-named`; this change lands on top of it
  rather than creating a second way to build stage 1.
- **`tools/flash.sh` / `tools/flash-latest.sh`.** `flash.sh` refuses anything
  that is not a `/dev/disk/by-id` path, for good reasons recorded in its
  header. A `ums` target is a different by-id path, not an exception to that
  rule.
- **`firmware/stage1/PROVENANCE.txt` and `docs/blob-inventory.md`.** The
  hashes of `fn_ug_u-boot.bin` change. Nothing enters or leaves the blob
  inventory.
- **Risk to the board: none that a card reader does not fix.** The TF card is
  this board's only boot medium.
