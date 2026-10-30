## Status (2026-10-30)

**ACTIVE.** The user decided on 2026-10-30: "i want a modern uboot on here
let's just port shit over in a subagent make everything modern i don't want
to be held back by vendor support". Host-provable tasks (stage a, host
builds) proceed now. **No boot firmware is written to the board or the card
by this change without a separately reviewed install and recovery
procedure** (task group 4 is that procedure; group 5 is the write).

## Why

Stage 1 today is a three-year-old U-Boot (2022.10) with Canaan's SDK overlay
rsynced over it, plus OpenSBI 1.4 with another overlay. Every improvement the
project wants in the boot path (a boot animation on a real timer framework, a
current MMC/USB/DM stack, a current compiler without `-Wno-error` and GCC 13
pins, a boot path that matches what the mainline Linux 7.3 kernel expects)
means patching a tree the vendor will not update. The user does not want the
boot path held back by vendor support, so this change moves the project to
the newest stable upstream U-Boot and OpenSBI and ports, rather than waits
for, the pieces upstream lacks.

What stops working if we do nothing: nothing today, but each new boot
feature (the Game of Life change hand-backports U-Boot's cyclic framework
into 2022.10 because 2022.10 lacks it) costs a private fork of old code.

What a person at the board must still see after the move: the same
console, the same splash, `ums 0 mmc 1` over J3, the same
`bootargs.txt`/`init=` selection, the same NixOS boot.

## What Changes

- Add a staged plan from the vendor-SPL chain to an all-upstream chain:
  - stage a: **modern U-Boot proper** (upstream v2026.10, which already has
    `k230_canmv_defconfig`) chained from the existing proven vendor-derived
    SPL, with the vendor pieces upstream lacks forward-ported;
  - stage b: **a modern SPL** with DDR training, replacing the vendor SPL;
  - stage c: **modern OpenSBI** (v1.9) with the one T-Head `MAEE` quirk
    forward-ported.
- Add `nix/` derivations producing a modern U-Boot in the same five-file
  layout `nix/stage1.nix` and the flashing tools already expect.
- Add a RAM-only trial path (stage a0) so the new U-Boot runs on the board
  before anything on the card is written.
- Write down, per stage, the proof and the recovery path.

## Non-goals

- Writing anything to a board or card in the proposal/host phase.
- Mainline kernel changes. The kernel and device tree are unchanged.
- Secure boot, SPI NOR/NAND boot, eMMC boot, the other K230 boards.
- Dropping the vendor DDR PHY training data: it stays an identified,
  vendored blob (`docs/blob-inventory.md` A5-A6) in stage b.
- Moving the splash geometry or the reserved-memory contract (the DT
  `reserved-memory` node and `canaan,stage1-splash` flag stay as they are).

## Needs the physical board?

Stage a host work: no. Stage a0 (RAM trial), stage a install, stages b and c
proof: yes, and each is gated on the recovery procedure in `design.md`.
Hardware-only tasks stay open until their named console proof exists.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `image/boot-chain`: stage 1's U-Boot proper becomes a current upstream
  release; SPL and OpenSBI follow in later stages.
