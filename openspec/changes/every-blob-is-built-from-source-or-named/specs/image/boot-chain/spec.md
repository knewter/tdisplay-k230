## RENAMED Requirements

- FROM: `### Requirement: Stage 1 is a pinned vendored artifact`
- TO: `### Requirement: Stage 1 is built from source this project can read`

## MODIFIED Requirements

### Requirement: Stage 1 is built from source this project can read

The boot chain before our kernel — U-Boot SPL, U-Boot 2022.10 and its
environment — SHALL be produced by this project from source, pinned by the
hash of that source rather than of the binary, and SHALL NOT be carried in
the repository as a committed binary. The packaging steps that turn the
compiled output into what the BootROM will load SHALL be expressed in the
flake rather than in a shell script run by hand.

This reverses the previous requirement, which held that stage 1 SHALL NOT be
built from source. The reason it held was a belief that the source was
unavailable or the build unreasonable. Both are false: the source is open and
on disk, and every packaging step has been reproduced with stock tools.

*Grounding: `docs/blob-inventory.md` §A1–A2 and §D. The sources are U-Boot
2022.10 upstream, sha256
`50b4482a505bc281ba8470c399a3c26e145e29b23500bc35c50debd7fa46bdf8`, plus
Canaan's rsync overlay applied by `UBOOT_OVERLAY_DIRS` in the SDK's
`buildroot-overlay/boot/uboot/uboot.mk`, both open. Measured 2026-09-20:
nixpkgs `ubootTools` reproduces the committed `env.env` byte for byte, and
nixpkgs `gzip` plus `mkimage` plus the U-Boot tree's own
`firmware_gen_no_securiy.py` reproduce both committed firmware images byte for
byte from the compiled U-Boot. `readelf -A` reports the compiled SPL as
`rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0` — no vendor ISA — and
the T-Head cache operations are hand-encoded as `.long` words, so the vendor
toolchain is not required to assemble them.*

<!-- UNVERIFIED: no stage 1 compiled by this project has been booted. The
compilation step is the one part not yet reproduced; grounded once
docs/evidence/stage1-from-source.txt records the board reaching a prompt on a
stage 1 the flake built. -->

#### Scenario: Someone needs to change how the board boots

- **WHEN** a person wants the boot command, a memory timing, or the environment to be different
- **THEN** the thing they edit is a file in this repository, and the change reaches the card by rebuilding

#### Scenario: The vendored firmware is inspected

- **WHEN** someone asks where the bootloader on the card came from
- **THEN** the flake names its sources and their hashes, and the build that turns them into what the card carries is the flake's own

## ADDED Requirements

### Requirement: What stays opaque inside stage 1 is named

Building stage 1 from source SHALL NOT be treated as making it transparent.
The parts of it that remain unreadable SHALL be listed by name, size and
sha256, with their location inside the produced binary, so that compiling
them ourselves does not remove them from view.

*Grounding: `docs/rtsmart-boot-log.txt` records this board's SPL printing
`PMU Major Msg: End of CA training` through `Firmware run has completed` —
the Synopsys DDR PHY training firmware running before anything else. It has no
source: it reaches us transliterated into 16 384 `reg_write()` calls in
Canaan's `lpddr4_init_32_swap_2667.c`, which the SDK's `ddr.sh` turns back
into an array at build time. Measured 2026-09-20 and recorded in
`docs/blob-inventory.md` §A5–A6: that image is 32 768 bytes of instruction
memory, sha256
`517aa534255e88c941882be40f5e5735349cd1e3b144b536155e51bdc6309c8b`, plus 1 660
bytes of data memory, and it sits verbatim at offset `0x1fc74` of the
committed SPL — 15.9 % of it.*

#### Scenario: A reader asks whether stage 1 is now fully open

- **WHEN** stage 1 is built from source
- **THEN** the answer is "all but the memory training firmware", and that firmware is named, sized, hashed and located rather than described as "a blob inside SPL"

### Requirement: No vendor executable runs in the firmware build

Producing anything that goes on the card SHALL NOT require executing a binary
this project cannot read. Where the vendor's own build does so, the project
SHALL substitute a readable equivalent and record the evidence that the
substitution changes nothing.

*Grounding: `docs/blob-inventory.md` §A4. The SDK's
`buildroot-overlay/board/canaan/k230-soc/post-image.sh` runs
`tools/k230_priv_gzip`, a stripped x86-64 ELF, to compress U-Boot. Its strings
identify it as GNU gzip 1.6 — the FSF copyright, `Written by Jean-loup
Gailly.`, `bug-gzip@gnu.org`, and gzip's unmodified option table
`ab:cdfhH?klLmMnNqrS:tvVZ123456789`, in which `-n8` is the ordinary `-n -8`.
Measured 2026-09-20 on the SDK's own 693 576-byte `u-boot.bin`: nixpkgs gzip
1.14 produces output identical to the vendor binary at every level the SDK
falls back through. What is actually vendor-specific is a one-byte `sed` on
the following line, flipping the gzip header's CM field to `0x09` so that the
SPL's `k230_priv_unzip()` uses the SoC's hardware decompressor.*

#### Scenario: The firmware build is audited

- **WHEN** someone asks what code ran to produce the bytes on the card
- **THEN** every program involved is one whose source is available, and the vendor binary that used to run is recorded as replaced rather than merely unused
