## Context

See proposal.md — Why. What constrains the approach:

- The vendored chain is `U-Boot SPL 2022.10` → `U-Boot 2022.10` → `OpenSBI v0.9`,
  with a DDR PHY training blob inside SPL and a Canaan-specific compressed image
  header. All observed in `docs/rtsmart-boot-log.txt`.
- U-Boot reports `Model: kendryte k230 canmv v3.0`, and `k230_linux_sdk` carries
  a matching `k230_canmv_v3_defconfig` with `BR2_TARGET_UBOOT_BOARDNAME="k230_canmv_v3"`.
  The board is a CanMV v3 derivative, which is why an official Linux path exists
  at all.
- The shipped card layout is known: raw firmware in sectors 0–102399, then two
  FAT32 partitions at sectors 102400 and 163840.
- The console already works and is well characterised, including its failure
  modes. That is the one part of this change with no unknowns.

## Goals / Non-Goals

**Goals:**

- Our kernel, loaded by the board's own vendored chain, reaching a prompt.
- A flashing procedure that cannot destroy the host's RAID array.
- A committed hardware transcript to ground later requirements.

**Non-Goals:**

- Building stage 1. It stays vendored, and this change pins it rather than
  reproducing it.
- The panel, touch, or radios. Headless is the whole target here.
- eMMC, USB, or network boot.

## Decisions

**Take stage 1 from `k230_linux_sdk`'s `k230_canmv_v3` build, not from the
LilyGO RT-Smart image.** Both would probably boot a kernel, but the RT-Smart
image's U-Boot is configured to load an RT-Smart payload from a raw offset,
while the Linux SDK's is configured to load a kernel from a filesystem. Taking
the one already aimed at our case avoids reverse-engineering boot arguments.
The cost is one buildroot run in Docker on Ubuntu, once.

**Pin stage 1 by content hash as a fixed-output derivation.** The alternative,
committing the binary into the repository, was rejected: it is several
megabytes of opaque vendor output, and a hash plus a recorded provenance says
more about where it came from than a checked-in blob does.

**Flash by `/dev/disk/by-id`, and refuse bare device nodes.** The host has four
8 TB RAID members at `/dev/sd[a-d]` and device letters move when the card
reader is replugged. Accepting `/dev/sdX` at all — even with a confirmation
prompt — leaves a one-character typo between a working session and a destroyed
array. Refusing the form outright is worth the small inconvenience.

**Show the card's contents before writing.** Rejected doing this only on a
`--force` flag. The card in hand was an EverDrive 64 cartridge card holding
306 ROMs, and "the blank one" is exactly the assumption that loses data.

**Reuse the existing console tooling rather than writing new.** `tools/msh.py`
and `tools/probe.py` already speak to this board; the boot capture pattern in
`tools/bootcap.py` produced `docs/rtsmart-boot-log.txt`. They need retargeting
at a Linux console, not replacing.

## Risks / Trade-offs

- **Stage 1 from the CanMV v3 reference does not match this board's DDR.** →
  The most likely hard failure, and it would appear as a hang in SPL before any
  console output. Mitigation: the shipped LilyGO image's stage 1 is known to
  work on this exact board and is the fallback, at the cost of having to learn
  its boot arguments.
- **A destroyed RAID array.** → By-id paths only, bare nodes refused, contents
  shown before writing.
- **A cable fault is mistaken for a boot failure.** → The console spec records
  all three signatures; check the kernel log before suspecting the image.
- **The board is bricked.** → It is not: the boot chain lives on the SD card,
  not in internal flash, so recovery is writing a different card.

## Open Questions

- Whether U-Boot needs a `boot.scr`, an extlinux config, or a fixed filename to
  find our kernel. This is a property of the vendored artifact, discovered by
  reading its environment once it is in hand. It changes a task's contents but
  not the approach or the specs.
