## ADDED Requirements

### Requirement: U-Boot proper is a current upstream release with the vendor-only pieces ported

The stage 1 U-Boot proper SHALL be built from the newest stable upstream
U-Boot release this project has proved on the board, with the board support
that upstream lacks carried as reviewable patches and files in this
repository. It SHALL keep what the 2022.10 build provides: console, SD/MMC
(`mmc 1`), USB gadget mass storage over J3 (`ums 0 mmc 1`), the early display
and splash with its reserved-memory handoff, the `bootargs.txt` flow that
selects `init=`, and the OpenSBI handoff.

*Grounding: upstream v2026.10 contains `configs/k230_canmv_defconfig`,
`arch/riscv/cpu/k230/` and `arch/riscv/dts/k230*.dts*` and documents running
as U-Boot proper behind the vendor SPL (read from the tag on 2026-10-30; see
`design.md`). It contains no K230 MMC, gadget, clock, reset, pinctrl,
cache-enable, SPL or display code. The 2022.10 behaviours to keep are
grounded in `docs/evidence/stage1-from-source.txt`,
`docs/evidence/uboot-ums-enumerate.txt` and `firmware/stage1/tdisplay.env`.
The modern U-Boot itself has not been run on the board.* <!-- UNVERIFIED: no modern U-Boot has run on hardware yet. -->

#### Scenario: The board is powered on with the modern U-Boot installed

- **WHEN** the board boots with the modern U-Boot in the U-Boot slot
- **THEN** the console prints the modern U-Boot banner, the panel shows the splash, and the NixOS login appears as it did before

#### Scenario: The card must be reflashed

- **WHEN** someone runs `ums 0 mmc 1` at the modern U-Boot prompt and connects J3 to a host
- **THEN** the card appears as a USB mass-storage device exactly as it did under 2022.10

### Requirement: Each stage of the move names its proof and its way back

A change to boot firmware in this chain SHALL be staged so that each stage
names the console evidence that proves it and the recovery path that undoes
it. No stage SHALL be written to the board's card before its recovery path is
written down, and a stage whose recovery relies on an unverified route SHALL
say so.

*Grounding: `design.md` of this change; the card-reader floor is the
procedure in `docs/uboot-ums.md` section 6 and was used on 2026-09-22. BootROM
USB recovery is unmeasured (`characterise-bootrom-usb-recovery`).* <!-- UNVERIFIED: BootROM USB recovery with SW3 has not been observed. -->

#### Scenario: A modern U-Boot fails before the console appears

- **WHEN** a written U-Boot never reaches its prompt
- **THEN** the recorded procedure restores the saved 2022.10 slot image from a card reader and the board boots as before
