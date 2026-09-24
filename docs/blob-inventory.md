# Blob inventory

Every opaque binary this project ships, executes, or would pull in if it
enabled one more option — classified, checksummed, and each one given the
event that would make it go away.

Compiled 2026-09-20. The point is not zero blobs. The point is that no blob is
a *silent* dependency: if we need one we keep it, but it is written down here
with its hash, so that a future reader can ask "has that upstream shipped
source yet?" without re-deriving this whole document, and so that a blob
appearing or disappearing from the tree is a visible diff.

## How to read this

**Class** — what it would take to get rid of it.

| Code | Meaning |
| --- | --- |
| **E1** | **Excisable now.** Open source is in hand and we can build or reproduce it in Nix today. Several of these are *proven* byte-for-byte below. |
| **E2** | **Excisable with effort.** Source exists; building it is a project. The estimate is in the row. |
| **IO** | **Irreducibly opaque.** No source exists anywhere we can reach. Can only be flagged, checksummed and isolated. |
| **NP** | **Not on our path.** A real blob, sitting in a vendor tree we have checked out, that nothing we build touches. Listed so that enabling it later is a deliberate act and not an accident. |
| **DATA** | **Not code.** Images, fonts, sample media, test vectors, certificates, documents. Cannot execute, but is a binary file, and the scanner will not let one go unlisted -- the photographs in `docs/evidence/` are the reason this class exists. |
| **SRC** | **Source, fetched by hash.** Not a blob at all; listed because a nix file pins it and `tools/blob-scan.py` must be told which pinned hashes are text and which are binary. |

**Scope** — whose fault it is. This is the column to read when choosing the
next board.

| Code | Meaning |
| --- | --- |
| `SILICON` | A property of the K230 die. Changing it means changing chip. |
| `CANAAN` | A property of Canaan's SDK or build process, not of the silicon. Someone else's K230 board could avoid it. |
| `LILYGO` | A property of this board's BSP, not of Canaan's. |
| `BOARD` | A property of which parts are soldered to *this* PCB. |
| `INDUSTRY` | Near-universal on modern SoCs. Buying a different chip does not escape it; you only change whose blob it is. |

Every sha256 in this document was computed on 2026-09-20 from the tree
described in `firmware/stage1/PROVENANCE.txt`, and re-verified on 2026-09-22
by `tools/blob-scan.py`, which now enforces the `MANIFEST` section at the
end — the machine-readable form — on every site build. What the scanner
changed is under **Rescan, 2026-09-22** at the very end; the sections
between were written on the 20th and are left as they were, dated.

---

## A. What we ship or execute today

Five blobs are on the live path, plus the one executed during the build that
produced them, two that sit *inside* one of them, and the toolchain that
compiled all five.

**Where they live changed on 2026-09-20, twice, while this was being
written** — see A0 immediately below. The paths in the table are still the
right names for the artifacts; they are just no longer git-tracked.

### A0 — a note on relocating a blob, which is not the same as excising one

At commit `5ee0a7a` the five stage-1 binaries were committed to
`firmware/stage1/`. At `e7f4e6b` they were removed from git: `.gitignore`
now covers `/firmware/stage1/*.bin` and `*.env`, `tools/gen-stage1.sh`
produces them locally, `.github/workflows/stage1.yml` builds the same bytes
in CI and publishes `stage1.tar.gz` to a release, and `nix/stage1.nix`
fetches that release by hash — preferring a local build when
`K230_STAGE1_DIR` points at one under `--impure`.

That is a genuine improvement: the repository stops carrying opaque bytes,
the provenance is explicit, and neither path can substitute different bytes
unnoticed. It changes **nothing** in this inventory's classification. The
same five artifacts, built the same way, by the same Docker container using
the same 1.9 GB vendor toolchain and the same stripped vendor `gzip`, still
end up on the card. A hash on a release tarball records that the blob has
not changed; it does not record what is in it, and it does not let anyone
change it.

Arguably the release is the *harder* thing to audit, because the bytes now
arrive from a URL rather than sitting in the tree where a scan trips over
them. `tools/blob-scan.py` must therefore check the pinned release hash in
`nix/stage1.nix` against this document, not only the files on disk.

This is the distinction the whole document turns on. Vendored, committed,
gitignored and fetched-by-hash are four places to keep a blob. Built from
source is the only one that removes it.

| # | Blob | Bytes | Class | Scope | sha256 |
| --- | --- | --- | --- | --- | --- |
| A1 | `firmware/stage1/fn_u-boot-spl.bin` | 206 596 | **E2** | `CANAAN` | `3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94` |
| A2 | `firmware/stage1/fn_ug_u-boot.bin` | 353 794 | **E2** | `CANAAN` | `c0fb8d95a983c33f3d0a1d7f18de721314878cb3322eaf62fbb1d2788d26b0c4` |
| A3 | `firmware/stage1/env.env` | 8 192 | **E1** | `CANAAN` | `3a9664f43f8d1b50299155cbc8014d69cdb0ed7d12193187e56d9e3c5707e1af` |
| A4 | ~~`tools/k230_priv_gzip`~~ **EXCISED 2026-09-20** | 109 896 | **GONE** | `CANAAN` | `c6d029a05f2d3038fd02f9b18716b595f4e8beeebca33f3598328fbde99bf11e` |
| A5 | DDR PMU training firmware, imem — *inside A1* | 32 768 | **IO** | `INDUSTRY` | `517aa534255e88c941882be40f5e5735349cd1e3b144b536155e51bdc6309c8b` |
| A6 | DDR PMU training firmware, dmem — *inside A1* | 1 660 | **IO** | `INDUSTRY` | `1c0819e81446a8944a3ecf95304642ecec2071451d430e21925e5d7daea47313` |
| A7 | `Xuantie-900-gcc-linux-6.6.0-glibc-x86_64-V3.0.2-20250410.tar.gz` | ~1.9 GiB unpacked | **E2** | `CANAAN` | not recorded upstream — **md5 only**: `8cefc7e94f760eaecc3620ffb238bf4a` |
| A8 | K230 BootROM | unknown | **IO** | `SILICON` | unreadable |
| A9 | `firmware/stage1/fw_jump.bin` | 270 728 | **E1** | `CANAAN` | `023b5495c9450af553c24d8c518cf8f191c9ed8e5622e7a7405007172cb4fb10` |
| A10 | `firmware/stage1/fw_jump_add_uboot_head.bin` | 270 792 | **E1** | `CANAAN` | `d0279bc93038793906764d22dfea298d82a89999dd0b26b23d69cce98497e544` |

### A1, A2 — the SPL and the compressed U-Boot

**What it is.** U-Boot 2022.10 and its SPL, built from
`kendryte/k230_linux_sdk` at `1104236` with `k230_canmv_v3_defconfig`, each
wrapped in a Canaan firmware header (magic `K230`, SHA-256 integrity, no
encryption). A2 additionally carries a U-Boot legacy image header around a
gzip stream.

**Source exists, and we have it.** U-Boot 2022.10 is GPL-2.0 upstream
(`u-boot-2022.10.tar.bz2`,
sha256 `50b4482a505bc281ba8470c399a3c26e145e29b23500bc35c50debd7fa46bdf8`).
Canaan's changes are not a patch series but an **rsync overlay** —
`buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/`, applied by
`UBOOT_OVERLAY_DIRS` in `buildroot-overlay/boot/uboot/uboot.mk:581` — under
the SDK's BSD-2-Clause licence. Every file involved is text.

**So why are these committed as binaries?** `firmware/stage1/PROVENANCE.txt`
answers "because a fixed-output derivation needs a URL and these were built
here, not downloaded". That is a true statement about fixed-output
derivations and a false dichotomy about the alternatives: the third option,
never considered, is an *ordinary* derivation that fetches the two sources
above and compiles them. The reason the binaries exist is that the build was
done in Docker with a 1.9 GB vendor toolchain before anyone asked whether Nix
could do it. That is a reasonable way to get a first artifact and a bad place
to stop.

**Cost of replacing.** Half the work is already proven done (see §D). The
remaining half is compiling `u-boot.bin` and `u-boot-spl.bin` with
`pkgsCross.riscv64` instead of Xuantie GCC — estimated **one to two days**,
with two known risks: U-Boot 2022.10 against nixpkgs GCC 15.3.0 is a
three-year version gap and older U-Boot trees routinely need `-Wno-` patches
for newer GCC; and `CONFIG_SPL_SIZE_LIMIT=0x80000` means a larger-codegen
compiler could overflow the SPL. Neither is a blocker, both are a day.

**Risk of not replacing.** We cannot change stage 1. That is not academic:
`docs/evidence/uboot-env.txt` already records that the environment's
hardcoded `blinux` command, not extlinux, is what boots us, which costs us
NixOS generations at the boot menu. Rewriting the environment is easy (A3 is
already reproducible); rewriting U-Boot to run `sysboot`, add a panel splash,
or fix a DDR timing is not, while it is a binary. We also cannot rebuild it
if the SDK is pulled, and we cannot answer "what is in it" except by
disassembly.

**Unblocking event.** None needed. Both sources are already on disk. This is
work, not waiting.

**Next device.** `CANAAN`, not `SILICON`. A vendor that ships a git tree with
a tag instead of an rsync overlay over a three-year-old release costs a
morning here instead of two days. Boards whose U-Boot support is *mainline*
(the JH7110 family, SiFive Unmatched) cost nothing at all. Ask, before
buying: **is the bootloader upstream, a patch series, or a tarball drop?**

### A3 — the U-Boot environment

**Status: excisable now, and the excision is proven.** `env.env` is
`mkenvimage -s 0x2000` over
`buildroot-overlay/board/canaan/k230-soc/env/default.env`, which is 40 lines
of plain text. Running nixpkgs `ubootTools` (uboot-tools 2026.07) against
that file reproduces the committed blob **byte for byte**:

```
$ nix shell nixpkgs#ubootTools -c mkenvimage -s 0x2000 -o env.env \
    .../buildroot-overlay/board/canaan/k230-soc/env/default.env
f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957  env.env   # identical
```

There is no argument for carrying this as a binary. It should be a
`runCommand` over a text file in the repository, which also makes the boot
command reviewable in a diff.

### A4 — `k230_priv_gzip`, the one we should be angriest about

**What it is.** A stripped x86-64 ELF in *both* vendor SDKs (same
`BuildID[sha1]=73aabd51455cae138ef23eacb3ad1be60bf200cf`), executed by
`buildroot-overlay/board/canaan/k230-soc/post-image.sh:92` to compress
U-Boot. We ran an unauditable vendor binary to produce firmware.

**It is GNU gzip 1.6.** Its strings carry `Copyright (C) 2007, 2010, 2011
Free Software Foundation, Inc.`, `Written by Jean-loup Gailly.`, `Report bugs
to <bug-gzip@gnu.org>`, the GPL notice, the version string `1.6`, and gzip's
exact option table including the unmodified getopt string
`ab:cdfhH?klLmMnNqrS:tvVZ123456789`. Canaan distributes a GPL binary,
stripped, with no source and no written offer. **We are entitled to the
source and have never had to ask for it — see below.**

**`-n8` is not a custom flag.** In gzip's getopt string `n` takes no
argument, so `-n8` parses as `-n -8`: "no name/timestamp" plus "level 8".
Ordinary gzip.

**Proven substitutable, byte for byte.** Compressing the SDK's own
`u-boot.bin` (693 576 bytes) with both:

```
$ ./k230_priv_gzip -n8 -f -k u-boot.bin      # vendor binary
$ gzip -n -8 -f -k u-boot.bin                # nixpkgs gzip 1.14
2051b07f1edbf8aebca5f512b1f72eba33b9c97934b4bb8c2ed0cfd1039e57d3   both
```

Identical at every level the SDK falls back through — 4, 5, 6, 7, 8 and 9 —
and identical again on an unrelated 300 KB sample. Whatever Canaan changed,
it does not change the output.

**What "priv" actually means, and it is not the compressor.** The privacy is
one `sed` on the *next* line of `post-image.sh`:

```sh
set -e ; sed -i -e "1s/\x08/\x09/"  ${filename}.gz;
```

That flips the gzip header's CM byte from `0x08` (deflate) to `0x09`, an
invalid value used as a private signal. The K230 SPL's own `gunzip()`
override in `arch/riscv/cpu/k230/unzip.c` reads it: CM `0x09` means "decompress
with the SoC's hardware ugzip DMA engine" (`k230_priv_unzip()`, registers at
`UGZIP_BASE_ADDR` 0x80808000), and anything else falls through to the
software `stand_gunzip()`. A one-byte marker, shipped as a 110 KB stripped
binary with a misleading name.

**Finding, recorded rather than hidden: our own pipeline omits that `sed`.**
`tools/gen-stage1.sh` reproduces `gen_uboot_bin()` but not `k230_gzip()`'s
trailing `sed`. The committed A2 confirms it — the gzip stream begins at
offset 596 and its CM byte is `0x08`:

```
$ python3 -c '...'   # find 1f 8b in fn_ug_u-boot.bin
gzip magic at 596 CM byte = 0x8
```

So the SPL we are about to boot will take the **software** decompression
path, not the hardware one. It should still work — `CONFIG_SPL_GZIP=y` is set
and `nm spl/u-boot-spl` shows both `zunzip` and `k230_priv_unzip` linked —
but it is slower and it is not what the vendor ships or tests. Either restore
the `sed` or decide deliberately that the software path is fine; do not leave
it as an accident.

**Cost of replacing.** Zero. Replace `tools/k230_priv_gzip` with
`pkgs.gzip`, re-add the one-byte `sed` (or `printf`), and verify against the
hashes above.

**Risk of not replacing.** Running a stripped vendor binary in the firmware
build is a supply-chain hole that a hash on the *output* does not close, and
it forces the build to keep an x86-64 host dependency and a glibc of the
right vintage. There is no upside.

**Unblocking event.** Already happened; nothing to wait for.

**Next device.** `CANAAN`, and specifically embarrassing. A hardware
decompressor in the boot ROM path is a fine idea (i.MX and Rockchip both do
compression tricks); signalling it with an out-of-spec magic byte applied by
a renamed GPL binary is not. Ask, before buying: **does the image-packaging
pipeline consist of scripts, or of executables?** If a vendor's build runs a
binary you cannot read, assume there is a one-line reason for it and that
nobody will tell you what it is.

### A5, A6 — the DDR PMU training firmware. The worst one.

**What it is.** The Synopsys DWC LPDDR4 PHY contains a small embedded
microcontroller ("the PMU") that runs a firmware image to train the DRAM
interface at boot — read enable, write levelling, per-DQ deskew, delay-centre
optimisation. The firmware is 16 384 16-bit instruction words (32 KiB, imem)
plus 830 data words (1 660 bytes, dmem).

**It is in "source", and that changes nothing.** There is no `.bin` in the
tree. The firmware is transliterated into **C register writes** inside
`board/canaan/k230_canmv_01studio/lpddr4_init_32_swap_2667.c` (1 059 036
bytes, 18 687 lines, sha256 `f01452416c6f5a19bbdb915845090fb826e3e616bab2016d91383eba7407562b`)
— lines 716–17 099 are the imem, lines 17 104–17 958 the dmem. The SDK's
`arch/riscv/cpu/k230/ddr.sh` rewrites those into `static const unsigned
short[]` arrays at build time, under Canaan's BSD-3 header.

So this is the crucial correction to the assumption in
`openspec/config.yaml` and `nix/stage1.nix`: **building U-Boot from source
does not remove this blob.** It removes the *packaging*; the 32 KiB of
Synopsys microcode simply gets compiled by us instead of by Canaan.

**Confirmed present in what we committed.** The 32 768-byte imem appears
verbatim at offset `0x1fc74` of `firmware/stage1/fn_u-boot-spl.bin`, and the
dmem at `0x1f5f4`. The imem alone is **15.9 % of the SPL**. The messages it
prints on the way past are in `docs/rtsmart-boot-log.txt` — `PMU Major Msg:
End of CA training` through `Firmware run has completed` — and the matching
`%08X: PMU Major Msg:` format strings are in the committed SPL.

**Is there source? No.** Synopsys ships DDR PHY training firmware to
licensees as imem/dmem images under NDA. Neither Canaan nor anyone else
publishes it. The C file is not source in any useful sense; it is a hex dump
with `reg_write(` around each word.

**Cost of replacing.** A clean-room DDR4/LPDDR4 training implementation is a
research project measured in **person-years**, and it is a project nobody has
completed for any Synopsys PHY. Treat as impossible.

**Risk of not replacing.** Bounded but real. It runs before anything of ours,
in M-mode, with full access to the machine, and we cannot audit it. It is
also frozen: if the LPDDR on this board is marginal at 2667 MT/s we can change
the *register configuration* around it (which is ordinary C we can read) but
not the training algorithm. Practically, this is the blob we accept.

**Unblocking event — the thing to check for in five years.** Any of: (a)
Synopsys publishing training firmware source, which would be unprecedented;
(b) a clean-room LPDDR4 trainer for the DWC PHY appearing in
`openSBI`/`oreboot`/coreboot — coreboot has fought this exact fight on Intel
MRC and lost it, so watch that space rather than this one; (c) moving to a
SoC whose DDR controller trains in hardware with no firmware at all.

**Next device — and this is the row worth internalising.** `INDUSTRY`. The
Synopsys DWC DDR PHY and its PMU firmware are in i.MX8, Rockchip RK35xx,
Amlogic, TI K3, Qualcomm, and StarFive JH7110. You do not escape it by
leaving Canaan, or by leaving RISC-V. What *does* vary is how it is
delivered, and that is what to ask about:

- **Best case:** the firmware is redistributable and lives in a normal
  package your distro already carries (`firmware-imx`, `rkbin` under a clear
  licence). You still ship a blob, but you ship it like a blob.
- **Middling (this board):** it is redistributable and embedded in the
  bootloader source, so you build it yourself and it disappears into the SPL.
  Inventoried here rather than visible as a file.
- **Worst case:** it is not redistributable, and a working image cannot be
  built from public inputs at all.

The genuinely different answer is an SoC with **DDR3 or a self-training
controller** — older or smaller parts, an FPGA soft controller, or something
with on-package LPDDR whose training is pre-characterised in ROM. That is a
real trade (less bandwidth) rather than a licensing preference. If the next
device must have LPDDR4 or better, budget for this blob and stop looking.

### A7 — the Xuantie GCC toolchain

**What it is.** T-Head's RISC-V GCC 14.1.1 (`Xuantie-900 linux-6.6.0 glibc
gcc Toolchain V3.0.2 B-20250410`), 1.9 GB unpacked, downloaded by
`tools/install_toolchain_and_depend.sh` over HTTPS from
`download.kendryte.com` and verified with **md5 only**. It is what produced
A1 and A2.

**Is it needed?** For stage 1, almost certainly not, and the evidence is
strong:

- `readelf -A` on both `u-boot` and `spl/u-boot-spl` reports
  `Tag_RISCV_arch: "rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0"`.
  Plain `rv64imac` plus the two standard Zi extensions. **No vector, no
  XTheadC, no vendor ISA at all.**
- The T-Head-specific cache maintenance ops in
  `arch/riscv/cpu/k230/cache.c` are hand-encoded as raw words —
  `asm volatile(".long 0x0295000b")  /* dcache.cpa a0 */` — precisely so that
  an assembler without T-Head support can build them. `objdump` finds no
  `th.` mnemonics in the SPL.
- The vendor CSRs (`CSR_MHCR`) are written by number through `csr_write`.

nixpkgs at the flake's pin provides
`riscv64-unknown-linux-gnu-gcc-wrapper-15.3.0`, which targets `rv64gc` and
will assemble all of the above.

**Is it in nixpkgs?** Not as the Xuantie toolchain. Its source is public
(`XUANTIE-RV/xuantie-gnu-toolchain`) but packaging a second GCC to build a
bootloader that needs no vendor extensions would be absurd.

**Cost of replacing.** Folded into A1/A2: one to two days, same task.

**Risk of not replacing.** A 1.9 GB unpinned download verified by MD5 over a
vendor CDN is a plain supply-chain risk, and it puts a Docker-and-Ubuntu step
between the repository and a bootable image — the very thing
`PROVENANCE.txt` says committing the blobs was meant to avoid. It did not
avoid it; it deferred it to whoever next needs to change stage 1.

**Unblocking event.** None. Do the work.

**Next device.** `CANAAN` bleeding into `INDUSTRY`. Vendor toolchains are
endemic in the RISC-V SoC world (T-Head, Andes, SiFive all ship one) and
usually unnecessary for the bootloader while genuinely useful for
vector-optimised userland. Ask, before buying: **does the vendor's
bootloader defconfig require the vendor toolchain, or merely default to it?**
Check `Tag_RISCV_arch` on a prebuilt image; it takes thirty seconds and it
answered this question here.

### A8 — the K230 BootROM

Masked into the die. It is what loads A1 from raw offset 0x100000, and its
firmware-header format is why A1 and A2 carry the `K230` magic at all.
Unreadable, unreplaceable, unavoidable. `SILICON`, and every SoC has one.
Listed for completeness so the chain in `openspec/specs` has no unnamed link.

---

### A9, A10 — OpenSBI, committed 2026-09-20 after this inventory was first compiled

**What it is.** OpenSBI 1.4, built from source in the same Docker container
as A1/A2, from `riscv-software-src/opensbi` plus Canaan's nine-file overlay at
`buildroot-overlay/boot/opensbi/opensbi-1.4-overlay/`, generic platform,
`FW_TEXT_START=0`. A10 is A9 with a U-Boot legacy image header
(`mkimage -A riscv -O linux -T kernel -C none -a 0 -e 0 -n linux`), because
`docs/evidence/uboot-env.txt` records that stage 1 `ext4load`s
`/fw_jump_add_uboot_head.bin` from the boot partition and `bootm`s it.

**These arrived while this document was being written, which is the argument
for the document.** `firmware/stage1/PROVENANCE.txt` says so itself: "Note for
the blob inventory: unlike the DDR training firmware, this is compiled from
published source ... It is committed for the same build-convenience reason as
U-Boot, not because source is unavailable, and building it inside the flake
would remove it from the tree entirely." That is exactly right, and it is also
exactly how a tree accumulates blobs — one well-reasoned convenience at a
time, each individually defensible. Class **E1**: nothing has to be waited
for, and the whole overlay is 9 files of readable C.

**A real difference to check before swapping in nixpkgs OpenSBI.** The
tempting move is `pkgs.opensbi` (1.8.1 at the flake's pin). Upstream v1.8
*does* carry `canaan,kendryte-k230` in
`platform/generic/thead/thead-generic.c`'s match table — but with
`thead_pmu_quirks` only. Canaan's 1.4 overlay matches the same compatible with
`THEAD_QUIRK_DISABLE_MAEE` and calls `thead_disable_maee()`, clearing
`MXSTATUS.MAEE` so that standard RISC-V page-table attribute bits behave;
upstream's `c9xx_errata.h` has no such quirk bit at all. So the two are not
equivalent, and MAEE left enabled is the kind of fault that shows up as a
kernel that boots and then corrupts memory under load.

**Unblocking event.** None for the *blob* — build it in the flake. For the
*version*: upstream OpenSBI gaining a MAEE quirk for the K230, or evidence
that our kernel does not need it. Until one of those, build Canaan's 1.4 plus
its overlay from source rather than substituting a newer upstream.

**Next device.** `CANAAN`, shading into `INDUSTRY`. OpenSBI itself is the good
news story in RISC-V: BSD-2-Clause, upstream, and it already knows this chip's
compatible string. That a vendor still ships a nine-file overlay against a
four-release-old version is a process choice. Ask, before buying: **how far
behind upstream is the vendor's OpenSBI, and what is in their delta?** Nine
readable files is fine. A fork is not.

### A11 — MVX codec microcode compiled into the kernel

The running Linux kernel has another opaque-code boundary that was missing
from the original table: the Canaan/Arm-China MVX V4L2 video codec driver.
`nix/kernel-src.nix` pins the source and the pinned `k230_defconfig` sets
`CONFIG_VPU_CANAAN=y`, so `drivers/media/platform/canaan/vpu/Makefile` links
`amvx` into the running kernel. This is not an optional RT-Smart library and
not a `/lib/firmware` lookup.

`mvx_firmware_cache.c` selects six compiled-in microcode arrays: H.264 decode
271,104 bytes (`fw_h264dec.c`), H.264 encode 361,472 (`fw_h264enc.c`), HEVC
decode 219,392 (`fw_hevcdec.c`), HEVC encode 353,664 (`fw_hevcenc.c`), JPEG
decode 184,192 (`fw_jpegdec.c`), and JPEG encode 277,760 (`fw_jpegenc.c`).
They are opaque instruction/data words embedded in source arrays, so this
codec path is **not blob-free**. Disabling the general redistributable firmware
set does not remove them, and no external firmware package supplies them.

The source notice needs qualification rather than a casual license claim: each
array file carries Canaan Bright Sight BSD-3-style redistribution conditions
and `SPDX-License-Identifier: GPL-2.0-only`; the surrounding MVX driver files
also carry an Arm Technology (China) confidential/proprietary notice alongside
GPL text. That is not a clean independent-redistribution conclusion. It needs
vendor/legal review if the project distributes a rebuilt kernel containing the
arrays. This correction does not add a manifest binary row: the payloads are
compiled from the pinned kernel source, rather than files in this repository.
See `docs/evidence/mvx-v4l2-audit.md` for source paths, the V4L2 capability
contract, and a non-streaming live-board probe.

## B. Blobs the Linux path would pull in

Except for B12, none of these is on our path *today*. Each is one defconfig
line away, and `k230_canmv_v3_defconfig` already sets most of those lines —
so if we ever build the SDK's rootfs rather than our own NixOS closure, they
arrive silently. That is exactly the accident this table exists to prevent.

| # | Blob | Count / size | Class | Scope | Note |
| --- | --- | --- | --- | --- | --- |
| B1 | `package/libnncase` — `nncase_k230_v2.11.0_runtime_linux.tgz` | 1 download | **IO** | `SILICON` | sha256 `28680932ac879d8591fbaaaab7b8c1ee2d305c2a82471fb2f38c449316cfb91f` |
| B2 | `package/libnncase` — `nncaseruntime_k230-2.11.0-py3-none-linux_riscv64.whl` | 1 download | **IO** | `SILICON` | sha256 `525e4611b587afb1ab406548ddc6a5e1add3e5fa74ff2829da9441d4a62f3075` |
| B3 | `package/aic8800/fw/**`, `package/aic8800_sdio/src/fw/**` | 103 files, 8.8 MB | **NP** / **IO** | `BOARD` | AICSemi radio firmware for a chip not on this board |
| B4 | `rootfs_overlay/etc/firmware/fw_bcm43438a1.bin` | 402 784 B | **NP** / **IO** | `BOARD` | sha256 `c11b83cfb92b9b01cdfb7150c75674c69563add2c8c1e71df1dc741694aae5a4` |
| B5 | `rootfs_overlay/boot/nuttx-7000000-uart2.bin` | 176 348 B | **NP** / **IO** | `CANAAN` | sha256 `6a35357449419dd493b201487f1a8467298dce0b990ad061bd00962a039c0b88` |
| B6 | `*.kmodel` (ai2d, face_detect, yolo×4) | 6 files, 14 MB | **NP** | `SILICON` | compiled NPU graphs; hashes in MANIFEST |
| B7 | `package/opencv4/3rdparty/csi-cv/libcsi_cv_c908v.a` | 1 file | **NP** / **IO** | `SILICON` | T-Head CSI-CV kernels for the C908 vector unit |
| B8 | `package/k230_assistant/dist/lib/*.a` | 7 files | **E1** | `CANAAN` | cJSON, mbedTLS, libsrtp2, usrsctp, libpeer — all upstream open source, vendored as `.a` purely for convenience |
| B9 | `package/rtl8733bs` downloads (wifi, bt, rtwpriv tarballs) | 3 downloads | **E2** | `BOARD` | Realtek *source* drops, not blobs, but pinned to `download.kendryte.com` |
| B10 | `package/ai2d_kpu/{input,ai2d_input,result}.bin` | 3 files | **NP** | `CANAAN` | KPU test vectors, not firmware |
| B11 | `package/audio_rec_play/audio.pcm`, `SourceHanSansSC-Normal-Min.ttf` | 2 files | **NP** | — | sample assets; listed only so the scan is complete |
| B12 | `8189fs.ko` embedded RTL8188F firmware array | 1 module, 4 988 584 B | **IO** | `BOARD` | Realtek payload compiled from `hal/rtl8188f/hal8188f_fw.c`; module sha256 `a78f80fd9f04c9ed381cc786b26fa32d15b0e037a3ce4d9c376eb6361bf49fe1` |

### B1, B2 — the NPU runtime. The second-worst one.

nncase is published Apache-2.0 at `kendryte/nncase`, which is what makes it
tempting to assume the K230 NPU stack is open. **It is not.** Checked
2026-09-20 via the GitHub API: `modules/` on `master`, `release/2.0`,
`release/3.0` and `dev/3.0` contains `Nncase.Modules.K210`,
`Nncase.Modules.StackVM`, `Nncase.Modules.NTT`, `k210` and `vulkan` — and no
K230 module on any branch. The K230 runtime ships only as the release tarball
and wheel above, and in the RT-Smart tree as
`libnncase.rt_modules.k230.a` (C3 below).

**Unblocking event.** Kendryte publishing `modules/k230` in the nncase repo —
a `feature/refactor_k230` branch exists, so the code is not imaginary, it is
just not released. Check that path on a future nncase tag. Failing that, a
reverse-engineered KPU driver, of which there is no sign.

**Risk of not replacing.** None today; we do not use the NPU. It becomes a
hard blocker the moment anything wants on-device inference, and it would be a
*closed userspace library* dependency inside an otherwise-Nix system, which is
worse than a firmware blob because it constrains the whole libc/toolchain
story around it.

**Next device.** `SILICON`, and this is the general rule: **NPUs are where
open SoC stacks go to die.** Rockchip's RKNN, Amlogic's NPU, and the K230 KPU
are all closed userspace runtimes. The only accelerators with credible open
stacks are GPUs with Mesa drivers. If the next device needs ML and needs to be
auditable, plan to run on CPU or on a GPU Mesa supports, and treat any "TOPS"
number in a datasheet as a closed-source number.

### B3, B4, B12 — radio firmware

The defconfig sets `BR2_PACKAGE_AIC8800=y` and `BR2_PACKAGE_RTL8733BS=y`
because `k230_canmv_v3_defconfig` targets Canaan's reference board.
`docs/findings.md` records that *this* board carries an RTL8189FTV on SDIO
(MMC1, enable on GPIO45). So 8.8 MB of AICSemi RF firmware and a Broadcom
BCM43438 image are dead weight we would ship by inheritance.

**The selected driver does not load a firmware file, but it is not blob-free.**
`BR2_PACKAGE_RTL8189FS=y` resolves to buildroot's own package, which fetches
`jwrdegoede/rtl8189ES_linux` at `94cc959d`. Its GPL-noticed driver source
builds a kernel module, while `hal/rtl8188f/hal8188f_fw.c` contributes an
embedded prebuilt Realtek firmware array to that module. There is no separate
firmware-file dependency and the source notices do not establish a license or
redistributability conclusion for the payload. Its owner is **REALTEK**; its
scope is `BOARD`, because choosing this radio causes the dependency. B12
names and checksums the built module so the payload is not silent.

**Next device.** `BOARD`. Wi-Fi is the one area where the part number decides
everything and the SoC decides nothing. Ask, before buying: **is the radio
supported by an in-tree mac80211 driver?** An out-of-tree Realtek vendor
driver (rtl8733bs, and the rtl8189 fork above) is a per-kernel-version
maintenance tax forever; an in-tree one is free.

### B5 — `nuttx-7000000-uart2.bin`

A prebuilt NuttX image for the K230's second (800 MHz) core, installed into
`/boot`. We do not use the small core. Flagged because a blob in `/boot` is
exactly the kind of thing that gets copied forward without anyone asking what
it is. `CANAAN`: NuttX is open source (Apache-2.0) and this is a build
artifact, so it is E1 in principle — but only if we ever want it.

---

## C. Blobs in the LilyGO RT-Smart SDK

`repo/` is gitignored — a 2.5 GB upstream clone, not committed — and RT-Smart
is the firmware we are *replacing*. Listed because `docs/findings.md` keeps
the RT-Smart Wi-Fi path alive as a fallback, and because it is the clearest
picture available of what the K230 ecosystem looks like when nobody is
resisting.

| # | Blob | Count | Class | Scope | Note |
| --- | --- | --- | --- | --- | --- |
| C1 | `mpp/kernel/lib/*.a` | 14 | **IO** | `SILICON` | VPU, VICAP, VO, DPU, MMZ — the media hardware drivers |
| C2 | `mpp/userapps/lib/*.a` | 39 | **IO** | `SILICON` | ISP (`lib3a.a`, `libcam_engine.a`), codecs, camera HAL |
| C3 | `libs/nncase/riscv64/**/*.a` | 4 | **IO** | `SILICON` | incl. `libnncase.rt_modules.k230.a` (545 398 B) and `libNncase.Runtime.Native.a` (20 MB) |
| C4 | `.../realtek/wlan_lib/libwlan_v1_1.a` | 1, 2.6 MB | **IO** | `BOARD` | sha256 `e776d472979e32d761fd22a6c1f69e1bdee6aa32663169e684900e61eb08dd43` |
| C5 | `libs/opencv/lib/*.a` | 25 | **E1** | `CANAAN` | OpenCV, BSD-3 upstream; vendored prebuilt only |
| C6 | `libs/kmodel/**`, examples | 87 + 19 | **NP** | `SILICON` | compiled NPU models and demo assets |
| C7 | `rtsmart/tools/udb-tools/linux/udb` | 1 | **NP** | `CANAAN` | stripped x86-64 host debug tool, sha256 `6e5eac63398ecf18dd8327585232c2245d0087a699b6a964291b35660f8a94f7` |
| C8 | `src/uboot/uboot/tools/k230_priv_gzip`, `tools/k230_priv_gzip` | 2 | **E1** | `CANAAN` | same binary as A4, same BuildID |
| C9 | `repo/firmware/CanMV-K230-V3P0_rtsmart_release{V1.2,V1.3}.zip` | 2 | **IO** | `LILYGO` | the shipped images; evidence, not a dependency |

### C4 — `libwlan_v1_1.a`, and why the RT-Smart Wi-Fi fallback is worse than it looks

`docs/findings.md` diagnoses RT-Smart's dead Wi-Fi precisely: `Set_WLAN_Power_On()`
is an empty stub, so GPIO45 is never driven, and `RT_USING_REALTEK` defaults
to `n`. Both are two-line fixes in source. What that analysis does not say is
that the driver *core* underneath them — 2.6 MB of `libwlan_v1_1.a` — is a
prebuilt Realtek archive with no source in the tree.

This matters for the plan, not just the inventory: the Linux path gets this
radio through `rtl8189ES_linux`, which is **GPL source** (B3 above). The
RT-Smart path gets it through a **binary blob**. If the RT-Smart fallback is
ever taken, it trades a source driver for a blob one, and that should be a
recorded decision rather than a discovery.

**Unblocking event.** Realtek releasing `wlan_lib` source, which will not
happen. Or: do not take the fallback.

---

## D. What was proven, not asserted

Three reproductions were run on 2026-09-20 against the SDK build described in
`firmware/stage1/PROVENANCE.txt`. They are the reason §A's classes are what
they are.

**1. `k230_priv_gzip` is stock gzip.** Vendor binary and nixpkgs gzip 1.14
produce identical output on the real `u-boot.bin` at levels 4, 5, 6, 7, 8 and
9, and on an unrelated sample.

**2. `env.env` reproduces exactly** from nixpkgs `ubootTools` and the SDK's
`default.env`.

**3. The entire stage-1 packaging pipeline reproduces exactly**, given the
compiled `u-boot.bin` and `u-boot-spl.bin`, using nothing but nixpkgs `gzip`,
nixpkgs `ubootTools` `mkimage`, nixpkgs `python3`, and the U-Boot tree's own
`tools/firmware_gen_no_securiy.py` (a 100-line open Python script):

```
SOURCE_DATE_EPOCH=1789941473
gzip -n -8 -f -k u-boot.bin
mkimage -A riscv -C gzip -O u-boot -T firmware -a 0 -e 0 -n uboot \
        -d u-boot.bin.gz ug_u-boot.bin
python3 firmware_gen_no_securiy.py -i ug_u-boot.bin -o fn_ug_u-boot.bin -n
python3 firmware_gen_no_securiy.py -i u-boot-spl.bin -o fn_u-boot-spl.bin -n

0f8feb747ef4437afbe26b9081c19acbd99475086f2b82db64cc3d3195c54579  fn_ug_u-boot.bin   # identical
3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94  fn_u-boot-spl.bin  # identical
```

`SOURCE_DATE_EPOCH` is required because `mkimage` stamps the build time into
the image header; with it, the pipeline is deterministic.

Only the compilation step remains vendor-bound, and §A7 shows the ISA does
not require the vendor compiler.

---

## E. Keeping this current

The `MANIFEST` below is the stable, diffable form: `sha256  path`, sorted by
path, one per line, with a class tag. It exists so that

- a blob changing its hash shows up as a one-line diff in review, and
- a blob appearing in the tree with no MANIFEST entry can be made a **build
  failure** rather than something someone has to remember to notice.

Two mechanisms are proposed in the change that accompanies this document
(`openspec/changes/every-blob-is-built-from-source-or-named/tasks.md`):

1. **`tools/blob-scan.py`** — walks the committed tree plus any vendor
   checkout it is pointed at, classifies each file as text or binary, and
   exits non-zero on any binary not listed here. The check is "every blob is
   in the inventory", not "there are no blobs".
2. **Rendering on the spec site needs no new code.** `scripts/render_specs.py`
   copies any `docs/…` path cited from a `*Grounding:*` line into the site and
   serves it at `/evidence/<slug>/`. A requirement citing
   `docs/blob-inventory.md` therefore publishes this document automatically,
   and `scripts/build_site.py` already fails when a cited evidence file is
   missing.

### MANIFEST

Verified 2026-09-20 at commit `5ee0a7a`: all 20 file-backed rows below
reproduce. The five `firmware/stage1/` rows became untracked at `e7f4e6b`
(A0); they still verify against a local `tools/gen-stage1.sh` build, and
`tools/blob-scan.py` must additionally check the release hash pinned in
`nix/stage1.nix`. Extract the
`sha256  path` pairs — expanding `(sdk)` to `.build/k230_linux_sdk/` and
`(lilygo)` to `repo/canmv_k230/`, and skipping `embedded:`, `dl:` and
`group:` rows — and pipe them to `sha256sum -c`. `tools/blob-scan.py` (see
above) is the automated form of that check plus the reverse direction: a
binary in the tree with no row here.


Paths are relative to the repository root. `(sdk)` is
`.build/k230_linux_sdk/`, `(lilygo)` is `repo/canmv_k230/`. Entries marked
`embedded` are not files; they are byte ranges inside another entry, recorded
so that building stage 1 from source does not silently drop them from view.

```
DATA  6d8dcad4ca99e9550f8d22bcb9a1648ce97151d72326428a81017f1b02ec382b  docs/evidence/omarchy-themes/board-switching/dark.png
DATA  1be738a33a276fe9b424a38a86568541b2227c885c19aa2b2aec72f3cae5b87f  docs/evidence/omarchy-themes/board-switching/light.png
DATA  6d8dcad4ca99e9550f8d22bcb9a1648ce97151d72326428a81017f1b02ec382b  docs/evidence/coherent-shell/refined-installed/drawer.png
DATA  cd1abfa7fcd1ccdc3a70b8b0123f2729117b9eb21896f53576df1643f6d826fe  docs/evidence/coherent-shell/refined-installed/terminal.png
DATA  ccb7f23fc2cb8c7d09b73cb83a7cb094a85e9abfde64a4298dee41cb6b5c5461  docs/evidence/coherent-shell/themed-installed/deck.png
DATA  fc3d567e4527bb2e4b71e9b0460af75d02aed0c49d86c9275e92926bd50c5888  docs/evidence/coherent-shell/themed-installed/drawer.png
DATA d9b9127bc6471222aa8a6c8cc99dd257b240e9c1a0a22e4f0504f889506dadbf  docs/evidence/vglite-scene-board/context-lifetime/round-1/gpu/scene-first.png
DATA 8a535115024cf19364360ea89a99bc71746af6cc7384c724d0a1d2c636a10e2f  docs/evidence/vglite-scene-board/context-lifetime/round-1/gpu/scene-later.png
DATA d9b9127bc6471222aa8a6c8cc99dd257b240e9c1a0a22e4f0504f889506dadbf  docs/evidence/vglite-scene-board/context-lifetime/round-1/pixman/scene-first.png
DATA 33b91fb93eeb2e98a06437f817a8ac170550c88746991188827ee8bb33e3eed8  docs/evidence/vglite-scene-board/context-lifetime/round-1/pixman/scene-later.png
DATA 0c22854140c93aa879eccc553e7ea85f1ac869b0ffce62b0f51e427f2a29d63d  docs/evidence/vglite-scene-board/context-lifetime/round-2/gpu/scene-first.png
DATA 980450a82edfe5e1a218767be6329d55d4f118675a4e2dd5bb588ed24f95137b  docs/evidence/vglite-scene-board/context-lifetime/round-2/gpu/scene-later.png
DATA 0c22854140c93aa879eccc553e7ea85f1ac869b0ffce62b0f51e427f2a29d63d  docs/evidence/vglite-scene-board/context-lifetime/round-2/pixman/scene-first.png
DATA 77d40029a1007744b82a4e89446035a437a4253b8a507f20a634dc5c415c47fb  docs/evidence/vglite-scene-board/context-lifetime/round-2/pixman/scene-later.png
DATA 8845f9437717a5c103ec30a9905bb64f62d0b41d414a4e0fe8299624831cab2b  docs/evidence/vglite-scene-board/context-lifetime/round-3/gpu/scene-first.png
DATA 41c6cbda8d7f2c3bd02d5873ccac113e6fe965df2c653365c12c2b4fcbd3ea23  docs/evidence/vglite-scene-board/context-lifetime/round-3/gpu/scene-later.png
DATA f32b82f2538d2babc2eda97464487e191d8de1a5e23b7ea76a086661ce225284  docs/evidence/vglite-scene-board/context-lifetime/round-3/pixman/scene-first.png
DATA 328327f15e9fc51e3b0bc898d75af949ff5a47f0814178750e601f255ec8216d  docs/evidence/vglite-scene-board/context-lifetime/round-3/pixman/scene-later.png
DATA d2b360a3dc612952c203e35e2559a82af40a7c3b7979bf768a077d4cb1bf71ca  docs/evidence/card-composition-board/after-close.png
DATA e2133dce11201eab18e59a4686cbe1c44d3f3ceb1b9998cc525b081f0482a0fe  docs/evidence/card-composition-board/card-during-drag.png
DATA 688ce8b11f991fdb18f2f908f43c2bfb85382b7cbe6dc96e714574bad3ffdf9b  docs/evidence/card-composition-board/expanded-second.png
DATA eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8  docs/evidence/card-composition-board/restore/keyboard-visible.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/card-composition-board/restore/terminal.png
DATA 20afc0d92b0f7e131441401c2d0c675fe1c33ce642f7c53a66cb26631a0da362  docs/evidence/card-composition-board/two-live-cards.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/final-shell-image/after-render-failure.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/final-shell-image/help-header.png
DATA eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8  docs/evidence/final-shell-image/keyboard-visible.png
DATA ba91edae2fe3b89422797769edcbcccde5195eb7574cce4a556b7ab9970d3102  docs/evidence/card-composition-headless/cards.png
DATA 00c70a72742835f3cc0376bcfc33c81c2d491e759d5c76d29fb0e9ea2c185030  docs/evidence/coherent-shell/rust-icons-host.png

DATA e448f0761d241083e2d9f9a7dc9c3e3c16e4c89822a348a5fa188d12c7cde4d6  docs/evidence/work-card-media/desktop-card.png
DATA abb9463e46fdd7b2d622d6fd6274e1f087768b8f9d724c3255a21a1d3ab2cb1d  docs/evidence/work-card-media/mobile-dialog.png
DATA 2e56b5aeb46b748a6cbd192352d7c3a985fe705ffedb1a1fe38d6f6bacc0e7a3  docs/evidence/card-shell/headless/during-drag.png
DATA 38cb6ab82eeedb0154574a7f126380b3c1cf52e62f88bb0228db208a89f35ed3  docs/evidence/card-shell/headless/private.png
DATA cd0ff6f6b75552bf4f5a891395e36f12b6366ab844d15afcf4e7fabdb97077f8  docs/evidence/card-shell/headless/two-live.png
DATA 5975a8e3a946701df1ca30d1dd01e2946a7b42d15dab8ed88ce4350f071eb55f  docs/evidence/card-shell/headless/unavailable.png
DATA 0aa7c1d4c919b21ac233ce996df62a7ed9e7fa342a1dd18f71e212560acad6e9  docs/evidence/video-acceleration/360p-native.png
DATA 0de84cf54feadaaaeff344d62d5764700fdfcb02eadf54f2d71485e164d5341b  docs/evidence/video-acceleration/360p-physical.jpg
DATA 3eb27a069ff2f1b7bae9c991229a73086ddaccb8a00c12de2b8b9110e8cc49fa  docs/evidence/video-acceleration/360p-physical.mp4
DATA 2a633a028f8e10ea939c9c5b17994ce0a0cefb7f923604c28bdbe7fa9ee7b439  docs/evidence/big-buck-bunny/270p-native.png
DATA 92b33c778c720a23b87bae0da2d1b05a0a7e27f76134100020a1d833eb3fb29c  docs/evidence/big-buck-bunny/270p-physical-clip.mp4
DATA 7b18cca3cdb439ef572de0f46f48351f9ce4faf20aa56459893d654e987b4780  docs/evidence/big-buck-bunny/270p-physical-frame.jpg
DATA 7c8c6558a8bce911d9660d2afea92b64ce416d80f6340ea305ca7b1ce9558775  docs/evidence/network-video/mvx-patched-traces.tar.gz
DATA 1abe57ed5618a0e755e972c8cba51ed3df2dc3aedfa977a31ccc96c2e4c89903  docs/evidence/launcher-gestures/preflight-apps-page-2.png
DATA 27a6acc3f1428c79ae7345632052b46d41911ccde6f60c060e8bcd93648e445a  docs/evidence/launcher-gestures/preflight-overview.png
DATA bb3c48a24804823a0f4b81f5313adf0bafe64aeadfa8d58d0af4643d54a28600  docs/evidence/launcher-gestures/integrated-injected/overview.png
DATA eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8  docs/evidence/launcher-gestures/integrated-injected/keyboard-visible.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/launcher-gestures/integrated-injected/apps-before.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/launcher-gestures/integrated-injected/after-back.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/launcher-gestures/integrated-injected/after-20-each.png
DATA eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8  docs/evidence/launcher-gestures/integrated-injected/keyboard-gesture.png
DATA d40206f05d3b2f964da1f78b662c0176f67d2ab47d49ca3453f4cb5df5d694b7  docs/evidence/launcher-gestures/real-finger/gestures.mp4
DATA 215d6123da8bf7ba7feb6a1977c88323974a6b54e07629fb594f4d83f871ab02  docs/evidence/launcher-gestures/real-finger/window-selection.jpg
DATA 015319ae3a573239a20028df99a946834521bd36efb445d405ee038e2ce3e425  docs/evidence/network-video/installed-app/playing-camera.jpg
DATA a425be3bc53c533bd2e3ba89ae40e7398cdf2c03ac15f2621b26f4913cb7748f  docs/evidence/network-video/installed-app/playing-camera.mp4
DATA f744200109383fa83efa0f7828da34286818e7db670428b6c8661aace06131ca  docs/evidence/network-video/installed-app/controls-native.png
DATA a092de30d81389838e6ad49182382d68accce152b2408ba605d24c2e39a97ece  docs/evidence/network-video/installed-app/playing-native.png
DATA 9ee90f16fee33b2c87bdac94f7ba3e77efcccc8581b1b205508e806168086a4f  docs/evidence/network-video/installed-app/apps-entry.png
# class  sha256                                                            path
#
# --- this project's own tree ---------------------------------------------
E2   3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94  firmware/stage1/fn_u-boot-spl.bin
E2   c0fb8d95a983c33f3d0a1d7f18de721314878cb3322eaf62fbb1d2788d26b0c4  firmware/stage1/fn_ug_u-boot.bin
E1   cf108755a3cf3a8070a2f0ded84af672108e2301dfd58e5c2aa6a7555dbbd352  firmware/stage1/env.env
E1   023b5495c9450af553c24d8c518cf8f191c9ed8e5622e7a7405007172cb4fb10  firmware/stage1/fw_jump.bin
E1   d0279bc93038793906764d22dfea298d82a89999dd0b26b23d69cce98497e544  firmware/stage1/fw_jump_add_uboot_head.bin
IO   517aa534255e88c941882be40f5e5735349cd1e3b144b536155e51bdc6309c8b  embedded:fn_u-boot-spl.bin@0x1fc74+0x8000  ddr-pmu-imem
IO   1c0819e81446a8944a3ecf95304642ecec2071451d430e21925e5d7daea47313  embedded:fn_u-boot-spl.bin@0x1f5f4+0x67c   ddr-pmu-dmem
DATA 910743a6c9ace7d92dab5fcf0a5bfe2e3bcc986bea428a9f102d4185ece20206  assets/boot-splash.png
DATA e17961464d313d4799d8037381c5179101f982f60bd908a111e74f92c6b2cdcd  nix/qtquick-software-probe/tile.png
DATA ce89bec08e3a28f2a5eee150dcca1dc9d048c9421e31116904d0c6ee5f8081e9  docs/evidence/coherent-shell/rust-probe-board/mapped.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/coherent-shell/rust-probe-board/restored.png
DATA 450c318b8f9eff21bff89fe70c34b16101f0dbdb43b37a50fdc385b6d658ddf2  docs/evidence/coherent-shell/reveal-integrated-qemu/rust-deck.png
DATA c008c3e10bfcbfe18348dae4b72ee090ea986316f31681bddc5d8549c145e01a  docs/evidence/work-card-media/file-mobile.png
DATA 118acb1e9bcefa389a49b97e344c31d362d07d00f79b36db762b41d1a30d09f4  docs/evidence/work-card-media/gallery-desktop.png
DATA e8f491fb0e78cf07a7369b0743719a1c10bf809f8a63b67b58974a5a4636003d  docs/evidence/coherent-shell/first-integrated-preview/notification-shade.png
DATA 298f42631b45023fb26c0e4e4e486a4740615cc4d9ee1f8e2eb12b24a27c11ab  docs/evidence/coherent-shell/first-integrated-preview/app-drawer.png
DATA b81dbc7f9de727cc7a0c0acff138d5509dc911ceec46d69c2f1ae89a95eb11b2  docs/evidence/coherent-shell/reveal-integrated-qemu/rust-drawer-mid.png
DATA 381f5aaa192d9bce2582a6712199b499c311e6e98da7c0782a52e87e87ec7276  docs/evidence/coherent-shell/reveal-integrated-qemu/rust-drawer-open.png
DATA b50f6bd0107b1d2e3a0fe2722e95b4edf8362f41501b89e831adde901e87b37c  docs/evidence/coherent-shell/reveal-integrated-qemu/rust-drawer-reversed.png
DATA b51be35b7afe08f4794fb99870a0ca4a907b11aa1122f4f74bfde2dd1de06327  docs/evidence/coherent-shell/reveal-integrated-qemu/rust-shade-mid.png
DATA 30d05a39baba44a579c70f369bcb1140b822178c726a689003777cf159048b73  docs/evidence/coherent-shell/rust-drawer-interaction-qemu/deck.png
DATA 13fcd64a52e3fbc23c0ce7df2846c7da48bec1637d77c47bb876816f8517aab5  docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-dismissed.png
DATA 6d38dbebddb6015d7019ebce7360a2540664717838cf413ed490f7cd2828718f  docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-open.png
DATA bd3b2e1340887b3431f6536186aab5deb63d0d3d681ec130077cf486a4b1fd54  docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-scrolled.png
DATA 553d64fc7e19f8f3b783a3b862245d9f3155c8bc425762f9e013f1fc8afd6feb  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/app-restored.png
DATA 2efb9c643352a88a89a8387372cdedf2cf29cebac62a736976e571fdfe00fea3  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/app-shade.png
DATA c23edc5813c65d9e399719aac6ea29cb53c62e9bff02ce2acbe530005a941dc6  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/deck-restored.png
DATA 9f15515cc8abb69f4b67ab5164fe46367996d4b935cd002b18431c64e4597a99  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/shade-cancelled.png
DATA befdaf2fcf1e0e7b1be1acdfdcc043e73ea6c194ee21ceaa22fc628a3b2b8c81  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/shade-multitouch.png
DATA 1dbdad98f99abd866138ab1e98c11b835be610c37c2aeed1824105666f6630ad  docs/evidence/coherent-shell/rust-shade-dismiss-qemu/shade-open.png
DATA d66a40dc8b6c65138c7d967754d8f0823684dff5925e61b4c247be0826140aff  docs/evidence/coherent-shell/rust-service-surface-qemu/settings-confirm.png
DATA 291e10cae0bb67a7896650b20f14569cd510caddaa448cff9af2a3fe66af4651  docs/evidence/coherent-shell/rust-service-surface-qemu/settings-fake-power-denied.png
DATA c3042ea320cd424f589b8844ca738c48723ca7ea32c3b0427d3a2fc83754aee1  docs/evidence/coherent-shell/rust-service-surface-qemu/shade-action-error.png
DATA babc311f3246bcb5ba9acc391cc061362f983a8af941660c927f19d4e33542b2  docs/evidence/coherent-shell/rust-service-surface-qemu/shade-private-first.png
DATA 9db3bbd5425e546f6abfe2a35de98f433f34b617abdcaa6cdfbe520896f7a8b9  docs/evidence/coherent-shell/rust-service-surface-qemu/shade-private-second.png
DATA b18c75f8d63c6f7792eed767e54e8ad333600d02dc504c22d62412e298def220  docs/evidence/coherent-shell/direct-reveal-drag-qemu/deck.png
DATA 96b4a3a5a268d33a466c5f0c0479ed5f02960322e97a91e014c648b142ca1d22  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-100.png
DATA 8c4308e515d65e4551c8d58b73b285157fd31e608c1d6c5e6c28f9bffdb89baf  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-cancelled.png
DATA 939a69ae6e42cf6dda98375ce8cfbb0869f9f9a410ac140de976e77943268621  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-held.png
DATA 84239bc8fc2cf384f14e69e3218f75d786ff77f398f7ed5e05266de30bde8539  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-lateral.png
DATA 431343213a8735a1cd1bc3cf69f452b9f68ff5b1cdc4b4d5335526b31b524854  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-reversed.png
DATA edbd20a1a8f462d2cc5555330c23a5acbe0d20532886fe52d78d61ecff3ffbb1  docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-settled.png
DATA 882d9732d92c28047a2e57808737c0cac52414f5145755b07a925e214d478e1e  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-100.png
DATA 2f60e48539e07f8b8de02fd8716c6d73c9de7a04a87ba80ffb9fa1123b8c21a0  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-cancelled.png
DATA 1c613ec7ce7f9785c0dbc43a963534789aa3580059b0747265369cafdc609076  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-held.png
DATA 54300d5986b4ef86263222df1ce23aa666b39cf09bd1ab03b5e64d5b5fd1837b  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-lateral.png
DATA dcb9307591e0b3d692d2800ed80e7a3ae27ec05ad8abf9f89a76453261d0c837  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-reversed.png
DATA 1dbdad98f99abd866138ab1e98c11b835be610c37c2aeed1824105666f6630ad  docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-settled.png
DATA aec89c175df00b8a6729b83374cff768d0700eba120a4778f06e9a1dffe65326  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-coasting.png
DATA 57482fe9fd326bd5f6f7d4ab946b77488853cb9c46d138d62830e46170952a42  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-held.png
DATA fc4e4449694e4cca4bf113d5c2da0b5e64c6e8d401a9af865344d391efb4041b  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-settled.png
DATA dc82447aaf14a1acdd66a1ea9bf46a788cc062fbba810b22232b7a9f5787aed7  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-opposite-return.png
DATA 569eafcf56af3a813dffb08247134adba4679872d47b747b05c4f9ea4756e5df  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-held.png
DATA 9e525b27f3d16d6caa0a82f6b34f3e194320f89dfa9464ba16ae046768fbdd19  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-releasing.png
DATA 1b9a322aa851a165bfd79821852019f7c7f30ca2eedf0a7abb5050332ac56da5  docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-reversed.png
DATA 68a92ee6cb08da4c13ea717d1046d8cf1f94aaf86fb92c0ff46534ba8f6ad73f  docs/evidence/coherent-shell/two-axis-qemu/two-axis-held.png
DATA 8521494c8dd2e1abdbc64da3a8d52935d51307f9910604645d5d519d88a8499b  docs/evidence/coherent-shell/two-axis-qemu/two-axis-left.png
DATA 1ccaab283a509331ed392725eac48ee08ef6e8c8d94711e2a0fd0d25315ac9d0  docs/evidence/coherent-shell/two-axis-qemu/two-axis-private-neighbor.png
DATA be1a5afadef475a2d132489465eff5b288e2983a22ea4f0782f159807aba44a4  docs/evidence/coherent-shell/two-axis-qemu/two-axis-second-focused.png
DATA 294a90a5ceba6bb59f49aeffc22ba6e24b0c3c6824b052da48ca217918f501b3  docs/evidence/coherent-shell/two-axis-qemu/two-axis-start.png
DATA 441248f701999c8c186ef1500c865e57970928e65b86a98895b38a5d5b48808e  docs/evidence/coherent-shell/two-axis-qemu/two-axis-up.png
DATA 53d0d27b07ddda9408816436dc3ceaa0b2f84664b8b3b91f100165309cc733e0  docs/evidence/omarchy-themes/deck-appearance-qemu/before.png
DATA 3830cb9114a3aed6ad4234aad7485626108212b26da1f2588c14c8595d5d8959  docs/evidence/omarchy-themes/deck-appearance-qemu/restored.png
DATA fa5007d0bbbe7e2a592a0b372c3221aa7b4006cbd1fa4b46bcda1aaa24cee9cd  docs/evidence/omarchy-themes/deck-appearance-qemu/themed.png
DATA 01bd1a7535e53eebef58a0fcc087dfc9b305704984018be99583876c88657543  docs/evidence/omarchy-themes/paired-endpoints-qemu/app-after.png
DATA 5f6661ca7c2b0e81615c6f8d2ace3d50bcd4c56ee64d6a1f60d7ef85af975fc9  docs/evidence/omarchy-themes/paired-endpoints-qemu/restarted-deck.png
DATA 96cecf526f58f4ea7af374974c70640a80e484f3a20202e1c7454a26c796de1f  docs/evidence/omarchy-themes/paired-endpoints-qemu/restarted-drawer.png
DATA 085a00f2d55edf2e0073788f1fd302f41548e3ade7dd9a07640f020b53ea7971  docs/evidence/omarchy-themes/paired-endpoints-qemu/rollback-deck.png
DATA d5b3e47bf88596e75dc8ba1f22d456de2ea478e68df4443d53d0e0489ce41f13  docs/evidence/omarchy-themes/paired-endpoints-qemu/themed-deck.png
DATA d2b189f2421e5b2421b091ae8cbfb403e57e784a2b70f3853f8b26945ecf089e  docs/evidence/omarchy-themes/paired-endpoints-qemu/themed-drawer.png

DATA 5414b90fd68924d1bae90f78982c7897ac9b75c3ff64e173f9352dd5ff1fb236  docs/evidence/shell-features/startup-portrait/20260922T172430Z-portrait-image-startup.mp4
DATA 3fd760e13e69c0bb5c640e901d3b64cc059e20b546ae8b3bcf022bb86ed6b947  docs/evidence/shell-features/startup-portrait/demo.mp4
DATA 70ac27055e70e2add02b8460b8596b1c4597aacfad212e8f1793257606536cfa  docs/evidence/shell-features/startup-portrait/screen.png
DATA a21b31bc9f2083a07b064d6e7903e5cee8171c5b17f98d25fe13f715e5351556  docs/evidence/shell-features/monitor-integrated/20260922T172916Z-monitor-integrated.mp4
DATA da384bb99cc17340995486503e40266d5c5d3a5bbe62d8673953f7df9484634e  docs/evidence/shell-features/monitor-integrated/demo.mp4
DATA bbaedd2437c461121860b4371e3519ae4e9a9f60833baecd2eb1ffd9b9ef162c  docs/evidence/shell-features/monitor-integrated/native-source.tar.gz
DATA b0bfd387d777e37bba4eecdca7b1f64dde8687012bb6fb26ce8af027c6c549cc  docs/evidence/shell-features/monitor-integrated/native.mp4
DATA 2997bf72414d03c70b23381cf4ccc30be1bc75ca79663f23cb20a365e1410fe3  docs/evidence/shell-features/monitor-integrated/screen.png
DATA 72815940d742506f6b6a8b1889e90b982c8b9d7bcb9899ffa2b73c528557a3d2  docs/evidence/shell-frame-timing/20260922T171130Z-portrait-frame-load.jpg
DATA ac7b86aa20bcca4c38c44047a21471e3a80a2f2b11fe36d552fd4fcbb05b88c0  docs/evidence/shell-frame-timing/portrait-scroll-keyboard.png
DATA group:10-files  docs/evidence/panel-photos/*.{jpg,png}   photographs of the panel, cited as evidence
DATA 9458168554467e700d6e67616d4f1d94cb389439b81da030a163fde1cef8b222  docs/evidence/cage-rgb565-first-light.jpg
DATA e15ef2cfcdb22b20bb693b2a5615aee11d25dfb2ead4d4a4dc7ef7563b97228a  docs/evidence/keyboard-signal-probe.jpg
DATA cdc5411c38b201629049ca282753473bdf523abbd5ef875efcafb05c236c4fd6  docs/evidence/keyboard-signal-screenshot.png
DATA 7aa3cf4543591727c3aafc89eccfde4644830852856ac43458c34876ad83c7b0  docs/evidence/keyboard-user-touch-screenshot.png
DATA 09bb59aa5db08fdc0c354beaa89813e7f0b9a70d0c8536db8ed79a081e3068cb  docs/evidence/keyboard-user-touch.jpg
DATA 0e59c03446e3d660ef8c0517b69557a6cc3632d41ccb38952ec8ebd62026ea62  docs/evidence/neofetch-panel.jpg
DATA d5f7cecfa9233657cae3a4e1b990239ca49a5c8729c60d73d555055ece533e29  docs/evidence/shell-features/neofetch/20260922T160722Z-neofetch.mp4
DATA e7d8bc52830857448cab640d99f70e592f41c74121c997b7ba433386360695bb  docs/evidence/shell-features/neofetch/demo.mp4
DATA 2d6d2959a427df3becde53cb97dc9468aa583a4d075be8b85c0caaeefd6cd6a8  docs/evidence/shell-features/neofetch/screen.png
DATA 682084b0523df900014af2236ef97e011ff519cd947f17bd00eda567e80ab839  docs/evidence/sway-first-light.jpg
DATA 12b8c09a3cf8f296d6aab6446efe8c4ec18fb847c49495c3403a8d83ff4f14fb  docs/evidence/shell-features/keyboard-show-hide/20260922T162954Z-keyboard-show-hide.mp4
DATA 49241c2b0f8b35a2e15626d2fc063f24ee913140b019ae810e996abb5c330a1e  docs/evidence/shell-features/keyboard-show-hide/demo.mp4
DATA 2ba50fa32f79a61c0e7453de034b7e69415e15c25dd5217029b9e46976a20a16  docs/evidence/shell-features/keyboard-show-hide/hidden.png
DATA 5baa7df84c80eedd8d3c824b92751ebc649feb9870fed6497c7695430d8a69eb  docs/evidence/shell-features/keyboard-show-hide/native.mp4
DATA 7f70a0ef16cbd98d30a936ae981b6def7ba3fe2acaf1486550200f387897e53b  docs/evidence/shell-features/keyboard-show-hide/screen.png
DATA 093723defda27fd079fe76056c2cdea3d55c18e82c64062bd2f1f3777bd3a8d9  docs/evidence/shell-features/launch/20260922T163054Z-launch.mp4
DATA 1b10fe9dd8e5f36084c070e4bed9dcb22768d6692f42e352fe8d8cca2c681ff8  docs/evidence/shell-features/launch/demo.mp4
DATA 634bf41e6c599584e206de0426e8488fd6f4d320b3b3e9953e51a5f906fd107b  docs/evidence/shell-features/launch/menu.png
DATA 8448897bb280748cc3bfcc0f82e6d00eb96ac916a8555af9c17c61b60189687a  docs/evidence/shell-features/launch/native.mp4
DATA 53bd1c31185d136a39ec3e6b55b9437c29ab9d7b39156efcc665ea3602816102  docs/evidence/shell-features/launch/screen.png
DATA 64e15949d323c518248afe2bcf03b6d8077efde57e946e0bd7d77ea968a6d558  docs/evidence/shell-features/monitor-portrait/20260922T163926Z-monitor-portrait.mp4
DATA 6e5bda7007857f96003ee6aae70b70913b3e16aa57fc4b95ebf15fea87975e3b  docs/evidence/shell-features/monitor-portrait/demo.mp4
DATA 6af3645676bddc303115904c349caa5be3bbe60d7edd475e468843cab72fb233  docs/evidence/shell-features/monitor-portrait/native.mp4
DATA fafa2ca7fe21c846eeef7cc1f1d73e8c7fc7cfbcc75e2cf011a2f02d1d014969  docs/evidence/shell-features/monitor-portrait/screen.png
DATA fb8062d265cfd6bfc5379bf2ee28c2e1d293c9fe665f87c5fe6c78e010ab6cd6  docs/evidence/shell-features/native-source.tar.xz
DATA 0d4c3d0821713b63510b5b218e886dc538727e8db0651027c8411673223969ca  docs/evidence/shell-features/neofetch-clean/20260922T163842Z-neofetch-clean.mp4
DATA 45ff2bc95ec643e9be76b8911238b24ea8d918a52c0ab1aa0f1c8a8dcad25d19  docs/evidence/shell-features/neofetch-clean/demo.mp4
DATA 9e12f344648897d0b207157fa079f21ae8c7360c8eb1fe07a5d840e538274ac9  docs/evidence/shell-features/neofetch-clean/native.mp4
DATA ab59925933402f9a99d07a6f28303b9ede8a9ae5cf9e1cf790b4a912ca24e682  docs/evidence/shell-features/neofetch-clean/screen.png
DATA da040cec9c72f5923eb8c03f841ac2266ad4100b859375343af9f1745ae46a5d  docs/evidence/shell-features/neofetch-launch-failed/20260922T163706Z-neofetch-clean.mp4
DATA 7e87e273ed1436b64884850b0d1f6146d6b483fa9093e2a93d6fca41d2700947  docs/evidence/shell-features/neofetch-launch-failed/screen.png
DATA 63dee924435f0ac8ef13dfb9382f6319385ef2997920994c076633eabd294f75  docs/evidence/shell-features/reboot/20260922T164431Z-reboot.mp4
DATA d52617e484759bfadfce009f34b22a2123ae1c2661b948b1ae821948e32a5620  docs/evidence/shell-features/reboot/demo.mp4
DATA b514bc82d98dacb70c369c7a0869681e5cfa1acd1614fcbed9c9c3259908b1c6  docs/evidence/shell-features/reboot/screen.png
DATA 3593e96abf46d2c1736c7cbfb7f5a7496428c2b25d2c921ee3c606b284bd88b8  docs/evidence/shell-features/startup/20260922T162402Z-unattended-startup.mp4
DATA 3b9466f6baa8cd81d6ba09399e347abb03976cfdfed5f3663c671aac39e5a399  docs/evidence/shell-features/startup/demo.mp4
DATA 8f27ae3bea9c15282aeb3d8ce397dfba17371dea8d86706685f2c217b8063ed4  docs/evidence/shell-features/startup/screen.jpg
DATA ced1003cbd52c8021e6ba40eab24df07ea9ebc451ab7a31116ae90b55e596af7  docs/evidence/shell-features/switch/20260922T163200Z-switch.mp4
DATA 494a893b235776b204a4bbd371dcdbe05f7e4ba5250d650a9ab7f2dd1fa3cd29  docs/evidence/shell-features/switch/demo.mp4
DATA f348fd0e4bda895ff74387d7c6ce819556fa9449870deb17dd5df392b8986bee  docs/evidence/shell-features/switch/menu.png
DATA 1c698823d78ca8a9ac4b476a540f066284969a7b1795ad048e36fd78a65424cf  docs/evidence/shell-features/switch/native.mp4
DATA 099ec6b0c372e8c0c89d4c5503866cdf21723b7fb1f3864eba4705de2d1d684e  docs/evidence/shell-features/switch/next.png
DATA 2d160b8ee2f3e797104072e9e5d349a3a12b1f2a32d9c8e54b05d1bc5b219f9c  docs/evidence/shell-features/switch/screen.png
DATA 4e8fff0a21bef185d0f7fda8f822d92e3cd72d9e9244710fc92ac145f1017dff  docs/evidence/shell-features/switch/terminal.png
DATA 303ad0dfcdd9fd0a8321604cff8db6c7eb0bcfc16eb946be462817226d537364  docs/evidence/shell-features/system-controls/20260922T163523Z-system-controls.mp4
DATA 0ff33771611d487aa09e9f11d86f2f05351c062e7e5b3bf494242fd52a6b759b  docs/evidence/shell-features/system-controls/demo.mp4
DATA e768a4d9ad2a68d265ed917462fc0f2291c9e95497df4dbb3b5e705f1df5850a  docs/evidence/shell-features/system-controls/menu.png
DATA f05f37915bfa0c9d051d2facabe4eb2822f80b274cfe62f463e3e4add5c803fe  docs/evidence/shell-features/system-controls/native.mp4
DATA bc5fac85d0a8d7c810c949af9cb7fc8587164b42b66e3c40ce1cac868f91dbe7  docs/evidence/shell-features/system-controls/poweroff.png
DATA ae41014be70bf9cc38e931d1b59d0366d94267e2ab15d00e9f7fa9ad615924a2  docs/evidence/shell-features/system-controls/screen.png
DATA f0bb888a4d5f19e22a62af4e2bab07bf62040dcf627b891576e42aea8f1eea47  docs/evidence/shell-features/terminal/20260922T162858Z-terminal.mp4
DATA 2dcf150c931c9c47f82a1db35d95fb063fcaebde68ca21e39d8798edb78b57f8  docs/evidence/shell-features/terminal/demo.mp4
DATA 7f70a0ef16cbd98d30a936ae981b6def7ba3fe2acaf1486550200f387897e53b  docs/evidence/shell-features/terminal/keyboard.png
DATA e35b37ff6f6c9cb539232e019e7036cb304c6f0c544b42743d990cedf32226d5  docs/evidence/shell-features/terminal/native.mp4
DATA 2ba50fa32f79a61c0e7453de034b7e69415e15c25dd5217029b9e46976a20a16  docs/evidence/shell-features/terminal/screen.png
DATA f6bd888aa7e85118d4c6f9e6ff5a787e626c44d4baf9fb1d7fa571475ec4edde  docs/evidence/shell-features/terminal-recovery/20260922T163353Z-terminal-recovery.mp4
DATA 1499eca1d75bb07a507e53b221eea5520a33b60ae10f2eb4ad4be7588fcb2992  docs/evidence/shell-features/terminal-recovery/closed.png
DATA 696908522be22f2e0ffd7efc5884a18e752de06897b84e7e2416697b646b86dc  docs/evidence/shell-features/terminal-recovery/demo.mp4
DATA 039657d825f133a2738413aaf3ed298928824cde0eb8e8ff076c514bae6749ce  docs/evidence/shell-features/terminal-recovery/menu.png
DATA e0af206407cdf44adec544a7ce9b83522d15cecbba09b45d38bf5532d23d5f49  docs/evidence/shell-features/terminal-recovery/native.mp4
DATA e68de7b14657587fa659442091807d08f30c4b3eb3fdf72c79446c169b6c7154  docs/evidence/shell-features/terminal-recovery/screen.png
DATA group:1-file    site/src/assets/*.png                    the board photograph on the spec site
#
# --- what the stage-1 nix files fetch by hash --------------------------------
# nix/uboot-k230.nix, nix/opensbi-k230.nix, nix/k230-sdk-src.nix. All three
# are text; the SDK fetch is sparse and was checked file by file (287 files,
# 287 text/*).
SRC  sha256-ULRIKlBbwoG6hHDDmaPCbhReKbI1ALw1xQ3r1/pGvfg=  src:u-boot-2022.10.tar.bz2                (50b4482a505bc281ba8470c399a3c26e145e29b23500bc35c50debd7fa46bdf8)
SRC  sha256-T8ZeAzjM9aeTXitjE7s+m+jjGGtDo2jK1qO5EuKiVLU=  src:riscv-software-src/opensbi@v1.4
SRC  sha256-P3XkeyJPkpe/h0oHAHCiz8a0VXofw1zsQ3YSa6UcG8w=  src:kendryte/k230_linux_sdk@1104236,sparse
#
# --- not files -----------------------------------------------------------
IO   -  (silicon) K230 BootROM
E2   md5:8cefc7e94f760eaecc3620ffb238bf4a  Xuantie-900-gcc-linux-6.6.0-glibc-x86_64-V3.0.2-20250410.tar.gz
IO   28680932ac879d8591fbaaaab7b8c1ee2d305c2a82471fb2f38c449316cfb91f  dl:nncase_k230_v2.11.0_runtime_linux.tgz
IO   525e4611b587afb1ab406548ddc6a5e1add3e5fa74ff2829da9441d4a62f3075  dl:nncaseruntime_k230-2.11.0-py3-none-linux_riscv64.whl
#
# --- the Linux SDK checkout, (sdk) = .build/k230_linux_sdk/ ----------------
E1   c6d029a05f2d3038fd02f9b18716b595f4e8beeebca33f3598328fbde99bf11e  (sdk)tools/k230_priv_gzip
NP   c11b83cfb92b9b01cdfb7150c75674c69563add2c8c1e71df1dc741694aae5a4  (sdk)buildroot-overlay/board/canaan/k230-soc/rootfs_overlay/etc/firmware/fw_bcm43438a1.bin
NP   6a35357449419dd493b201487f1a8467298dce0b990ad061bd00962a039c0b88  (sdk)buildroot-overlay/board/canaan/k230-soc/rootfs_overlay/boot/nuttx-7000000-uart2.bin
NP   91f53b9af6bacf9f91bb3995727cb4f9712810baaffbb2f230ff0ce87ab4464e  (sdk)buildroot-overlay/package/ai2d_kpu/test.kmodel
NP   56d35ded2a717fafcc1a357fd6e634531fa1693e59c77707140d8c6e1693eae9  (sdk)buildroot-overlay/package/face_detect/utils/face_detection_320.kmodel
NP   bb6c1142da99f017861d6d5ffaf956eb2b4a29cc393a6a7bc5bedad392499e15  (sdk)buildroot-overlay/package/yolo/utils/yolo11n.kmodel
NP   11c6f0aa707c63d351fb54fa24be3df23ae579590cd448921ffa3614a6a05190  (sdk)buildroot-overlay/package/yolo/utils/yolo26n.kmodel
NP   91b6c3e9bc2fc5d0bf5258e1217b6d8a81b4330521922165db255fe98795901c  (sdk)buildroot-overlay/package/yolo/utils/yolov5n.kmodel
NP   0b4bcdd3eef7ad05d827127ec630d2354659f6db1b0c627ecb4af32cb2004a09  (sdk)buildroot-overlay/package/yolo/utils/yolov8n.kmodel
NP   group:90-files   (sdk)buildroot-overlay/package/aic8800{,_sdio/src}/fw/**            8.8 MB: 103 files, of which 13 are text configuration
NP   group:7-files    (sdk)buildroot-overlay/package/k230_assistant/dist/lib/*.a
NP   group:1-file     (sdk)buildroot-overlay/package/opencv4/3rdparty/csi-cv/libcsi_cv_c908v.a
NP   group:3-files    (sdk)buildroot-overlay/package/ai2d_kpu/{input,ai2d_input,result}.bin
DATA group:2536-files   (sdk)buildroot-overlay/package/k230_assistant/libpeer/**             test corpora and certificates of libsrtp, mbedtls and usrsctp
DATA group:5-files   (sdk)buildroot-overlay/package/{face_detect,usage_ai2d,yolo,helloworld_cmake}/**/*.jpg   sample inputs
DATA group:1-file    (sdk)buildroot-overlay/package/audio_rec_play/audio.pcm
DATA group:1-file    (sdk)buildroot-overlay/package/cloudplat_deploy_code_linux/utils/SourceHanSansSC-Normal-Min.ttf
DATA group:2-files   (sdk)buildroot-overlay/package/webrtc/**/__pycache__/*.pyc
DATA group:1-file   (sdk)buildroot-overlay/package/lvgl/*/*.patch                       patches carrying binary hunks
DATA group:2-files   (sdk)buildroot-overlay/board/canaan/k230-soc/logo/*                 the U-Boot splash, png and raw yuv
DATA group:2-files   (sdk)docs/pic/*.png
#
# --- the LilyGO RT-Smart clone, (lilygo) = repo/canmv_k230/ ----------------
IO   e776d472979e32d761fd22a6c1f69e1bdee6aa32663169e684900e61eb08dd43  (lilygo)src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/extdrv/realtek/wlan_lib/libwlan_v1_1.a
IO   5f6baf7c785916beb7e18bda2535585cabaa62315dd8446f256d651900c06564  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libnncase.rt_modules.k230.a
IO   f6674a664be8133e368ab0f08df3e42d351e1f50811fdbddb6cf195cab6c0264  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libNncase.Runtime.Native.a
IO   1ac694e7197944e7217e21b50acfa2a8b14956355cf28e2f887d16d2a608fb01  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libfunctional_k230.a
IO   88c690d309fa5bc04b53ad909b450d97a9b9ebe887ee634891d8e4e44845118e  (lilygo)src/rtsmart/libs/nncase/riscv64/rvvlib/librvv.a
NP   6e5eac63398ecf18dd8327585232c2245d0087a699b6a964291b35660f8a94f7  (lilygo)src/rtsmart/rtsmart/tools/udb-tools/linux/udb
E1   c6d029a05f2d3038fd02f9b18716b595f4e8beeebca33f3598328fbde99bf11e  (lilygo)tools/k230_priv_gzip
E1   c6d029a05f2d3038fd02f9b18716b595f4e8beeebca33f3598328fbde99bf11e  (lilygo)src/uboot/uboot/tools/k230_priv_gzip
IO   group:14-files   (lilygo)src/rtsmart/mpp/kernel/lib/*.a                              6.6 MB
IO   group:39-files   (lilygo)src/rtsmart/mpp/userapps/lib/*.a                             18 MB
E1   group:15-files   (lilygo)src/rtsmart/libs/opencv/lib/*.a
IO   group:1-file     (lilygo)src/rtsmart/libs/opencv/lib/opencv4/3rdparty/libcsi_cv.a    T-Head CSI-CV, as B7
E1   group:9-files    (lilygo)src/rtsmart/libs/opencv/lib/opencv4/3rdparty/*.a            ade, jpeg-turbo, openjp2, png, protobuf, tiff, webp, quirc, zlib: upstream open source
NP   group:64-files    (lilygo)src/rtsmart/libs/kmodel/**/*.{kmodel,model}
NP   group:5-files    (lilygo)src/rtsmart/libs/nncase/examples/**/*.{tflite,onnx,bin}    example models and their inputs
DATA group:345-files   (lilygo)src/rtsmart/libs/**                                          sample images, test vectors, audio
IO   group:2-files    (lilygo)src/rtsmart/rtsmart/userapps/sdk/**/*.so                    the prebuilt RT-Smart userspace runtime: libcxx, librtthread
DATA group:51-files   (lilygo)src/rtsmart/rtsmart/**                                       images, documents, an archived doxygen tree
NP   group:11-files    (lilygo)src/rtsmart/mpp/userapps/sample/fastboot_app/build/**       a CMake build directory the vendor committed: .obj, a.out, an .elf
NP   group:2-files    (lilygo)src/rtsmart/mpp/userapps/src/sensor/dewarp/*.bin            dewarp tables for an IMX335 that is not on this board
DATA group:47-files   (lilygo)src/rtsmart/mpp/**                                           images, fonts, vim swap files
NP   group:19-files    (lilygo)src/canmv/resources/examples/**/*.{bin,kmodel}
DATA group:20-files   (lilygo)src/canmv/resources/**                                       sample images, audio, fonts
NP   group:1-file     (lilygo)src/canmv/micropython/ports/cc3200/bootmgr/relocator/relocator.bin   upstream MicroPython's CC3200 port
DATA group:56-files   (lilygo)src/canmv/micropython/**                                     upstream MicroPython test data, certificates, images
DATA group:161-files   (lilygo)src/canmv/port/**                                            UI assets: images, fonts
NP   group:1-file     (lilygo)src/opensbi/opensbi/hw.dtb
DATA group:38-files   (lilygo)src/uboot/uboot/**                                           upstream U-Boot's logos, fonts, test data
DATA group:1-file    (lilygo)tools/genimage/test/qemu.qcow.gz
IO   group:2-files    repo/firmware/CanMV-K230-V3P0_rtsmart_release{V1.2,V1.3}.zip        the shipped images; evidence, not a dependency
DATA group:16-files   repo/{Structural_Design,datasheet,schematic,image}/**                LilyGO's mechanical, datasheet and schematic documents
DATA 56c6a25b7d91a921199034d0f1005f068f103dc3f6dfe31638c72bad24e5230c  docs/evidence/shell-features/neofetch-cpu/20260922T185501Z-neofetch-cpu.mp4
DATA 2f25602ad853140dd9efa618c334d7d01cc2c2e48f02c91acba78102fd0bd769  docs/evidence/shell-features/neofetch-cpu/first-launch-path-error.png
DATA d7fdf5e05bef42cb01a6c407d386a94064c27769d47dd039f1c18ce01beea4cd  docs/evidence/shell-features/neofetch-cpu/native.png
DATA e22deb8c67b22fad47334f6b98803869fdc2f419202ed6b49075a3a1e3f52bae  docs/evidence/shell-features/portrait-launcher/20260922T185608Z-portrait-launcher.mp4
DATA bcc465eda496c31f6f384f2a20942f683c3a09899a22d4051c189b0ef9a80ed8  docs/evidence/shell-features/portrait-launcher/20260922T190646Z-portrait-launcher-final.mp4
DATA 3136f7257fb9851ede40444d080a9e1d2774a7c5874c73051f02d635e0cee388  docs/evidence/shell-features/portrait-launcher/drag-cancelled.png
DATA 871ddd0190226d7d901058bc047b1a5969e6e7c62ee982f95aea7aebc2d3460e  docs/evidence/shell-features/portrait-launcher/final-drag-cancelled.png
DATA 6b0b14f0350f98d11afdcaa49c810bb8ea7adf221213f0d54472a9a63a180bef  docs/evidence/shell-features/portrait-launcher/final-keyboard.png
DATA 871ddd0190226d7d901058bc047b1a5969e6e7c62ee982f95aea7aebc2d3460e  docs/evidence/shell-features/portrait-launcher/final-menu.png
DATA db23b8c873238bdb79f88c2c4f4e462acf1c765940fb00a5f2e7f177575f9855  docs/evidence/shell-features/portrait-launcher/final-monitor.png
DATA 0ca8ad93f91f38e7e2f46d84777b8a790e8010277a6d4045318ef38a4b2deee6  docs/evidence/shell-features/portrait-launcher/final-new-terminal.png
DATA 3e92020c1c0073cbd86560ef46bcb0f914e2aa931b7be65f0d6028015de8cf6e  docs/evidence/shell-features/portrait-launcher/first-layout-extra-margin.png
DATA a3dd9800b1caeb2e4d7c0d6f0d6ad52285f1889cae25952797ef54c978281e4c  docs/evidence/shell-features/portrait-launcher/keyboard.png
DATA 3136f7257fb9851ede40444d080a9e1d2774a7c5874c73051f02d635e0cee388  docs/evidence/shell-features/portrait-launcher/menu.png
DATA 9bb466599777d7975742e274a33d7f0d7fafb47144e17d85f874acf8b10ad143  docs/evidence/shell-features/portrait-launcher/monitor.png
DATA 2ac85f505b954a014e72026e4d01e571f9cb66c65840b233a958686204f28ea3  docs/evidence/shell-features/portrait-launcher/new-terminal.png
DATA 3d1a9b8cab377b20a59de1214907eb1b779064520b4daa352a7fab6d68609d31  docs/evidence/splash-trial/20260922T183200Z-uboot-splash-first-trial.mp4
DATA 31cc52a11767d7f4b1d114ac104fc1aa906c9b756aca4523da8f4c9e426424ab  docs/evidence/splash-trial/20260922T183316Z-splash-to-linux-first-trial.mp4
DATA 5128fb0bd80b0f0c598c06777cce19ff6b108bedc9d211b5270bfe2b65028a9c  docs/evidence/splash-trial/20260922T183432Z-shell-after-splash.jpg
DATA f947d3631ffeee8b0a9d63e83126a0ba54b1095ee04b3455205407b75aea5bb9  docs/evidence/splash-trial/20260922T184003Z-shell-without-logo.jpg
DATA 70ac27055e70e2add02b8460b8596b1c4597aacfad212e8f1793257606536cfa  docs/evidence/splash-trial/linux-native.png
DATA 403ee78cf4d3f516a2550ce4c73784587c709ce1956a41278882beefe5af60cf  docs/evidence/splash-trial/splash-to-linux-rotated.mp4
DATA 264f0169cef918095b431bc1f6dbabfafdbace2041248bbb16ea24fbb2f657c4  docs/evidence/splash-trial/timeline-linux.jpg
DATA 2c3e28403e9fa01f82e431bd198762b8481f26a50b35e5ef324ae1503119ddb4  docs/evidence/splash-trial/timeline-uboot.jpg
DATA eda0693650af79208e1f170b0e7c78ba8b939df22f82543a12645e28e4f756e5  docs/evidence/splash-trial/uboot-held-25s.jpg
DATA 7fb0582fe6d94d7252c4d71cd1243132c516da43b617bb5420a3d09fc0be3216  docs/evidence/splash-trial/uboot-splash-held-rotated.mp4
DATA 4cfc9d5278c031360775cb51e717d3e83941214314d401848c852081c2429673  docs/evidence/shell-features/desktop-launcher/20260922T192343Z-desktop-launcher.mp4
DATA 002d71ec94c44a4d6d9968ad8be4ff71341f7067c839f426438e6873a4cbfaf2  docs/evidence/shell-features/desktop-launcher/added.png
DATA 9927be9097bab6bf8a316cc9ec512f45ce8fe9e061f33449c39c0de1278cc648  docs/evidence/shell-features/desktop-launcher/apps.png
DATA d6f1f7f7f6ddf724b759cb9f1efb5e722baa8b93e9e328caf947e4bc94625052  docs/evidence/shell-features/desktop-launcher/error.png
DATA 9927be9097bab6bf8a316cc9ec512f45ce8fe9e061f33449c39c0de1278cc648  docs/evidence/shell-features/desktop-launcher/final.png
DATA 9927be9097bab6bf8a316cc9ec512f45ce8fe9e061f33449c39c0de1278cc648  docs/evidence/shell-features/desktop-launcher/first-page.png
DATA b9ad5f630b399f5e2aaec8399ed74cbcf91d56f9ee1346fe8a50a4f58f32ccba  docs/evidence/shell-features/desktop-launcher/htop.png
DATA 2915cf45af55f550316009ac4e433813ae3bf349da646f6780dff159f3210b43  docs/evidence/shell-features/desktop-launcher/keyboard-page-two.png
DATA 755c39d0a82d53456d604af8d84133304b009e72aa3d6a66bd12a6dd5d9d5a12  docs/evidence/shell-features/desktop-launcher/keyboard.png
DATA da27b7a03b4e3351f3be052b5b5284ce10064371e04eebf3f6cb663283884374  docs/evidence/shell-features/desktop-launcher/launched.png
DATA 9927be9097bab6bf8a316cc9ec512f45ce8fe9e061f33449c39c0de1278cc648  docs/evidence/shell-features/desktop-launcher/removed.png
DATA 570881146f0b409a3b82504cacf91d6a4d98afb87d324761b2ab4ac10fefcaef  docs/evidence/shell-features/desktop-launcher/second-page.png
DATA 482180f5abcd6d4bc47da78fc7e9b05db98c3fbf972e02926bad22caae183f91  docs/evidence/splash-handoff/20260922T200502Z-normal-shell-recovered.jpg
DATA 4a483866071a8bf78916e2deda97343d3ff334c1b27e2534ce357ca982621206  docs/evidence/splash-handoff/20260922T195817Z-splash-kernel-preservation.mp4
DATA 5eb6bcbdea3c6813db176afdf220523cf727e0cf9b9ddec7ea874a524197ef7b  docs/evidence/splash-handoff/20260922T200130Z-splash-to-shell.mp4
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-handoff/first-shell-native.png
DATA 623b94b83b0ed1993a6597f5ae8b5cf35396f4ac22759de4a9262fefe2cd99e8  docs/evidence/splash-handoff/first-shell-physical.png
DATA 9e161136c33236b08ffad17159db74b1ef0523b06f79ed6a1f2f987db44db228  docs/evidence/splash-handoff/preserved-at-linux-prompt.png
DATA cd0c1a4f6341032bb6ec4a2fe9511c4a2589c9f88f7dfd8e7106cdc6905e4391  docs/evidence/shell-features/desktop-launcher/image-htop.png
DATA 570881146f0b409a3b82504cacf91d6a4d98afb87d324761b2ab4ac10fefcaef  docs/evidence/shell-features/desktop-launcher/image-entries.png
DATA 9927be9097bab6bf8a316cc9ec512f45ce8fe9e061f33449c39c0de1278cc648  docs/evidence/shell-features/desktop-launcher/image-apps.png
DATA 1e2c1e90e7c2fe2bc85366ea926e1e7773744bd5d4be613ba5d3e16714009c65  docs/evidence/shell-features/desktop-launcher/20260922T195137Z-desktop-image-launcher.mp4
DATA 45ca6eeb078eb2ec7ab66990fa23060a5510cef35d20b13f9a16c8a72a304659  docs/evidence/shell-features/desktop-launcher/20260922T193941Z-desktop-image-boot.mp4
DATA 7ea86c8411dbfb252ab761567291ceb1256772964fa75b71c1662a59c108406f  docs/evidence/shell-features/declarative-defaults/20260922T203440Z-plain-neofetch.mp4
DATA bc760c98a6f6f0333bd42a56c623b218b803bcebe0407db170187215d5ff0ac2  docs/evidence/shell-features/declarative-defaults/20260922T203502Z-plain-htop.mp4
DATA 444ddf0f49d5bf7b0280f35543c8c84cf0bdb9bad133b8603ed237fc3d8c5723  docs/evidence/shell-features/declarative-defaults/neofetch-layout-trial.png
DATA 12952974027f08df9207bda91573473558c634c2b1f0ed1e723b2b12b529c101  docs/evidence/shell-features/declarative-defaults/plain-htop-physical.jpg
DATA 1c2d1699ac6fa4bcf01587b352eb1cae6f133134ac8408c211e18a9370c927e4  docs/evidence/shell-features/declarative-defaults/plain-htop.png
DATA def0e4061cae1ca35d53d65d11fd06afe6e1b68062e3a0aa6b3de45ccf6de576  docs/evidence/shell-features/declarative-defaults/plain-neofetch-physical.jpg
DATA 898b022c0097eaaab30a6b522758abb40451aa26858dc98877d07e3be7a8081a  docs/evidence/shell-features/declarative-defaults/plain-neofetch.png
DATA 1001b534fc142f12b1d79ca1eaa58631a2a8a7bb60154d57681f7595d90e0368  docs/evidence/shell-features/declarative-final/20260922T204210Z-declarative-final-startup.mp4
DATA 793193d7ea51c310f93d2a6066bcd0a1a1371c5860518a31e23d4cfba74cf47e  docs/evidence/shell-features/declarative-final/20260922T204419Z-plain-neofetch.mp4
DATA 59ad78cbf928009a34861c864dcd61d6098c7c5a87aadaba9356f45859eacda1  docs/evidence/shell-features/declarative-final/20260922T204441Z-plain-htop.mp4
DATA 03a8b4015fe2878ae661d40baa52226245fe4539580f4765f48241aab756bc3d  docs/evidence/shell-features/declarative-final/plain-htop-physical.jpg
DATA e8b36be194f16abf621ea67fd633e2919fb21be08718849ed549780d9a118e2c  docs/evidence/shell-features/declarative-final/plain-htop.png
DATA ecb6ea5d43be2ff34ed4420f4a499bad6c3f626d43687b24541e2fe39661d04b  docs/evidence/shell-features/declarative-final/plain-neofetch-physical.jpg
DATA 06f0648371ab08b2b2ec6b7b903c9d8d22c3ad33626baee09f678317feb4e35a  docs/evidence/shell-features/declarative-final/plain-neofetch.png
DATA fe941c83dd2d5e36ecc13b376f605aecad623279d46b5d6cf448d7f25c162845  docs/evidence/shell-features/declarative-final/startup-physical.jpg
DATA 8ede6ec14095a5fbd7b51ce02723859cfcac1c0cf15c1891acccc6ff4ce6050d  docs/evidence/splash-phases/20260922T205934Z-logo-to-drm-owner.mp4
DATA 615edc721c0a645db588bb43a7d4ffca3579796db0815f2df81d4902bf7e807a  docs/evidence/splash-phases/20260922T210027Z-drm-owner-to-sway.mp4
DATA c261663a7ebd59e7e842f93c3e91fd79d5378721a58b86b6d66cbe9cd92094eb  docs/evidence/splash-phases/20260922T210255Z-retained-logo-owner-sway-repeat.mp4
DATA abc592b6938179374ec8b37dc943a615d3dc94bca5c6b98eb2e289a9cdcadff0  docs/evidence/splash-phases/20260922T210603Z-phase-normal-recovery.jpg
DATA f77eaccedeae13f14bd13e14d8f52b6c53a66fca9d3458276ec0b0edfd9ab54d  docs/evidence/splash-phases/repeat-owner.jpg
DATA ada6806d5ef6a7e3fcedd06d5cd8fce11d02a971ee51cd301deeb44137e3c65a  docs/evidence/splash-phases/repeat-retained-logo.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-phases/repeat-sway-native.png
DATA c5b6365d9ed306a960794e02995905cf18b5c418a8a70115512e81a6a7a53a59  docs/evidence/splash-phases/repeat-sway.jpg
DATA 48b6ef6dc7e59962f1b4d004958f28cdc8c8d0f51354169f391b3b626b761dd8  docs/evidence/splash-phases/sway-first-physical.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-phases/sway-native.png
DATA c9ef74213899144262cb22b4575ca988456d216460d051b6bc1897e0cf9e22b8  docs/evidence/splash-preserve-trial/20260922T214204Z-preserve-image-automatic-boot.mp4
DATA 817757902d37a7dd7ae30adc9c0eed869e8916ec39f1e6bdcbe8eb90a3fbea58  docs/evidence/splash-preserve-trial/20260922T214458Z-preserve-automatic-repeat-1.mp4
DATA ce1bac8c208fc1a91449e232ba71fc58a460eb0086450aefee6bf596f44d3c5a  docs/evidence/splash-preserve-trial/20260922T214638Z-preserve-automatic-repeat-2.mp4
DATA 895042cb38cec7e2e8bd6ed5b4570752120e4fe48453940cef2041d8144dd11a  docs/evidence/splash-preserve-trial/20260922T214914Z-preserve-keyboard-pageflips.mp4
DATA 3c396c1d8dc1a0201cc5565d5cc669f1df472ca1112620c52a7d006533b739bb  docs/evidence/splash-preserve-trial/20260922T215021Z-preserve-kernel-no-logo-fallback.mp4
DATA 60862df429822d6913fa6e7534fe98a2ce0a2dcd631db2479371cfecf8b4a025  docs/evidence/splash-preserve-trial/20260922T215603Z-preserve-colors-pageflips.mp4
DATA 19d68e46eb59089553afe7b4a98f842fdcfa4e64e2d48502338dc52d23873b54  docs/evidence/splash-preserve-trial/20260922T215737Z-preserve-keyboard-and-dpms.mp4
DATA 12e466f6df6954051f225c15f7b91e46bba8efb616cac3257ecde6ec350554c5  docs/evidence/splash-preserve-trial/20260922T220022Z-preserve-keyboard-explicit.mp4
DATA 75a162c4727b2360d867bdf016943d702d4c3ab7182465913cabc29d9c140795  docs/evidence/splash-preserve-trial/20260922T220155Z-preserve-full-height-rows.mp4
DATA 8d9371c61b9f84e2d8450f43925a9df29bd611562d2c538a7c7e6dab6d78209b  docs/evidence/splash-preserve-trial/20260922T220341Z-keyboard-contrast-diagnostic.mp4
DATA 31618a04a377883eb57013eee541b1e47faf995711788e4c11cb55d1a319a4a9  docs/evidence/splash-preserve-trial/20260922T220505Z-keyboard-camera-focus.mp4
DATA e4e8d272c81e0780cc393f831952f127546355b48125bfd5f89ad921aec53704  docs/evidence/splash-preserve-trial/colors-native.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-preserve-trial/controls-after-dpms-native.png
DATA 51aaeb480cc87621bb997d7afbb961d949510dcf09885ff2f11b795293c67704  docs/evidence/splash-preserve-trial/controls-after-dpms-physical.jpg
DATA fc9e766b661bff2840f225dc401526c1edf0c4436d83b3bd4ef40b3266ad6816  docs/evidence/splash-preserve-trial/keyboard-contrast-native.png
DATA d65287480b85f3ab3130d6796587fb5b4cc7fdbfe4beb27278441af8cbc254a1  docs/evidence/splash-preserve-trial/keyboard-contrast-physical.jpg
DATA cb6db86340520a8a1ec7bf6efa76bc40ce6bca085080982a9237fe6858ecc70e  docs/evidence/splash-preserve-trial/keyboard-explicit-native.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-preserve-trial/keyboard-hidden-native.png
DATA 8cf4c3042a911519efc9d5e9fe7f852899c71c7b1d382faed22509c2f77cc179  docs/evidence/splash-preserve-trial/keyboard-physical.jpg
DATA cb6db86340520a8a1ec7bf6efa76bc40ce6bca085080982a9237fe6858ecc70e  docs/evidence/splash-preserve-trial/keyboard-shown-native.png
DATA 6f5546bfaa97346253abf25384e56a5da6e60d06be13a609ba11b5510ab6add8  docs/evidence/splash-preserve-trial/no-logo-physical.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-preserve-trial/repeat-1-native.png
DATA c3dd8073bdbaae308ac0bcb2c5861c91ef15edbaa06e674e10bad624783e8603  docs/evidence/splash-preserve-trial/repeat-1-physical.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-preserve-trial/repeat-2-native.png
DATA 883e607182d6726108242633702487bd4c6893431d046ffe378577213e37b245  docs/evidence/splash-preserve-trial/repeat-2-physical.jpg
DATA 1a888057276d30433c81d4a7866ddf19e2c2640737ff4a46c11f9f114603fabd  docs/evidence/splash-preserve-trial/rows-native.png
DATA 356f7a499f10fcd9b7a488bcac72e27e1136e5cf57c783306c1e73c1df2df5d4  docs/evidence/splash-preserve-trial/rows-physical.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-preserve-trial/shell-native.png
DATA 4a6e83eadde865c50360841244297b32a58e8ec7f96a2aea08026645edf5d68f  docs/evidence/splash-preserve-trial/shell-physical.jpg
DATA a675bf43671b9c099e6fe33c436d0f955c8d95a729f414ace8d75dc1d5b2dafd  docs/evidence/splash-initial-scene-trial/20260922T221824Z-initial-scene-automatic-boot.mp4
DATA cc1d078bdab03677cd5539ef41e6a08c2e8b8afe966c83d7fbfc9fa5a61b2f68  docs/evidence/splash-initial-scene-trial/20260922T222253Z-initial-scene-invalid-assets.mp4
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-trial/invalid-missing-native.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-trial/invalid-size-native.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-trial/shell-native.png
DATA 4423e99ff3d309711ac9a8653d57b7c0ad8d49e67da1da494c6c0b5cc03259fd  docs/evidence/splash-initial-scene-trial/shell-physical.jpg
DATA c2d6856150e7ffab2d38ad8766689ec4f2459c75c50b99b01f08c14b0201f8ef  docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4
DATA b9831514a542c77ac820a2e2fd4a611e817b50e7e3120e21cfeacf7416827420  docs/evidence/splash-initial-scene-ready/20260922T223311Z-initial-scene-ready-controls.mp4
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-ready/after-dpms-native.png
DATA c0153647eb895d46e5a220986d181389d917fe1e6c808246a44dfd5fe46982b7  docs/evidence/splash-initial-scene-ready/controls-recovery-38s.png
DATA cb6db86340520a8a1ec7bf6efa76bc40ce6bca085080982a9237fe6858ecc70e  docs/evidence/splash-initial-scene-ready/keyboard-native.png
DATA d093fcf3768834ef40205f558e17832bf22d0404de0451b5430239377ed8690d  docs/evidence/splash-initial-scene-ready/panel-ready-shell.png
DATA 15d4fdc1a82bae8c09d97218ba0ff9484480e969dd65d757e648342b5e8804a6  docs/evidence/splash-initial-scene-ready/panel-ready-transition.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-ready/shell-native.png
DATA 94c8f2c8a1b3fea2a066cadf6d647149942de2d35c4f4255edfdba951af75f29  docs/evidence/splash-uboot-motion/20260922T224020Z-uboot-motion-target.mp4
DATA 844b0eb59f684b7710b8c9296df5e30cecd5ffdc6f4b897f5316940af75fe73e  docs/evidence/splash-uboot-motion/focus-0.png
DATA 11bd164ee6ce2ffce913aa619470bc98553fbf1183428f21b14e7e946abd9c08  docs/evidence/splash-uboot-motion/focus-30.png
DATA 457227104d3add298806950e778d396b060feb7200fe971fc462656e81a8b614  docs/evidence/splash-uboot-motion/focus-50.png
DATA 3a7e1a570714cf3f8d37f991e138894ec3b4e9a754a40cdfa49caf72ad3d0217  docs/evidence/splash-uboot-motion/focus-55.png
DATA 937a69079635dffd1f56c6b9937ff1fbe6a9586bbc3be76cc1225bb7351e7964  docs/evidence/splash-uboot-motion/focus-60.png
DATA 312fc297a5186f9ca88d390823f3aeb27026e308dc4118f5474709b47b9840c1  docs/evidence/splash-uboot-motion/focus-65.png
DATA 90df8e93c3070659a91390b4ece8760ade4e698a1e0db40bbd8dada0e0b5a9b1  docs/evidence/splash-uboot-motion/focus-70.png
DATA a4ece8f965a8d04a3db8d62d3df118564a2fa45abd3115839ee97fa0ccc4ee0e  docs/evidence/splash-uboot-motion/focus-90.png
DATA 3479d31e302cb5ed65dd82150c109d3b26c88c21143d3bc6f2e37a8c964f66b4  docs/evidence/splash-uboot-motion/keyboard-focus-30.png
DATA fc54f15c8f969569ee5c3c9312342b24961e69a3bbc3050c52d31909afdc6f21  docs/evidence/splash-uboot-motion/keyboard-focus-50.png
DATA b5d5a89184ae66833f4e3dfa0cef65a6bd35e87fbe4690039b7b4d29bdb8c47a  docs/evidence/splash-uboot-motion/uboot-target-physical.png
DATA d411b25e783eae3d63736a1bca1acf3c8f6e5c5479c035173134e90d615e7406  docs/evidence/splash-initial-scene-ready/20260922T224622Z-keyboard-visible-focus30.mp4
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-initial-scene-ready/keyboard-visible-restored-native.png
DATA 0fd988037536dd0b6d21f9e1abfab558fe913cbcc666f74ce83bd363a85c9bcb  docs/evidence/splash-initial-scene-ready/keyboard-visible-hidden.png
DATA 69b610fa9249b2b6fcd89235641829e83a63687cab97d5e7f73806e322013741  docs/evidence/splash-initial-scene-ready/keyboard-visible-shown.png
DATA 14439fa6bff4714efb1e15073ec2aae890e8bca546f1567db46d71c389a819a3  docs/evidence/splash-first-modeset-preserve/20260922T225553Z-first-modeset-idle-logo.jpg
DATA b914704003bd4f7f2fef7e6293888a90bbd9cf72549c5b323c73e23f6788b59c  docs/evidence/splash-first-modeset-preserve/20260922T225553Z-preserved-first-owner-to-sway.mp4
DATA 122fc85a77830ab38e0a3da1ab3cd2d3d23afb2c78f8c11034f11afd4917f1c0  docs/evidence/splash-first-modeset-preserve/20260922T230013Z-first-modeset-recovery-shell.jpg
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/splash-first-modeset-preserve/sway-native.png
DATA 8d32feee01660f8828efb7fb638ca9544fee143d5da836b661089543131f53ac  docs/evidence/splash-first-modeset-preserve/preserved-owner-logo.png
DATA cf1b9a2acb27341bed769554ddd762f79057d31e85e5205c379dfc9d7b7f2203  docs/evidence/splash-first-modeset-preserve/preserved-sway-shell.png
DATA 891ff11bac41d4153ed044baf6d72cfab2f78437187d5590b84239255f5db27c  docs/evidence/shell-real-touch-keyboard/20260923T000200Z-keyboard-real-touch.mp4
DATA 8dfa332d6b5c5f2c207fcde9cf5ef70303715f53ebc9c9af748a7da0b2b800a9  docs/evidence/shell-real-touch-keyboard/after-test-native.png
DATA 3da258b19965badf7fd6980a7014caf28b41ab12d947699b21e83ccf6f93a096  docs/evidence/shell-real-touch-keyboard/during-test-native.png
DATA f56be25c740014a5544f935c3716b748eda2afb016c9a8b5e3ed9edada47ded7  docs/evidence/shell-real-touch-keyboard/20260923T001007Z-keyboard-visibility-real-touch.mp4
DATA afc050c01a241c24d9be12a55a509bec7ab1db14ae57f57177d15aba554ce93e  docs/evidence/shell-real-touch-keyboard/20260923T001244Z-keyboard-after-followup.jpg
DATA cb6db86340520a8a1ec7bf6efa76bc40ce6bca085080982a9237fe6858ecc70e  docs/evidence/shell-real-touch-keyboard/after-followup-native.png
DATA d2c95c3e68203540cdac39b82f4531054ec9a54c85b860243e6a6478a3bd4ebe  docs/evidence/shell-real-touch-keyboard/physical-keyboard-hidden-49s.png
DATA 699a0eb71ddfd1a16cc438ba9476960cd64da7da64474ba81705b5d8fec17534  docs/evidence/shell-real-touch-keyboard/physical-keyboard-hidden.png
DATA dd1986ef7d2ea46e78b42e85aeaac344bc8e5dfa6a029eb6a94dab9a2b5b0e93  docs/evidence/shell-real-touch-keyboard/physical-keyboard-shown-56s.png
DATA 6930b7368e408187b3d9a320f608909aee2b93f8bfb6653c639f1fe65295f3ca  docs/evidence/shell-real-touch-keyboard/physical-keyboard-shown.png
DATA 7168cfc491aba317481d812179ef49c50ff4019a301c1002be40e843090035f9  docs/evidence/shell-real-touch-keyboard/physical-typed-output.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/shell-real-touch-keyboard/visibility-followup-native.png
DATA 34db69480a48ba8b37dee547272d4454475f3486b81aeebe0e362e376377042e  docs/evidence/shell-real-touch-apps/20260923T000357Z-apps-windows-real-touch.mp4
DATA 7073ea6fce87e7de71aee1555c2071dc31d5ac670aecb760de50595d7151b025  docs/evidence/shell-real-touch-apps/after-test-native.png
DATA 4db0908c176349a92bb37262838ccb7bfee78f514261612c621512d3716972a5  docs/evidence/shell-real-touch-apps/physical-apps-menu-29s.png
DATA da2f137f24175df5bd2f3f2b7940e927ab2696e2f1c2a20ccb513aec95a73a25  docs/evidence/shell-real-touch-apps/physical-monitor-30s.png
DATA dd82c6f81ffc0af214253c8327b59c8bcc2b7515555146ae732f1ae1fa09a191  docs/evidence/shell-real-touch-apps/physical-terminal-exit-49s.png
DATA 91880c8fa17a7933936e95327c51c5d6dc6820109864be059dc79eccd1271ebd  docs/evidence/shell-real-touch-system/20260923T000520Z-system-controls-real-touch.mp4
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/shell-real-touch-system/after-reboot-native.png
DATA c4ef2ed1c0d302148e97350183116b889a00892b90fe68b9936d57f57225e294  docs/evidence/shell-real-touch-system/system-boot-logo.png
DATA 378020ceb726f240276649c34bfc646c22b9f141386ed2be3e8a68d90fd36493  docs/evidence/shell-real-touch-system/system-post-reboot.png
DATA d8323e6e649fe56333be64aab1ed9c36ce8884ac8651b1aeca5f0917dcf71f79  docs/evidence/shell-real-touch-system/system-pre-touch.png
DATA fc258d16b77e22de46ea70d6a614818ef085cf5cb242af4d69381168605a3ce3  docs/evidence/shell-real-touch-keyboard/keyboard-toggle-cropped.mp4
DATA 92d34deb2afd707e52cae6bd747edc2f3f6d34fa328e0244d3004d5262add5a4  docs/evidence/shell-real-touch-keyboard/keyboard-toggle-cropped.jpg
DATA 1abe57ed5618a0e755e972c8cba51ed3df2dc3aedfa977a31ccc96c2e4c89903  docs/evidence/offline-help-injected/editor-card.png
DATA 537c6cf93ae83dd7c254a64e9d07504231d68d9b71d9297dbd01f06cfb4c934d  docs/evidence/offline-help-injected/editor-running-home.png
DATA 2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7  docs/evidence/offline-help-injected/editor-running.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/offline-help-injected/error-help.png
DATA 755c39d0a82d53456d604af8d84133304b009e72aa3d6a66bd12a6dd5d9d5a12  docs/evidence/offline-help-injected/help-back-apps.png
DATA fdb66d113c05ad36d3441268aa56e92d798f5504601d0f88ac0151d678508e1f  docs/evidence/offline-help-injected/help-keyboard-page-3.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/offline-help-injected/help-page-1.png
DATA d30c3336ada6dc56522cc42a7e3015a87fd37c9d6a4e5eca1bb9d82334d23fd9  docs/evidence/offline-help-injected/help-page-2.png
DATA 2e6790919b0d6dbe9e3469b042b0eea0ff38c84ce066ffc59f44c46818869a52  docs/evidence/offline-help-injected/launch-error.png
DATA 099d87b6928bf49f107323a8f4f71d13d0df29e6ddb409cd59ac25dbaa216721  docs/evidence/offline-help-injected/nnn-card.png
DATA c6427f6710ccde570d29e8ec2aba99f32193e802e88cb1f460dafeb8292b7b1a  docs/evidence/offline-help-injected/nnn-running.png
DATA 1abe57ed5618a0e755e972c8cba51ed3df2dc3aedfa977a31ccc96c2e4c89903  docs/evidence/offline-wifi-image/editor-card.png
DATA 3be4d8c8a8bdc63f93ef1e56821558857bd1cf337fa11190ba8c44c396355823  docs/evidence/offline-wifi-image/editor.png
DATA d30c3336ada6dc56522cc42a7e3015a87fd37c9d6a4e5eca1bb9d82334d23fd9  docs/evidence/offline-wifi-image/help-2.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/offline-wifi-image/help.png
DATA 099d87b6928bf49f107323a8f4f71d13d0df29e6ddb409cd59ac25dbaa216721  docs/evidence/offline-wifi-image/nnn-card.png
DATA 4d16393ff67ea278621808d6c769116ef7719de2a1d8f741589b2dfefb72b460  docs/evidence/offline-wifi-image/nnn.png
DATA 717c4f4ee0c143fe7e79ec9aa43cfcd2ec4c16c5bf305a0faa8bb42c068537e5  docs/evidence/offline-wifi-image/wifi-regression.png
DATA 44e881c144e5ff2ef02a43b7ce2dd585884cb655ac94b702df496af462e4ec65  docs/evidence/offline-wifi-image/lf-trial.png
DATA 81a2ca6124a20845272f6762e8aaca7a47d60ab31f39b5b651e4fc1a7f71a9b5  docs/evidence/launcher-gestures/edge-states/empty-overview.png
DATA 20ab1b0d089d37cc5fe05746fede71c2b768a3995b916a90a4ebadc90659e986  docs/evidence/launcher-gestures/edge-states/stale-after-close.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/launcher-gestures/edge-states/stale-back-apps.png
DATA a72a13b46a2df3201dd53082527aca2fc8bec74c38074735192de8502f0af16a  docs/evidence/launcher-gestures/edge-states/stale-before-close.png
DATA b3f3a62fd1b4d479b02a588bec7a91e924bd134cbf9a23cf31f45cf6bcee0aa7  docs/evidence/vglite-scene-board/diagnostic/scene-first.png
DATA 980450a82edfe5e1a218767be6329d55d4f118675a4e2dd5bb588ed24f95137b  docs/evidence/vglite-scene-board/diagnostic/scene-later.png
DATA c0b5297def4c6933b592be976b8f75fdf950bb20a8ad2ff1b998d79d97857ddd  docs/evidence/vglite-scene-board/initial/scene-first.png
DATA 4d5366204d74a455b767a10cbfbb74cee66fb41557d1c8a2f4bfaff84565e457  docs/evidence/vglite-scene-board/initial/scene-later.png
DATA bbfee295cb830d6eeb54ff3ae5df0161d224ce74c2b7133a3671a70bd7942784  docs/evidence/card-shell/board-first-trial/apps.png
DATA 5de4285d05627ab6acc973d86a98cc12d0e992818adfd4f97df41f803450b212  docs/evidence/card-shell/board-first-trial/cards-back.png
DATA 41b120bb9cc9685b22d8d58881dc259dcb874d424cd95113aafdffdd995617a3  docs/evidence/card-shell/board-first-trial/close-exit.png
DATA a35c90014131cd838fdfadeed323c55c38a3c5f5f3ee5b3a4b4764324404b098  docs/evidence/card-shell/board-first-trial/close-timeout.png
DATA f97d20b16871565dbf99789965849649af1767dd45aa14172ee6dc7551db0e96  docs/evidence/card-shell/board-first-trial/closing.png
DATA a49bf1b809ce5c4030308ed8b721a4e78601d3aa94d4373daeb24a8c8b388071  docs/evidence/card-shell/board-first-trial/during-drag.png
DATA 368209ce1658ea0b941b3836bd445a3f075cb8491ba970184a92dd90b90383f0  docs/evidence/card-shell/board-first-trial/expanded.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/card-shell/board-first-trial/help-back.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/card-shell/board-first-trial/help.png
DATA be41861755173bddedd3d05b001c86d9c1ee26a576c37de93f35dec7a094cbfc  docs/evidence/card-shell/board-first-trial/home.png
DATA 41ca39ab8dee0e58cffd6c5ef0f78ce3627040b464a3aca05c929b579f843a38  docs/evidence/card-shell/board-first-trial/keyboard.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/card-shell/board-first-trial/monitor.png
DATA a287815a1ef46c57345d5491451f154e6b97dea5897cfac2f261bb66759e18f7  docs/evidence/card-shell/board-first-trial/normal.png
DATA 4741c4e54be909b4b4f3935d3ea9785f5221a2468e06bc522b1cb6c58b6f721d  docs/evidence/card-shell/board-first-trial/one-live.png
DATA 9bfb0f7f50043d736abf921550a75f4066003dd5cc9961a007c6bb8382bc063d  docs/evidence/card-shell/board-first-trial/private.png
DATA e6c7b02ce60d06dc6ab3a93f9e3815c3c38c5853c87cb2e28acb76b2f480ae08  docs/evidence/card-shell/board-first-trial/system-back.png
DATA 2655a66f615b47177559b60d2d7158281e257c65d57683a55d4f9c4ae5342e71  docs/evidence/card-shell/board-first-trial/system.png
DATA 5036a2e6526606ff1d08ca9238de11afe1fe9a9456992770a83a646f0eca63f7  docs/evidence/card-shell/board-first-trial/terminal.png
DATA acff27e72f64374414f5df4e99d07b67021352cc1c7847d8cf54370a17774e73  docs/evidence/card-shell/board-first-trial/two-live.png
DATA 5a5ea9a36814f394bec4137494059f71a9f4106c77bc3a69f95351683d7cb4c7  docs/evidence/card-shell/board-first-trial/unavailable.png
DATA ecd7c8e4a8d937dfbe107b9b620b83bdf4564602dd50ec28c8928a72b31fa99b  docs/evidence/card-shell/board-first-trial/windows.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/card-shell/injected/apps.png
DATA 848228ed337b3505ab12cd2d7026c9ce5c8ecd7bf677c0cc8f20f45625d563b8  docs/evidence/card-shell/injected/cards-back.png
DATA 95baac46ad5ac66b710085f68f8b2408a04f86163b3f57e2ca2b3716c03f185f  docs/evidence/card-shell/injected/close-exit.png
DATA e4c7d4838047f85ee826d6169010b6bb796f22bcd2d9cb7df274d8cf5548b94d  docs/evidence/card-shell/injected/close-timeout.png
DATA f0d52c7cbe10e5eb27635483aed5254b182811c22774dde2f5cb3eae15a7a76a  docs/evidence/card-shell/injected/closing.png
DATA 4ab8e0a3d0a91b5d561c603a2fbc3b10ac1898b57c2abc210e9b1969f5f3563c  docs/evidence/card-shell/injected/during-drag.png
DATA cb69afd5d822285d22ec985af29b24b76ebe273fa838af432f70aa7984519971  docs/evidence/card-shell/injected/expanded.png
DATA b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e  docs/evidence/card-shell/injected/help-back.png
DATA 237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3  docs/evidence/card-shell/injected/help.png
DATA bc63727a810fa797ef7984e89b487e7ba43e658a1c4fa678327eded0bfcdc49a  docs/evidence/card-shell/injected/home.png
DATA 7d79b3e5329568460b47a71d34f0ef6606b403ed74bb7c1eb7ee5769501f3e0e  docs/evidence/card-shell/injected/keyboard.png
DATA 715e20363af08e957489bd79dcda9ada9c82c1c49774896664e1b5b9f092a093  docs/evidence/card-shell/injected/monitor.png
DATA a287815a1ef46c57345d5491451f154e6b97dea5897cfac2f261bb66759e18f7  docs/evidence/card-shell/injected/normal.png
DATA 74ad8be305999e8d4ad3e57c6f9005ce6d5c77dbf2c07bc55eb289df7253d517  docs/evidence/card-shell/injected/one-live.png
DATA 9bfb0f7f50043d736abf921550a75f4066003dd5cc9961a007c6bb8382bc063d  docs/evidence/card-shell/injected/private.png
DATA bc63727a810fa797ef7984e89b487e7ba43e658a1c4fa678327eded0bfcdc49a  docs/evidence/card-shell/injected/system-back.png
DATA a8d0ceda4be290060e487e62e4491677f83e06a22925112873322a5a660559a8  docs/evidence/card-shell/injected/system.png
DATA a287815a1ef46c57345d5491451f154e6b97dea5897cfac2f261bb66759e18f7  docs/evidence/card-shell/injected/terminal.png
DATA 2a7363bebeb3345d5fac2e2ff8f8ba80809ee63c2b017435e53b681135543222  docs/evidence/card-shell/injected/two-live.png
DATA 5a5ea9a36814f394bec4137494059f71a9f4106c77bc3a69f95351683d7cb4c7  docs/evidence/card-shell/injected/unavailable.png
DATA 92f8189e77044d6b77979b8fccbaded362022db1531e030ea9ab6588b0d92365  docs/evidence/card-shell/injected/windows.png
DATA 7005dee79977230539647f191250859fdde0b1dba6fd6b8be4e23cf04668f26d  docs/evidence/vglite-scene-board/padded/gpu/scene-first.png
DATA 48e8bf258f444730dbe827d5f73e83b16a558a5447b00332cef396fa534d1977  docs/evidence/vglite-scene-board/padded/gpu/scene-later.png
DATA 8845f9437717a5c103ec30a9905bb64f62d0b41d414a4e0fe8299624831cab2b  docs/evidence/vglite-scene-board/padded/pixman/scene-first.png
DATA 4d5366204d74a455b767a10cbfbb74cee66fb41557d1c8a2f4bfaff84565e457  docs/evidence/vglite-scene-board/padded/pixman/scene-later.png
# RGB565 upload correction: native synthetic scene captures
DATA 8845f9437717a5c103ec30a9905bb64f62d0b41d414a4e0fe8299624831cab2b  docs/evidence/vglite-scene-board/color-upload/scene/gpu/scene-first.png
DATA 0f0d6df50445c4c9ace8d6e0dc2406b627fdd5aa1a8a01a79051890b1ac5818a  docs/evidence/vglite-scene-board/color-upload/scene/gpu/scene-later.png
DATA 066ce3d3c67319949aafb77776ab08bf13bc22a90ffba9ca1339a3978bf857ed  docs/evidence/vglite-scene-board/color-upload/scene/pixman/scene-first.png
DATA ed2d3814ca804d3a21c29762a80f2227cde0db92df0db19268a844d9398fb93c  docs/evidence/vglite-scene-board/color-upload/scene/pixman/scene-later.png

# Instrumented GPU/CPU baseline: native synthetic scene DATA
DATA 8845f9437717a5c103ec30a9905bb64f62d0b41d414a4e0fe8299624831cab2b  docs/evidence/vglite-scene-board/cost-profile/baseline/gpu/scene-first.png
DATA 0f0d6df50445c4c9ace8d6e0dc2406b627fdd5aa1a8a01a79051890b1ac5818a  docs/evidence/vglite-scene-board/cost-profile/baseline/gpu/scene-later.png
DATA 0c22854140c93aa879eccc553e7ea85f1ac869b0ffce62b0f51e427f2a29d63d  docs/evidence/vglite-scene-board/cost-profile/baseline/pixman/scene-first.png
DATA 77d40029a1007744b82a4e89446035a437a4253b8a507f20a634dc5c415c47fb  docs/evidence/vglite-scene-board/cost-profile/baseline/pixman/scene-later.png

DATA f6fd5b602373bda6d8c0776f99ae080a7e0706c73a0f0040a7023d8c4636298b  docs/evidence/card-shell/scaled-cache-board/board/run-1-off/captures/two-live.png
DATA fa4631fea9c528ba41352b800215fb353979e66d160e2d9b8376b0709c8158d2  docs/evidence/card-shell/scaled-cache-board/board/run-1-off/captures/during-drag.png
DATA 9bfb0f7f50043d736abf921550a75f4066003dd5cc9961a007c6bb8382bc063d  docs/evidence/card-shell/scaled-cache-board/board/run-1-off/captures/private.png
DATA 55650b6737053bc2fb3f4151ee8b293ea10963515acbd6cac5ea1e690ea1eb17  docs/evidence/card-shell/scaled-cache-board/board/run-1-off/captures/close-timeout.png
DATA 64e856a1544fbedbdcac8a1bea92b9ce08e06611c0e77f3ce76265805648a609  docs/evidence/card-shell/scaled-cache-board/board/run-2-on/captures/two-live.png
DATA 37ac7bccec11e01f2c244436ee60d1a430ed7475850424f909caf0faaa3dc4bd  docs/evidence/card-shell/scaled-cache-board/board/run-2-on/captures/during-drag.png
DATA 9bfb0f7f50043d736abf921550a75f4066003dd5cc9961a007c6bb8382bc063d  docs/evidence/card-shell/scaled-cache-board/board/run-2-on/captures/private.png
DATA daf9ae76840b71eef09940dbfda654d38554f62bbe7d671d5c692c096178c620  docs/evidence/card-shell/scaled-cache-board/board/run-2-on/captures/close-timeout.png
DATA bf55548b7df7f5b7efa1016fab9955e98ed5a831d48ffeddb3de29dd8215b80c  docs/evidence/card-shell/tracked-motion-qemu/before-expand.png
DATA 0677f13977a3c6734e461a808921716c86402386695ef3343cb4a3c36ad56a69  docs/evidence/card-shell/tracked-motion-qemu/during-expand.png
DATA 51471171d73d883577104cae64254bcc039c12278d9b68502699de6c41ef0a02  docs/evidence/card-shell/tracked-motion-qemu/entry-end.png
DATA 61786ceefb7f771eb3034ecea012932c366130a3f02114d3b8b7500c4fc5e99d  docs/evidence/card-shell/tracked-motion-qemu/entry-middle.png
DATA 7033843d9fb164232b7406150f120475a2f2bb756b091bfe2a17b3fe2fe0b32d  docs/evidence/card-shell/tracked-motion-qemu/entry-start.png
DATA faf50cf2f88613f2524fcb8c130831e1b08ca2a69feca67ddfde799e5854da87  docs/evidence/keyboard-gestures/native-qemu/foot-typed.png
DATA 865c3fa18b743280892c49b63ccf7ba54049da74d83a6015a61f198a8f898b98  docs/evidence/keyboard-gestures/native-qemu/grip-held.png
DATA 4e086633efc0ff342823a72e001a56e06a6cfcf7a550441761ce19c8c748d5bf  docs/evidence/keyboard-gestures/native-qemu/grip-reverse.png
DATA ef2b4dfc9fc2fe0b2d6a7fe8c3085b4eaca2227beea99e991f5d1387c302af9f  docs/evidence/keyboard-gestures/native-qemu/held.png
DATA 73174e71bd6ef16ee9f7484ac088e4fcd44a40500c8ad03c96b0734b2cef1236  docs/evidence/keyboard-gestures/native-qemu/hidden.png
DATA 2f3ada81bf23ac6ae1c55077c3e223e1512c11db4908fe1c484e790c21df3369  docs/evidence/keyboard-gestures/native-qemu/reverse.png
DATA 1eac9525b757c36bd8ec7c4b7812c161a6ba2b375e78aa96c93810f2e082be44  docs/evidence/keyboard-gestures/native-qemu/shown.png
DATA 9638d2dfa0e296e689ad8f5da90c4a039faa3c4682e254e30e26d39244334040  docs/evidence/keyboard-gestures/supervised-grip-qemu/theme-dark-grip.png
DATA c6c93e431a8d3c8a1574594caba23ee771681d380478dac4c7c39d2fe6190a88  docs/evidence/keyboard-gestures/supervised-grip-qemu/theme-light-grip.png
DATA 0ec94093d0139736c5c6d0c7b1a707d555cc845c2d3d62e4b07cead826d7e14c  docs/evidence/coherent-shell/rust-drawer-grid-host/dark.png
DATA fb552085a88544e9759aa17a136505b6369ddeb40504a3752fcad588c142bb95  docs/evidence/coherent-shell/rust-drawer-grid-host/latte.png
DATA 1b81a035e84de1aaabea0cfda17f535da2fea12c0fa80f0ddeaadc2d4b056a19  docs/evidence/coherent-shell/rust-visual-themes-host/dark/drawer.png
DATA 58282345c66748b95c64e47ead88c3698046de3d231f5447f26b8d842bf23857  docs/evidence/coherent-shell/rust-visual-themes-host/dark/preview.png
DATA f20c8690aa16951e8f64227f734337bdf3e8b8896dc9d1b2de28d92e9fc3966a  docs/evidence/coherent-shell/rust-visual-themes-host/dark/settings.png
DATA 46f03a6e34944c00bce6b098d7f0e23cab543c12c207b81e70c3ac62524feb3d  docs/evidence/coherent-shell/rust-visual-themes-host/dark/shade.png
DATA df7ee114f05bc49ccf8cbca4354e5a7aa8d7ab78ab90a22e609c5af6dc0d605b  docs/evidence/coherent-shell/rust-visual-themes-host/dark/themes.png
DATA 03ce789d9abeb9c06b2aae2bbfc421851cb68f9316eb6d48d0d2d2f03cc1f358  docs/evidence/coherent-shell/rust-visual-themes-host/latte/drawer.png
DATA f46a27a79670a1968ceb8b4bd1fc398c8d4f3750fab75d8f96e53140b1a73493  docs/evidence/coherent-shell/rust-visual-themes-host/latte/preview.png
DATA 02a2fa43467c766afd3721e364ed738bff2ab22bf0ea2f2353b8e9bd3c28cf73  docs/evidence/coherent-shell/rust-visual-themes-host/latte/settings.png
DATA b471f7de6f27b1da4c27ac3bf52f1f2f63bca3e99b02ec4ef934812e53b24b45  docs/evidence/coherent-shell/rust-visual-themes-host/latte/shade.png
DATA ea77ac12202cc445453a9d458bfab23fe2e720e72ec4d4e0cb88dd2d1899d8a0  docs/evidence/coherent-shell/rust-visual-themes-host/latte/themes.png
DATA 01afc171955fb0625e5d17262357af043fedbb78a2811e3b11872167ba1aff80  docs/evidence/coherent-shell/real-theme-paired-qemu/app-after.png
DATA 8900500145efe6fdb13d5a705b385f034d2d56777311bdae8a0c3a64c8b6d3a8  docs/evidence/coherent-shell/real-theme-paired-qemu/default-deck.png
DATA f247e96c608ec9cba0cda92fcf924fcd6329ceb9ce3c8a0f7320ed6872e51629  docs/evidence/coherent-shell/deck-visual-qemu/dark-ordinary.png
DATA 839fd97c28444da99ece4f80fb8441d21142aabe5729e4eaff8d7d5615c959c9  docs/evidence/coherent-shell/deck-visual-qemu/latte-empty.png
DATA 9323bae053396da177251402e2773fd6d6287c6b2775db9b2b0cd0d05606e949  docs/evidence/coherent-shell/deck-visual-qemu/latte-ordinary.png
DATA b3d289baa7dc73d5d5d7a7518995d0834ee898049d01c55b199f52a4188351a3  docs/evidence/coherent-shell/deck-visual-qemu/latte-private.png
DATA ef25eecd486e05105d261e885ccf60be774ce15bc06020d360ce6f7c2d21cd32  docs/evidence/coherent-shell/real-theme-paired-qemu/latte-deck.png
DATA f2b5285c4b49724b5c2aaf2e8cb833126401fff0a0afaa2bd834685d5082999f  docs/evidence/coherent-shell/real-theme-paired-qemu/latte-drawer.png
DATA 507106852a16b574cbe443f6b77c1735d77b84624bc3e689f3578bb61c1b762f  docs/evidence/coherent-shell/real-theme-paired-qemu/restarted-deck.png
DATA da29388bc9afc242aff7b1ee051f5badb078f42d60bdafc3b843856965c22580  docs/evidence/coherent-shell/real-theme-paired-qemu/restarted-drawer.png
DATA 912d9208a2a4db6ddb32844228d4ed8290c6f95cb3752654ad07fa6124528b60  docs/evidence/coherent-shell/real-theme-paired-qemu/rollback-deck.png
```

`group:` rows stand for a directory whose members are enumerated by
`tools/blob-scan.py` rather than pasted here; the scanner's job is to make a
member appearing or vanishing visible. Individual hashes are recorded for
every blob that is on, or one flag away from, a path we might actually take.

**Totals.** 35 inventory rows covering roughly 332 individual binary files:
5 on this project's own boot path (committed at `5ee0a7a`, gitignored and
fetched-by-hash from `e7f4e6b` — see A0; same bytes either way), 2 embedded
inside one of those, 121 in the Linux SDK
(120 git-tracked plus `k230_priv_gzip`), ~203 in the LilyGO RT-Smart clone,
1 downloaded toolchain, and 1 in silicon.

By class: **8 excisable now** (A3, A4, A9, A10, B8, C5, C8 — and A1/A2's
*packaging*, proven in §D), **4 excisable with effort** (A1, A2, A7, B9),
**the rest either irreducibly opaque or not on our path**.

The count moved while this was being written. A9 and A10 were committed on
2026-09-20 after §A was first compiled, which is the plainest possible
argument for §E: a document maintained by memory describes the tree as it was
the last time someone remembered.

---

## F. If someone asks "what should I buy so I don't hit this again"

In descending order of how much pain each one caused here.

1. **Is the bootloader mainline, a patch series, or a tarball drop?** This
   board is a tarball drop plus an rsync overlay over U-Boot 2022.10. That is
   the single biggest cost in this inventory and it is entirely a vendor
   process choice.
2. **Does the image-packaging pipeline execute any binaries?** One stripped
   ELF here turned out to be renamed GNU gzip hiding a one-byte `sed`. Read
   the post-image script before buying.
3. **Is the Wi-Fi part supported in-tree?** An out-of-tree Realtek driver is a
   forever tax. This board's RTL8189FTV has GPL-noticed driver source and no
   separate firmware file, but its driver embeds an opaque Realtek firmware
   payload; the *reference* board it shares a defconfig with instead pulls
   8.8 MB of AICSemi RF firmware.
4. **Accept the DDR PHY training firmware.** It is industry-wide on anything
   with LPDDR4. The only question is whether it is redistributable and how it
   is delivered; the only escape is a slower memory technology.
5. **Assume the NPU is closed.** It is, on every SoC in this class. If ML
   matters and auditability matters, budget for CPU inference or a
   Mesa-supported GPU.
6. **Check `Tag_RISCV_arch` on a vendor prebuilt.** Thirty seconds, and it
   tells you whether the vendor toolchain is a requirement or a habit.


---

## Excised: A4, `k230_priv_gzip` — 2026-09-20

The inventory called this "the one we should be angriest about" and put the
cost of replacing it at zero. Done, and verified rather than assumed.

`tools/gen-stage1.sh` now calls stock `gzip -n -8`. Compared against the
vendor binary on this exact `u-boot.bin`, at every level the SDK falls back
through — 8, 9, 7, 6, 5, 4 — the compressed streams are byte-identical, and
so is the finished `fn_ug_u-boot.bin`:

    vendor k230_priv_gzip : c0fb8d95a983c33f3d0a1d7f18de721314878cb3322eaf62fbb1d2788d26b0c4
    stock nixpkgs gzip    : c0fb8d95a983c33f3d0a1d7f18de721314878cb3322eaf62fbb1d2788d26b0c4

**No vendor binary is executed to produce our firmware any more.**

### What that took first: reproducibility

The comparison initially said the two differed, and the difference was not
gzip. `mkimage` stamps the uImage header with the current time, and the
K230 firmware header carries a SHA-256 over the payload, so two builds of
identical inputs differed in 32 bytes at offset 12. A real change was
indistinguishable from a rebuild.

`gen-stage1.sh` now pins `SOURCE_DATE_EPOCH=1700000000`, and two consecutive
builds produce identical bytes. That is worth more than the excision: from
here, a hash that moves means something.

### Hashes that moved, and why

| row | now | why |
| --- | --- | --- |
| A2 `fn_ug_u-boot.bin` | `c0fb8d95a983c33f…` | the gzip CM byte fix, then `SOURCE_DATE_EPOCH` |
| A3 `env.env` | `3a9664f43f8d1b50…` | load addresses moved above the kernel |

A3 is also no longer byte-identical to the SDK default: `blinux` loads the
device tree and OpenSBI at `0x8400000` and `0x8000000` instead of
`0x2200000` and `0x3000000`, because a 60 MB NixOS kernel at `0x200000`
overwrote both. Observed on hardware; see `docs/evidence/hardware-boot.txt`.
That changes the ENVIRONMENT, which is data we generate with `mkenvimage`,
not the SPL or U-Boot binaries.


---

## Rescan, 2026-09-22 — the scanner exists, and stage 1 is a derivation

`tools/blob-scan.py` landed, and its first run over the vendor checkouts
found what §E predicted a hand-maintained list would hide: **3 080 binary
files with no row** and four `group:` counts that were wrong. The LilyGO
clone's OpenCV archives were recorded as 25 (there are 15), its `kmodel/`
tree as 87 files (401, most of them sample images the glob also matched), the
examples glob was one directory too shallow, and C8's two `k230_priv_gzip`
copies had never been given rows. Two of the project's own rows were stale:
A2 at `0f8feb74…` (the build before the CM-byte fix) and A3 at `f522ba13…`
(the SDK default, not the modified environment the card carries). None of it
was hidden on purpose, which is the point: a document nobody is forced to
update describes the tree as it was the last time someone remembered.

**What changed in the MANIFEST.** Two classes were added to the table at the
top: `DATA` for binary files that are not code (images, fonts, test vectors,
certificates, documents — the eight photographs in `docs/evidence/` and the
board photograph on the site are the reason it exists), and `SRC` for a
source tarball or checkout a nix file pins by hash, which is text and must be
told apart from a fetched blob. Every vendor binary is now covered by a
counted `group:` row or an individual hash, 68 rows in all; the scanner
verifies 54 of them against bytes on disk here and walks 45 422 files to do
it. `docs/evidence/blob-scan.txt` is the run.

**What changed in stage 1.** A1, A2, A9 and A10 are now produced by the
flake from source — `nix/uboot-k230.nix`, `nix/opensbi-k230.nix`,
`nix/k230-sdk-src.nix` and `nix/stage1.nix` — and A3 from
`firmware/stage1/tdisplay.env`, a text file in this repository. Nothing is
fetched by URL except the three sources, which are the `SRC` rows. No
release tarball is pinned in `nix/stage1.nix` any more, so A0's warning about
a release hash is satisfied by there being nothing to check; the scanner
still reads the file, and would refuse a pin with no row. The one executed
vendor binary, A4, stays excised: `docs/evidence/gzip-equivalence.txt` is
the measurement redone with both hash sets. §D's third reproduction was
redone in Nix too — the packaging over the vendor-compiled `u-boot.bin`
gives `c0fb8d95…` and `3872df5a…`, the bytes on the card, and
`docs/evidence/stage1-from-nix.txt` shows which 40 bytes the CM-byte `sed`
changes.

**Later the same day: it booted.** `docs/evidence/stage1-from-source.txt`
records the board reaching the NixOS login prompt on the pure `nix build
.#sdImage` and hashing its own card's stage-1 slots to this flake's
output. So A1, A2, A3, A9 and A10 are now **E1 in fact, not in prospect**:
built in Nix, booted, and the gitignored vendor-compiled files in
`firmware/stage1/` are a bisect fallback that nothing reads unless asked
by name (`K230_STAGE1=vendor ./tools/flash-latest.sh`). Their MANIFEST
rows stay, because the files still exist on the machines that built them
and a fallback whose bytes drift is no fallback. A7, the Xuantie
toolchain, is off the path entirely: nothing this project ships was
compiled by it. A4 is gone. A8 is silicon.

**What did not change.** A5 and A6 are exactly where they were promised to
be: the same 32 768 and 1 660 bytes, same hashes, inside the SPL we
compiled, at `0x23f80` and `0x23900` of `u-boot-spl.bin` — 14.7 % of a
222 816-byte SPL. Compiling it moved it. It did not remove it. And one thing
the boot settled that the inventory had not asked: the vendor's OpenSBI
copies the device tree to `0x2200000`, inside the kernel's `.BTF` section
(`docs/evidence/opensbi-fdt-lands-in-kernel-image.md`); the OpenSBI built
here passes it through, and the board's `/sys/kernel/btf/vmlinux` now reads
BTF bytes where it used to read an FDT header.

### Video-trial evidence, 2026-09-23

The following DATA assets are bounded evidence for the Big Buck Bunny software
streaming trial. They are not runtime dependencies or shipped application
assets.

| Blob | Bytes | Class | sha256 |
| --- | ---: | --- | --- |
| `docs/evidence/big-buck-bunny/270p-native.png` | 210067 | DATA | `2a633a028f8e10ea939c9c5b17994ce0a0cefb7f923604c28bdbe7fa9ee7b439` |
| `docs/evidence/big-buck-bunny/270p-physical-frame.jpg` | 18221 | DATA | `7b18cca3cdb439ef572de0f46f48351f9ce4faf20aa56459893d654e987b4780` |
| `docs/evidence/big-buck-bunny/270p-physical-clip.mp4` | 265203 | DATA | `92b33c778c720a23b87bae0da2d1b05a0a7e27f76134100020a1d833eb3fb29c` |

## Launcher gesture preflight evidence

Native compositor captures; see `docs/evidence/launcher-gestures/preflight.md`.

| Blob | Bytes | Class | sha256 |
| --- | ---: | --- | --- |
| `docs/evidence/launcher-gestures/preflight-apps-page-2.png` | 37632 | DATA | `1abe57ed5618a0e755e972c8cba51ed3df2dc3aedfa977a31ccc96c2e4c89903` |
| `docs/evidence/launcher-gestures/preflight-overview.png` | 31697 | DATA | `27a6acc3f1428c79ae7345632052b46d41911ccde6f60c060e8bcd93648e445a` |

## Launcher empty/stale board evidence

Native grim captures; provenance in `docs/evidence/launcher-gestures/edge-states/README.md`.

| Blob | Bytes | Class | sha256 |
| --- | ---: | --- | --- |
| `docs/evidence/launcher-gestures/edge-states/empty-overview.png` | 28569 | DATA | `81a2ca6124a20845272f6762e8aaca7a47d60ab31f39b5b651e4fc1a7f71a9b5` |
| `docs/evidence/launcher-gestures/edge-states/stale-after-close.png` | 27341 | DATA | `20ab1b0d089d37cc5fe05746fede71c2b768a3995b916a90a4ebadc90659e986` |
| `docs/evidence/launcher-gestures/edge-states/stale-back-apps.png` | 38398 | DATA | `b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e` |
| `docs/evidence/launcher-gestures/edge-states/stale-before-close.png` | 26130 | DATA | `a72a13b46a2df3201dd53082527aca2fc8bec74c38074735192de8502f0af16a` |
## Card composition headless probe capture

Generated locally by `grim` against the pinned, source-built opt-in Sway running
under headless RISC-V user emulation. Both clients are built from repository
source; this contains no user application data and is not a photograph of the
board. Command and limitations: `docs/evidence/card-composition-headless/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-composition-headless/cards.png` | 5075 | DATA | `ba91edae2fe3b89422797769edcbcccde5195eb7574cce4a556b7ab9970d3102` |

## Final installed shell regression captures

Native grim frames from the board; source, procedure, rejected trials and limits
are in `docs/evidence/final-shell-image/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/final-shell-image/after-render-failure.png` | 38398 | DATA | `b8e4c7894698a1b2f425dc1c10d4f07af05c31fc22042285cc8725c4bfecfd9e` |
| `docs/evidence/final-shell-image/help-header.png` | 48044 | DATA | `237247e3e1a95f6afdf0abf8735655d2b738d4d408ad9015da0fd3a3b9071cd3` |
| `docs/evidence/final-shell-image/keyboard-visible.png` | 48872 | DATA | `eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8` |

## Card shell host captures

Four locally generated `grim` captures of synthetic repository clients under
headless QEMU/Pixman. No board or user application content. Provenance, commands
and limits: `docs/evidence/card-shell/headless/README.md`. Hashes are in MANIFEST.

## Finger-tracked card motion headless captures

Five locally generated `grim` frames of the repository's synthetic nested
Wayland clients and card compositor under headless RISC-V QEMU/Pixman. They
contain no user application data or physical panel image. Exact source package,
commands, visual bounds and limits: `docs/evidence/card-shell/tracked-motion-qemu/README.md`.
Their SHA-256 values are in MANIFEST.

## Card composition board captures

Native board captures from synthetic fixtures and the restored normal shell.
Commands and limits: `docs/evidence/card-composition-board/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-composition-board/after-close.png` | 4956 | DATA | `d2b360a3dc612952c203e35e2559a82af40a7c3b7979bf768a077d4cb1bf71ca` |
| `docs/evidence/card-composition-board/card-during-drag.png` | 5675 | DATA | `e2133dce11201eab18e59a4686cbe1c44d3f3ceb1b9998cc525b081f0482a0fe` |
| `docs/evidence/card-composition-board/expanded-second.png` | 4994 | DATA | `688ce8b11f991fdb18f2f908f43c2bfb85382b7cbe6dc96e714574bad3ffdf9b` |
| `docs/evidence/card-composition-board/restore/keyboard-visible.png` | 48872 | DATA | `eb0d6c97a5380669fa5e31dfbc34db07c150943d07ca8b727a21e1a8faac5fb8` |
| `docs/evidence/card-composition-board/restore/terminal.png` | 16517 | DATA | `2da9e91dc7261bec5f58c042f8f5eab8ebcafe0ca392f92b00615fbf27b363f7` |
| `docs/evidence/card-composition-board/two-live-cards.png` | 5639 | DATA | `20afc0d92b0f7e131441401c2d0c675fe1c33ce642f7c53a66cb26631a0da362` |

## VG-Lite scene fallback captures

Native captures of repository synthetic clients in bounded experimental compositor
sessions. These show Pixman replay, not GPU acceleration. The diagnostic first
capture is black before visible content; it is retained as a capture timing limit.
Commands and interpretation: `docs/evidence/vglite-scene-board/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/vglite-scene-board/diagnostic/scene-first.png` | 2115 | DATA | `b3f3a62fd1b4d479b02a588bec7a91e924bd134cbf9a23cf31f45cf6bcee0aa7` |
| `docs/evidence/vglite-scene-board/diagnostic/scene-later.png` | 4896 | DATA | `980450a82edfe5e1a218767be6329d55d4f118675a4e2dd5bb588ed24f95137b` |
| `docs/evidence/vglite-scene-board/initial/scene-first.png` | 4887 | DATA | `c0b5297def4c6933b592be976b8f75fdf950bb20a8ad2ff1b998d79d97857ddd` |
| `docs/evidence/vglite-scene-board/initial/scene-later.png` | 4894 | DATA | `4d5366204d74a455b767a10cbfbb74cee66fb41557d1c8a2f4bfaff84565e457` |

### Product card first board trial (not accepted)

Native captures of synthetic app surfaces, privacy placeholders and shell
controls from a temporary Pixman session. These are diagnostic DATA, not
firmware or an accepted feature demo. Failed assertions, parser rejection,
source artifact, and limits: `docs/evidence/card-shell/board-first-trial/README.md`.

### Product cards: injected board interactions

Native screenshots of synthetic live cards and the existing shell controls.
The reviewed interaction repeat passes; performance and physical-finger
acceptance remain open. DATA provenance, exact package and limitations:
`docs/evidence/card-shell/injected/README.md`.

### Padded live-scene GPU diagnostic

Synthetic scene captures on real RGB565 scanout with padded pitch, in GPU and
forced-Pixman modes. Actual submission succeeds, but sampled colors differ.
Provenance and unaccepted correctness/performance gates:
`docs/evidence/vglite-scene-board/padded/README.md`.


### RGB565 upload correction scene captures

Native synthetic-scene DATA on real scanout; exact sampled palettes now match
Pixman. Performance and normal-service acceptance remain open. Provenance:
`docs/evidence/vglite-scene-board/color-upload/README.md`.

| File | Bytes | Kind | SHA256 |
| --- | --- | --- | --- |
| `docs/evidence/vglite-scene-board/color-upload/scene/gpu/scene-first.png` | 4886 | DATA | `8845f9437717a5c103ec30a9905bb64f62d0b41d414a4e0fe8299624831cab2b` |
| `docs/evidence/vglite-scene-board/color-upload/scene/gpu/scene-later.png` | 4888 | DATA | `0f0d6df50445c4c9ace8d6e0dc2406b627fdd5aa1a8a01a79051890b1ac5818a` |
| `docs/evidence/vglite-scene-board/color-upload/scene/pixman/scene-first.png` | 4886 | DATA | `066ce3d3c67319949aafb77776ab08bf13bc22a90ffba9ca1339a3978bf857ed` |
| `docs/evidence/vglite-scene-board/color-upload/scene/pixman/scene-later.png` | 4905 | DATA | `ed2d3814ca804d3a21c29762a80f2227cde0db92df0db19268a844d9398fb93c` |


### GPU render-pass cost baseline

Native synthetic-scene DATA accompanying opt-in phase timings. Exact palettes
match; no performance acceptance is claimed. Commands, artifacts and limits:
`docs/evidence/vglite-scene-board/cost-profile/README.md`.

### Qt Quick probe checker image

`nix/qtquick-software-probe/tile.png` is original generated DATA, not vendor
firmware or third-party artwork. The source recipe is
`python3 tools/generate-qtquick-probe-tile.py`: a 32×32 RGBA checker
using two literal colors, PNG chunks and zlib from the Python standard
library. It is only a known image-decode fixture for the opt-in Qt Quick
probe. The 125-byte file has SHA-256
`e17961464d313d4799d8037381c5179101f982f60bd908a111e74f92c6b2cdcd`.

### Rust software-client board diagnostic captures

`docs/evidence/coherent-shell/rust-probe-board/` contains two native Sway
captures from the reserved board: the opt-in Rust diagnostic overlay and the
restored ordinary shell. They were visually reviewed and contain no private
app data. Commands, exact package/system identity and limits are recorded in
that directory. They prove compositor pixels, not camera-visible presentation
or physical touch; the diagnostic is not the finished shell UI.

### Rust drawer icon host fixture

`docs/evidence/coherent-shell/rust-icons-host.png` is a 56,149-byte DATA
software-render fixture made from fixed public `.desktop` labels and the
installed Foot, htop, and mpv SVG assets. Its SHA-256 is
`00c70a72742835f3cc0376bcfc33c81c2d491e759d5c76d29fb0e9ea2c185030`.
The rendering command, evidence limits and upstream icon license records are
linked from `docs/evidence/coherent-shell/rust-icons-host.md`. It is not a
board image or a runtime dependency.

### Work board media browser captures

`docs/evidence/work-card-media/{desktop-card,mobile-dialog}.png` are public
Playwright Chromium captures of the local static work board. They show the
card evidence menu and mobile gallery; existing media retains its original
QEMU/design/board provenance. They are host website proof, not new device
observations. Reproduction and source revision are in the adjacent README.

### Rust drawer QEMU interaction captures

`docs/evidence/coherent-shell/rust-drawer-interaction-qemu/` contains four
headless QEMU DATA captures of public synthetic cards and temporary desktop
fixtures. They show drawer open, scrolled, and dismissed states; no private
app content. The exact source/package identities, command, observations, and
limits are in the adjacent README. They are not physical-panel captures.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/rust-drawer-interaction-qemu/deck.png` | 18508 | DATA | `30d05a39baba44a579c70f369bcb1140b822178c726a689003777cf159048b73` |
| `docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-dismissed.png` | 18538 | DATA | `13fcd64a52e3fbc23c0ce7df2846c7da48bec1637d77c47bb876816f8517aab5` |
| `docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-open.png` | 69645 | DATA | `6d38dbebddb6015d7019ebce7360a2540664717838cf413ed490f7cd2828718f` |
| `docs/evidence/coherent-shell/rust-drawer-interaction-qemu/drawer-scrolled.png` | 68868 | DATA | `bd3b2e1340887b3431f6536186aab5deb63d0d3d681ec130077cf486a4b1fd54` |

`docs/evidence/work-card-media/` files `gallery-desktop.png` and `file-mobile.png` capture the
viewport media gallery and rendered document modal at source `046ae608`.
They are reviewed local-browser captures with the same provenance limits.

### Deck appearance QEMU captures

`docs/evidence/omarchy-themes/deck-appearance-qemu/{before,themed,restored}.png`
are original headless QEMU DATA captures of a public synthetic card and a
synthetic red/blue canvas plus green/yellow card brush. They were visually
reviewed and contain no private app content. Source/package identity, command,
pixel observations and limits are in that directory's README. They are not
physical-panel captures.

### Paired theme endpoint QEMU captures

`docs/evidence/omarchy-themes/paired-endpoints-qemu/` contains six original
headless QEMU DATA captures of a public synthetic live card, a two-color
wallpaper, and four temporary public desktop labels. The exact Sway/Rust
packages, fanout command, pixel checks, and physical limits are in its README.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/app-after.png` | 4926 | DATA | `01bd1a7535e53eebef58a0fcc087dfc9b305704984018be99583876c88657543` |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/restarted-deck.png` | 18333 | DATA | `5f6661ca7c2b0e81615c6f8d2ace3d50bcd4c56ee64d6a1f60d7ef85af975fc9` |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/restarted-drawer.png` | 39509 | DATA | `96cecf526f58f4ea7af374974c70640a80e484f3a20202e1c7454a26c796de1f` |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/rollback-deck.png` | 18312 | DATA | `085a00f2d55edf2e0073788f1fd302f41548e3ade7dd9a07640f020b53ea7971` |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/themed-deck.png` | 18346 | DATA | `d5b3e47bf88596e75dc8ba1f22d456de2ea478e68df4443d53d0e0489ce41f13` |
| `docs/evidence/omarchy-themes/paired-endpoints-qemu/themed-drawer.png` | 39422 | DATA | `d2b189f2421e5b2421b091ae8cbfb403e57e784a2b70f3853f8b26945ecf089e` |

### First integrated Rust shell preview

`docs/evidence/coherent-shell/first-integrated-preview/*.png` are reviewed
physical-board native compositor DATA captures. They contain shell UI and
public installed-app labels/icons; no private application content. The
adjacent README preserves exact system identity and reported navigation bugs.

### Rust shade dismissal QEMU captures

`docs/evidence/coherent-shell/rust-shade-dismiss-qemu/` contains six headless
QEMU DATA captures of the public synthetic card, empty notification shade,
and its cancellation, unmap, and live-underlay behavior. The adjacent README
records the exact old and corrected packages, command, observations, and
physical limits. No private notifications or real app pixels are included.


### Direct reveal drag QEMU captures

The 13 PNG files below are original headless QEMU captures of a public synthetic
card and temporary drawer/shade UI. The adjacent README records exact binary
identities, pixel measurements, and physical limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/deck.png` | 18491 | DATA | `b18c75f8d63c6f7792eed767e54e8ad333600d02dc504c22d62412e298def220` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-100.png` | 23526 | DATA | `96b4a3a5a268d33a466c5f0c0479ed5f02960322e97a91e014c648b142ca1d22` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-cancelled.png` | 18623 | DATA | `8c4308e515d65e4551c8d58b73b285157fd31e608c1d6c5e6c28f9bffdb89baf` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-held.png` | 23529 | DATA | `939a69ae6e42cf6dda98375ce8cfbb0869f9f9a410ac140de976e77943268621` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-lateral.png` | 23518 | DATA | `84239bc8fc2cf384f14e69e3218f75d786ff77f398f7ed5e05266de30bde8539` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-reversed.png` | 21223 | DATA | `431343213a8735a1cd1bc3cf69f452b9f68ff5b1cdc4b4d5335526b31b524854` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/drawer-settled.png` | 39433 | DATA | `edbd20a1a8f462d2cc5555330c23a5acbe0d20532886fe52d78d61ecff3ffbb1` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-100.png` | 14044 | DATA | `882d9732d92c28047a2e57808737c0cac52414f5145755b07a925e214d478e1e` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-cancelled.png` | 18554 | DATA | `2f60e48539e07f8b8de02fd8716c6d73c9de7a04a87ba80ffb9fa1123b8c21a0` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-held.png` | 14001 | DATA | `1c613ec7ce7f9785c0dbc43a963534789aa3580059b0747265369cafdc609076` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-lateral.png` | 14042 | DATA | `54300d5986b4ef86263222df1ce23aa666b39cf09bd1ab03b5e64d5b5fd1837b` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-reversed.png` | 17013 | DATA | `dcb9307591e0b3d692d2800ed80e7a3ae27ec05ad8abf9f89a76453261d0c837` |
| `docs/evidence/coherent-shell/direct-reveal-drag-qemu/shade-settled.png` | 42007 | DATA | `1dbdad98f99abd866138ab1e98c11b835be610c37c2aeed1824105666f6630ad` |

### Rust drawer grid host captures

The two 568×1232 DATA PNGs below are original host-rendered public fixture
screens for the three-column drawer in pinned Catppuccin dark and Latte. Their
adjacent README records generation IDs, checks, and the non-physical limit.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/rust-drawer-grid-host/dark.png` | 48961 | DATA | `0ec94093d0139736c5c6d0c7b1a707d555cc845c2d3d62e4b07cead826d7e14c` |
| `docs/evidence/coherent-shell/rust-drawer-grid-host/latte.png` | 48225 | DATA | `fb552085a88544e9759aa17a136505b6369ddeb40504a3752fcad588c142bb95` |

### Rust visual theme host captures

The ten original host-rendered DATA PNGs in `docs/evidence/coherent-shell/rust-visual-themes-host/` show public fixture content with the pinned Catppuccin dark/Latte appearance generations and selected Yaru app icons. The adjacent README records generation/source identity, commands, visual review, and hardware limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/rust-visual-themes-host/dark/drawer.png` | 26365 | DATA | `1b81a035e84de1aaabea0cfda17f535da2fea12c0fa80f0ddeaadc2d4b056a19` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/dark/preview.png` | 36255 | DATA | `58282345c66748b95c64e47ead88c3698046de3d231f5447f26b8d842bf23857` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/dark/settings.png` | 40662 | DATA | `f20c8690aa16951e8f64227f734337bdf3e8b8896dc9d1b2de28d92e9fc3966a` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/dark/shade.png` | 39405 | DATA | `46f03a6e34944c00bce6b098d7f0e23cab543c12c207b81e70c3ac62524feb3d` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/dark/themes.png` | 23437 | DATA | `df7ee114f05bc49ccf8cbca4354e5a7aa8d7ab78ab90a22e609c5af6dc0d605b` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/latte/drawer.png` | 26158 | DATA | `03ce789d9abeb9c06b2aae2bbfc421851cb68f9316eb6d48d0d2d2f03cc1f358` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/latte/preview.png` | 36733 | DATA | `f46a27a79670a1968ceb8b4bd1fc398c8d4f3750fab75d8f96e53140b1a73493` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/latte/settings.png` | 39223 | DATA | `02a2fa43467c766afd3721e364ed738bff2ab22bf0ea2f2353b8e9bd3c28cf73` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/latte/shade.png` | 37777 | DATA | `b471f7de6f27b1da4c27ac3bf52f1f2f63bca3e99b02ec4ef934812e53b24b45` |
| `docs/evidence/coherent-shell/rust-visual-themes-host/latte/themes.png` | 22963 | DATA | `ea77ac12202cc445453a9d458bfab23fe2e720e72ec4d4e0cb88dd2d1899d8a0` |

### Two-axis card entry QEMU captures

These six PNGs are unedited headless QEMU DATA captures of public synthetic
blue/purple Wayland clients. The adjacent README records exact binaries,
measured pixel displacement, and the open physical-touch gate.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-held.png` | 9431 | DATA | `68a92ee6cb08da4c13ea717d1046d8cf1f94aaf86fb92c0ff46534ba8f6ad73f` |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-left.png` | 9389 | DATA | `8521494c8dd2e1abdbc64da3a8d52935d51307f9910604645d5d519d88a8499b` |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-private-neighbor.png` | 8152 | DATA | `1ccaab283a509331ed392725eac48ee08ef6e8c8d94711e2a0fd0d25315ac9d0` |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-second-focused.png` | 4505 | DATA | `be1a5afadef475a2d132489465eff5b288e2983a22ea4f0782f159807aba44a4` |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-start.png` | 5817 | DATA | `294a90a5ceba6bb59f49aeffc22ba6e24b0c3c6824b052da48ca217918f501b3` |
| `docs/evidence/coherent-shell/two-axis-qemu/two-axis-up.png` | 6573 | DATA | `441248f701999c8c186ef1500c865e57970928e65b86a98895b38a5d5b48808e` |

### Pinned theme paired QEMU captures

The seven original headless QEMU DATA captures in `docs/evidence/coherent-shell/real-theme-paired-qemu/` show the public live-card fixture over the actual bundled waves wallpaper, prepared Latte still, drawer, app, rollback, and restart. The adjacent README records exact identities, pixel tests, and hardware limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/app-after.png` | 18818 | DATA | `01afc171955fb0625e5d17262357af043fedbb78a2811e3b11872167ba1aff80` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/default-deck.png` | 68829 | DATA | `8900500145efe6fdb13d5a705b385f034d2d56777311bdae8a0c3a64c8b6d3a8` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/latte-deck.png` | 55351 | DATA | `ef25eecd486e05105d261e885ccf60be774ce15bc06020d360ce6f7c2d21cd32` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/latte-drawer.png` | 56435 | DATA | `f2b5285c4b49724b5c2aaf2e8cb833126401fff0a0afaa2bd834685d5082999f` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/restarted-deck.png` | 55361 | DATA | `507106852a16b574cbe443f6b77c1735d77b84624bc3e689f3578bb61c1b762f` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/restarted-drawer.png` | 56535 | DATA | `da29388bc9afc242aff7b1ee051f5badb078f42d60bdafc3b843856965c22580` |
| `docs/evidence/coherent-shell/real-theme-paired-qemu/rollback-deck.png` | 55297 | DATA | `912d9208a2a4db6ddb32844228d4ed8290c6f95cb3752654ad07fa6124528b60` |

### Themed installed shell captures

Original native board captures from installed source `aab74fb7`; reviewed public app content, exact system and limits in the adjacent README.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/themed-installed/deck.png` | 39512 | DATA | `ccb7f23fc2cb8c7d09b73cb83a7cb094a85e9abfde64a4298dee41cb6b5c5461` |
| `docs/evidence/coherent-shell/themed-installed/drawer.png` | 55241 | DATA | `fc3d567e4527bb2e4b71e9b0460af75d02aed0c49d86c9275e92926bd50c5888` |
### Direct carousel headless QEMU captures

These seven unedited DATA captures show public blue/purple live-client pixels during the corrected direct switch and upward Home settlement. The adjacent README gives exact binaries, commands, and physical limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-coasting.png` | 5264 | DATA | `aec89c175df00b8a6729b83374cff768d0700eba120a4778f06e9a1dffe65326` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-held.png` | 5399 | DATA | `57482fe9fd326bd5f6f7d4ab946b77488853cb9c46d138d62830e46170952a42` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-home-settled.png` | 20682 | DATA | `fc4e4449694e4cca4bf113d5c2da0b5e64c6e8d401a9af865344d391efb4041b` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-opposite-return.png` | 4884 | DATA | `dc82447aaf14a1acdd66a1ea9bf46a788cc062fbba810b22232b7a9f5787aed7` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-held.png` | 4965 | DATA | `569eafcf56af3a813dffb08247134adba4679872d47b747b05c4f9ea4756e5df` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-releasing.png` | 4948 | DATA | `9e525b27f3d16d6caa0a82f6b34f3e194320f89dfa9464ba16ae046768fbdd19` |
| `docs/evidence/coherent-shell/direct-carousel-qemu/two-axis-quick-reversed.png` | 4954 | DATA | `1b9a322aa851a165bfd79821852019f7c7f30ca2eedf0a7abb5050332ac56da5` |

### Quiet deck visual QEMU captures

These four unedited headless QEMU DATA frames show the revised touch-first deck in dark and Latte themes, including ordinary, private and empty states. The adjacent README records the exact cross-built compositor and host limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/deck-visual-qemu/dark-ordinary.png` | 64191 | DATA | `f247e96c608ec9cba0cda92fcf924fcd6329ceb9ce3c8a0f7320ed6872e51629` |
| `docs/evidence/coherent-shell/deck-visual-qemu/latte-empty.png` | 72649 | DATA | `839fd97c28444da99ece4f80fb8441d21142aabe5729e4eaff8d7d5615c959c9` |
| `docs/evidence/coherent-shell/deck-visual-qemu/latte-ordinary.png` | 48886 | DATA | `9323bae053396da177251402e2773fd6d6287c6b2775db9b2b0cd0d05606e949` |
| `docs/evidence/coherent-shell/deck-visual-qemu/latte-private.png` | 46628 | DATA | `b3d289baa7dc73d5d5d7a7518995d0834ee898049d01c55b199f52a4188351a3` |
