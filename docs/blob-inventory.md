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
DATA 5672cfb5929a3af54d211a76bac5ae34f791cf1f6721b996368ec7f1ae60cc4b docs/evidence/interaction-jank/ordinary-cards/probe-video/arm-focused.png
DATA b4b2feb54cbe12d3b0cb53336d80bfc8cfd91a4b815b9f33b7ab929db068b45e docs/evidence/interaction-jank/ordinary-cards/probe-video/deck-dragged.png
DATA d96ea9a35c885e2007c8a5cac2c52fc80895e2a4f89d1a1361cb0c7eac699f29 docs/evidence/interaction-jank/ordinary-cards/probe-video/deck.png
DATA 0b0be5a757efced534c41d28eeafe9013f364edf9f1078cfcb2a9899f896a182 docs/evidence/interaction-jank/ordinary-cards/probe-video/expanded.png
DATA 55381f254639278c06843516fe461cf2666da9674cdf9beec4182426e3988743 docs/evidence/interaction-jank/keyboard/probe1/before.png
DATA 4f6eef5de15b27915e181b8b10faaf1c0a71bc5bcafebe50094c973df652917b docs/evidence/interaction-jank/keyboard/probe1/hidden.png
DATA fc2b26d3cf54847501310ef5675d445d2f387a5d9a44d0ea1a875c136ea5889f docs/evidence/interaction-jank/keyboard/probe1/shown.png
DATA 7a2f2289f6cb1dcf31e4d017265769563b9eb27d065cc0e9f351453f21a7315e docs/evidence/interaction-jank/drawer-scroll/run4/after-close.png
DATA 63af3f4281611d470feaf69ce22843d7f7b50bf88d7cdf22a3ee06497dcb821e docs/evidence/interaction-jank/drawer-scroll/run4/drawer-open.png
DATA 4cc7d9bc7a234671639008ec5c969923657d4de75b318b2f63beb4203aab1fd1 docs/evidence/interaction-jank/drawer-scroll/run4/mid-scroll.png
DATA 10554387857e0f2befb3b3f7b5a95b50281d63d470345b6c01a328eb08603ae5 docs/evidence/omarchy-themes/background-video-board-2026-10-21/render-profile/traced/events.jsonl.gz
DATA c17ccf67aa547ac359aee159ae2dc28452d8e68ff184cb2b6e92197690d2d1d6 docs/evidence/landscape-drm-holder/board/trial-a/traced/events.jsonl.gz
DATA e60a160e2c036c989b8e3082cdf47e4d32d02060dd2a25982b63ed627bf5e858 docs/evidence/landscape-drm-holder/board/trial-a/traced/functions.jsonl.gz
DATA 9f7545361103f1308392285dc905b982f98a6d7b2c0696ac20167b6d5f1c5413 docs/evidence/landscape-drm-holder/board/trial-a/traced-retry/events.jsonl.gz
DATA 40ac701d2440a95cd9d4e2c0b95bb7024ef16fe51c28b4e111b984641e0d59ca docs/evidence/landscape-drm-holder/board/trial-a/traced-retry/functions.jsonl.gz
DATA 25d1f864fbce06099ae0f0af2bb3476de54cf5ff3506b1a133711705e2a647c3 docs/evidence/landscape-drm-wait/board/trial-a/traced/events.jsonl.gz
DATA 99bab6a7531c1c5e97bf4c5f00052eb6a4afaea573358e069bb739cdc4154641 docs/evidence/landscape-drm-wait/board/trial-a/traced/stacks.jsonl.gz
DATA af2b216b1e6e6be97c2d8ec3aa74b7c7e5790747dfe93989aa142705fcf0c5b0 docs/evidence/landscape-hdmi-stall-trace/board/trial-a/traced/events.jsonl.gz
DATA 8123fd85b5c5afad79a32b226bcf2de6a8c147b3792c83f95bf8f4e36f27f891 docs/evidence/landscape-hdmi-stall-trace/board/trial-a/traced-retry/events.jsonl.gz
DATA 154e3568645238a0f6bc21fb72a41ae3e1126f9d9812df1b48836b0c1c0412bc docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/ordinary-a.png
DATA 6b99b5674b661119e865270d33eaaddb0e043ae2d4ab574911f2ec9d05f69821 docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/ordinary-b.png
DATA ad86810b1c0735f4cd2cedc112331afc6a52cf2e2787f8c004c452b99377247c docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/overview-a.png
DATA ac9718bad50f8071df99e33cee2c72b113d5cb71fafa4e49a65de8e567dac24d docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/overview-b.png
DATA 1cb688812240d80a41acd853c8dda854df3c7041d62e3465f8981baa3b3250e1 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/ordinary-a.png
DATA 47abdb889f5ec3a3ac1ee1e2a752a71ea2d2b75e6f04e398f1b909438a5841a8 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/ordinary-b.png
DATA b92c26ae53513519988f8533871b5ef0da5ce3d816f54e501034bc4c8fcfbae0 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/overview-a.png
DATA 7d76c47ba299309671042a7b4336c6d0090d2dee1f0f20e815d181d4c2185e3c docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/overview-b.png
DATA 0772c695ecea3a4d3402ba2b8dbc6e467239cf5a86269d14b5cec16720590427 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/ordinary-a.png
DATA e1215e04cf0d51f0be7555e0b663909c8fb614cfa779936e78925dac57a2e9f3 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/ordinary-b.png
DATA 33a74cc4d484efea10356015da31969b0fb55b632a3cd5a81ffe8d5ec0713097 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/overview-a.png
DATA 271b7cd1f072d238fb891a25ff068c01b07f43513430a699019c9e8425262659 docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/overview-b.png
DATA 8fe55879676a9662c4d0c7ed068f7437869a22a4abe18145ca9315e400b9a426 docs/evidence/panel-paint/candidate-scene-coalescing/camera/full-contact-1.jpg
DATA 6fb32d8d67ec0e046c31eea5614eb7fed410fdd98f41b722594cb990579db9b8 docs/evidence/panel-paint/candidate-scene-coalescing/camera/full-contact-2.jpg
DATA 563259b918556d4182fcc2620f17cd567fca6682abd015eca5361d6572f93530 docs/evidence/panel-paint/candidate-scene-coalescing/camera/full.mp4
DATA 5a2b89b995f2bb8fcfd03bb52f1c8b4d6c265b00e4dd7df77eab24400319e4ba docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced-contact-1.jpg
DATA b4eb088fec63029b100b283af1b6c71c0f403256a2e8172d02fdf65ec0e4e5eb docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced-contact-2.jpg
DATA 386de08ceb29b10af5330130f6b21329f65dffd2effe9fb124a4c7d875b43ea5 docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced.mp4
DATA eace8062bd0f7d19d5887aeb823b5184e28c82132539b1874ca17aac360f10d1 docs/evidence/panel-paint/candidate-scene-coalescing/live/before.png
DATA e7980631e2786f14afe4b7ef4960e2ee6b45dc66a66add188b95cac5fc8067af docs/evidence/panel-paint/candidate-scene-coalescing/live/after.png
DATA 4fbe0ded570c91331436bfc5b73b5c78b6769bed5bede911913ca0817c16c6db docs/evidence/panel-paint/candidate-label-ink/static-before.png
DATA 1c00680d9329156e8764348c3b06d638edd55488c9f19fd54ef2359e1ef7c71a docs/evidence/panel-paint/candidate-label-ink/live/before.png
DATA c32dbb9ce42ffb0a06c5f5d185cbe95424e128964c75296c9a7ea8766dc0c3b1 docs/evidence/panel-paint/candidate-label-ink/live/after.png
DATA ec0e34b5236fbc340ed3afca3cd657df3dfe7dbcbc9909d21500b0cfdc4216a1 docs/evidence/panel-paint/candidate-opaque-interior/live/before.png
DATA 7e629704a01b4463024d513233f49c65495e458246bff6239a4e647471631eb7 docs/evidence/panel-paint/candidate-opaque-interior/live/after.png
DATA cac6396187d3f193e964b389f5da86a80852635d2b0a2b8ce311279387241557 docs/evidence/panel-paint/candidate-retained-output/live/before.png
DATA a036bc8d1ca10157be62ee4fc1fab2535b2591c999c05244bca42388052c1a41 docs/evidence/panel-paint/candidate-retained-output/live/after.png
DATA 8f41ffe0be47661ffb7b4f75ea8a847eca8eb466c6457ef5af9ffebd4ca6d9e0 docs/evidence/coherent-shell/motion-2026-10-19/camera/full-contact.jpg
DATA e38a564b4f0a002e510a319eb9c94ca4aed51172d53c9cbeaeb5f57a76d6d695 docs/evidence/coherent-shell/motion-2026-10-19/camera/full.mp4
DATA 5a42db1dae662497c74822f66e22f7e3abfeb4ba158efe4859be2603b61ee82a docs/evidence/coherent-shell/motion-2026-10-19/camera/reduced-contact.jpg
DATA 62c08db87ee6b7110d7855ae14805c009c1c47be10804f3d528da4edbed2e9a2 docs/evidence/coherent-shell/motion-2026-10-19/camera/reduced.mp4
DATA 022cccd66d73e4dfd2f1d48c4a5e3e32abb901296e8a876d7c94a5359d814d08 docs/evidence/coherent-shell/motion-2026-10-19/diagnostic-probe/held.png
DATA 0fd107c75e8a68b2a3bf8cae56fadf5aa9814b108a179ecc1891d6b1cd8478eb docs/evidence/coherent-shell/motion-2026-10-19/full-after.png
DATA 0fd107c75e8a68b2a3bf8cae56fadf5aa9814b108a179ecc1891d6b1cd8478eb docs/evidence/coherent-shell/motion-2026-10-19/full-before.png
DATA 8aedb44255dd121e869fcc78c2845ae9dfbc52131d1ef9aa3c038ac41283e9b0 docs/evidence/coherent-shell/motion-2026-10-19/reduced-after.png
DATA 8aedb44255dd121e869fcc78c2845ae9dfbc52131d1ef9aa3c038ac41283e9b0 docs/evidence/coherent-shell/motion-2026-10-19/reduced-before.png
DATA cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88 docs/evidence/overview-backdrop-tap/backdrop-drag-overview.png
DATA 58692858d53cf304c793082fa706d60fa48c8f75d9f5da9bd08dbeae46142ff1 docs/evidence/overview-backdrop-tap/body-tap-home.png
DATA 7a2f2289f6cb1dcf31e4d017265769563b9eb27d065cc0e9f351453f21a7315e docs/evidence/overview-backdrop-tap/card-tap-terminal.png
DATA aaae7b98bbc9c44b2a7842080798db969d4b456ddbc6e8309113b6399ac52d0d docs/evidence/overview-backdrop-tap/overview-before.png
DATA cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88 docs/evidence/overview-backdrop-tap/overview-retained.png
DATA 8eea0fd6d76f9aa12a0551f52024b56987f7f64f12794160a00dc8bf322546bf docs/evidence/overview-backdrop-tap/shade-pull.png
DATA cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88 docs/evidence/overview-backdrop-tap/side-back.png
DATA 880f1bc6d3bb49be989aa9c9903b7849ee377f7b2dd78add53f0335f51600de1 docs/evidence/overview-backdrop-tap/side-tap-home.png
DATA 358adfa74c2011904c9062a9ac94e429cc7feab3f743282428d31dc57a126075 docs/evidence/overview-backdrop-tap/title-tap-home.png
DATA 1b8409b74178fdc996d5cd617e7f042ae56e59a9b1ba20cd8306bd4640fbd42b docs/evidence/mainline-display/physical-2026-10-01/minimal-probe-recovery-2026-10-02/home.png
DATA 09218a4f2d904716a63418e0ebc38cfc2d055350ffab11032bd0d65bb81531ad docs/evidence/omarchy-themes/background-fit-modes-board/chooser-heading-tap-fit-1280x720.png
DATA f5905b8474ee17347b47c5c10095b943e9c57a47bf9dd292ea306c99105cd4d1 docs/evidence/omarchy-themes/background-fit-modes-board/chooser-status-overlap-before-fix-1280x800.png
DATA ac3676b1a60096e88123ab3277054e999692f03b8697648009f4e984c9af5343 docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-center-1280x720.png
DATA 58b186e46e68486485a3d4ad80bc5a662a2a28aa201c6d49f12d4db44cf31663 docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-crop-1280x720.png
DATA cfe77480071057630b90959f93fb44c86604770c00b147d9c7a1487a6dd84e24 docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fill-1280x720.png
DATA 0ece7fa2d055ee2280e571296feda685718121e5bdbd59c68e305fd40ae794ba docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fit-1280x720.png
DATA 5381a73cd0ce1546f95ab5cd6ef593d9a7e7a241cdaeeb003636bc61903a89cd docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fit-after-restart-1280x800.png
DATA 38b60ddf4765ade9f10446893749aa659a246e89b3175a4b61c5587f8fdabb9c docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-solid-1280x720.png
DATA 76e95966c4019a03ccc3cc96696469840f4105108d5ebf65413d0df68d7a05e4 docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-center-1280x800.png
DATA 39e8fbfb80737619e0bfb4bf936f15110130caaf06ce880f3173936778230647 docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-crop-1280x800.png
DATA 573350f46079dcc3a805887d3aea0d690f22169dbf42b192216098921cb815cf docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-fill-1280x800.png
DATA 3c5a18862d13d995e8a516eee806faa4e3507dff4961e57d9faea618037872be docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-fit-1280x800.png
DATA 19b3bf9816093b2c87c747b14c75fb9368a13b9cebf2f99e9c7608f262fca03f docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-solid-1280x800.png
DATA ef9ef4431135292a7384a81178ec6f230ad203e5b90394d4139e706ce7681d23 docs/evidence/omarchy-themes/background-fit-modes-board/overlay-chooser-1280x800.png
DATA 45bd142c99c8c0f702dedcb97e98aa4c4ad78ded4bba9067f18dd535b69853fe docs/evidence/omarchy-themes/background-fit-modes-board/overlay-home-after-restart-1280x800.png
DATA 035ef7a8d29ca62a7d93b46e8e711c33e3a7bd8bb81ee70a1e293cac55d3b2c2 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/app-menu-adapted.png
DATA e87aa670e0f44d5df88f2557802510470e407f9e89cde9176c870225e4acd170 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/app-menu-baseline.png
DATA e25bde2aeed303bb0f318292e527f6dc12752579d018309514a851c0236eab0b docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/baseline.png
DATA f3aba6dcba026149c1d0bee499c6d0bfe245286f3f3ce57667a6b69aeb6392c2 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/drawer-focus-adapted.png
DATA fac3032e908aee0313637415c017bfa88ba034dee0e1cccacd2bec0026718f94 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/drawer-focus-baseline.png
DATA 935c93768c4d7468484fd3b48ded32f2a28c93b8b6ad5735dbcba1824923beba docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/font-spacing-adapted.png
DATA 551ffc44f607dd64f172f050276ca858eaac39674c1e76b4b005549315e4d906 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/help-adapted.png
DATA dc51a79c53b67e1ead64c32b1ce4be9fb2908b8cdb6f632846b314b77cf4d190 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/help-baseline.png
DATA 2bae5e80ba30aa3686a1a8665b53b24294122db619f77632e50196544e663468 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/home-adapted.png
DATA 0de7b275e7ffe891501352e5489041e2b9f1c2100fc0fbb0222c53d359bc0ed0 docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/home-baseline.png
DATA 623061d59c3f38531b61e47f418ccd5f2ae29990fb1a4af145e1e30f40a7889f docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/settings-hover-adapted.png
DATA 1250dd1a8b302938865b558775cf818d8f67f80d44484a7147469b4b338c213c docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/settings-hover-baseline.png
DATA e25bde2aeed303bb0f318292e527f6dc12752579d018309514a851c0236eab0b docs/evidence/omarchy-themes/font-spacing-adaptation/baseline.png
DATA 2c971a30f7138e3ed0b0cfeb4538bbdf432e33ac65cc329225fc7b5af9d52a6f docs/evidence/omarchy-themes/font-spacing-adaptation/font-spacing-adapted.png
DATA d470fae779b6106d7c6cd59cb250d928f28c0e97f7f0192be618863933a1d4ee docs/evidence/visual-language-panel/board-panel-100-drawer.png
DATA 976484f682c9a36422d53f52c6f967d0a6b910701e5c58df16b7ab1bfa8d3004 docs/evidence/visual-language-panel/board-panel-100-drawer-roles.png
DATA 6cdb9a7768d00c85c01e951a6db5bd4af13cc7eeb767867020b63c23d5d744ae docs/evidence/visual-language-panel/board-panel-200-drawer-roles.png
DATA 57c5b786d39209e28d67addb5c557f0d93e875a78483d7d7d403021acc9d7a71 docs/evidence/visual-language-panel/board-panel-100-home.png
DATA ac5aa88ae6dadc73672c322a57ce91dbfd4216b4b64678f188c1c691243f6270 docs/evidence/visual-language-panel/board-panel-100-settings.png
DATA a51cada8f2a82729c14c2f1264cfb951e93776c00de0c1f4132575c3fbce22f8 docs/evidence/visual-language-panel/board-panel-100-shade.png
DATA d2318655f0617eb8a3eeaa7cd60c40a716cb0dd3e5b0d4cbca8aeb27ddd17834 docs/evidence/visual-language-panel/board-panel-100-vision.png
DATA 482d8a04f510b691584287b3225da562874dd15f8184ddf12e7a4415de17154d docs/evidence/visual-language-panel/board-panel-200-drawer.png
DATA 67306afb8745e6fe7f2eff6e0c2d3d324b3531d1c435e3f9a638db9fb5d86b11 docs/evidence/visual-language-panel/board-panel-200-home.png
DATA a4ece9287f51c2d7583781013563932f9c92c04c7f686e7fe3b7ed82e7304435 docs/evidence/visual-language-panel/board-panel-200-settings.png
DATA 6b8e7a461293f2ff62576ab4a5d0bda53835fb50c0f8c49cdc574183ec1f7beb docs/evidence/visual-language-panel/board-panel-200-shade.png
DATA 7b87bebba551c421c6a521324e524da735f8d333cc6449c179c4ab1894f098ae docs/evidence/visual-language-panel/board-panel-200-vision.png
DATA e1b06b77e8d7b8072e5cd8b09aedabe4c094c5c719d8bcd5c1b90399b15a4bda docs/evidence/visual-language-panel/host-drawer-steps-1232x568.png
DATA 0074e6a96aaef045a1a3e41760cd2ba9ce75423028e3553cbb125e15ff902356 docs/evidence/visual-language-panel/host-drawer-steps-568x1232.png
DATA 6c932721f51eccfe719486e1474e411c6303c2a95bf1ea7c6240260f1b939669 docs/evidence/volume/closeout-2026-10-01/expanded-real-stream.jpg
DATA ef63b26ac876397657f42f5e72039874a82b658ef9cd11abf16d96047ed3d8ee docs/evidence/volume/closeout-2026-10-01/hud-dragged.jpg
DATA 65557a7fe7f93d61c76232c8484f87ac11c2ee475618c61de0c620d1c2da304d docs/evidence/volume/closeout-2026-10-01/hud-hidden.jpg
DATA a1f5516863d468fdb7db50ed5e7ec0b8b6df2cbec8d0631dc8a5d50e7ce8ca7f docs/evidence/volume/closeout-2026-10-01/hud-over-app.jpg
DATA c8b6f87b725207d49bb2ada8b93e41afd403490494355371816b95603daffa01 docs/evidence/volume/closeout-2026-10-01/hud-over-home.jpg
DATA 22656082dcb995fd55faa23823c983683fea7d7c08cb15cbeb1c53d771f8a849 docs/evidence/volume/closeout-2026-10-01/qemu/hud-collapsed.png
DATA d45bb5c45bb915c22852043bd4db37866331c8afa0de69bf117bc69fedce44d6 docs/evidence/volume/closeout-2026-10-01/qemu/hud-expanded.png
DATA 32e76a43c396a304855f725750ca6544f9b8a9e5a29b59f8eda5b6f88657a4c1 docs/evidence/volume/closeout-2026-10-01/qemu/shade-both-sliders.png
DATA 853b935d2441b6214c8efc4a256864f49e7360a622b455be8fe841404d143578 docs/evidence/volume/closeout-2026-10-01/settings-75.jpg
DATA 3b5fcbe1917ffa20fcbf2c6583f14c0c57e6635cbdec9352faf40d2a6be016c8 docs/evidence/volume/closeout-2026-10-01/shade-50.jpg
DATA b10f493aa0185ceb875dd2787cc0402b70985726ec37133145abbae4fae98434 docs/evidence/home-widget-design/closeout-2026-10-01/board/edge-indicator.jpg
DATA e34f6168a23d7020248b0c195482c50ad9912a845fb94c6b3b2a31c0ccb8e266 docs/evidence/home-widget-design/closeout-2026-10-01/board/fling-drop.jpg
DATA 4d2b3933bf5bc0d1b8cd4c48c3d4000c04902c8a404dda58bdce1402fef08903 docs/evidence/home-widget-design/closeout-2026-10-01/board/new-page-drop.jpg
DATA d26682489466c02d7da1f5abbe579a072adaddd6d8d34b68d0422271cc189247 docs/evidence/home-widget-design/closeout-2026-10-01/board/widgets-battery.jpg
DATA bb79b07f61f8751675f7e072479912e19334af0943a8ec9389237848771d41d0 docs/evidence/home-widget-design/closeout-2026-10-01/board/widgets-bubble.jpg
DATA a9904e028f756621522a097434859d2ea30343799f76a743c388d04df97ed1f2 docs/evidence/home-widget-design/closeout-2026-10-01/board/widgets-dot-matrix.jpg
DATA f19494f45aaf64477fa34f4a7decc48051907b68707dabce6c25e78e1019d751 docs/evidence/home-widget-design/closeout-2026-10-01/board/widgets-thin.jpg
DATA d17d0e60b3dd8343575020284da0773c29c441874c4c1521c866115880d32b22 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/clock-placed.jpg
DATA 49e0b8b31d9a4fe2a7498490ce2375edfd77ac5143f2ba615e580cf2882a84c3 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/dock-folder-open.jpg
DATA f439a4c958c0817a03058897a8b0043713bda2c51c6c0f22074914dba018d091 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/folder-created.jpg
DATA ce0c05b14f1c6c4111d3ce64fc789ff4f350c420870c97d47b65c42826a63a27 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/folder-open.jpg
DATA b6512ddd4de177575f96278dbdc3c382a22b0285bb01e7e72841b9298b56c564 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/folder-renamed.jpg
DATA 4392aa51db53b01d5820e5a6259a2b138fc040f7db0bbbd2f63c1420ebf07bf7 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/member-extracted.jpg
DATA d17d0e60b3dd8343575020284da0773c29c441874c4c1521c866115880d32b22 docs/evidence/home-widgets-folders/closeout-2026-10-01/board/persisted-home.jpg
DATA f69f65f6c6d220143a4b54ae15b18444dc5445c734745e3597f443dff77d7ca8 docs/evidence/wifi-settings/closeout-2026-10-01/hidden-again.jpg
DATA fe473bd186bc8ac642c12a301399ee51e5a592b22e786a8a67b7fbcf421bbd90 docs/evidence/wifi-settings/closeout-2026-10-01/masked-empty.jpg
DATA f69f65f6c6d220143a4b54ae15b18444dc5445c734745e3597f443dff77d7ca8 docs/evidence/wifi-settings/closeout-2026-10-01/masked-typed.jpg
DATA fe473bd186bc8ac642c12a301399ee51e5a592b22e786a8a67b7fbcf421bbd90 docs/evidence/wifi-settings/closeout-2026-10-01/reopened-masked-empty.jpg
DATA 80e3d11f0f230c08eaee29c5ac2f972506f5e0d0863257b279a98b4526b3ea9a docs/evidence/wifi-settings/closeout-2026-10-01/revealed-corrected.jpg
DATA a1a83cc7ee51c1daac8526a3574e6d7c1ee7e07cd0e017374678709aaf9cdd50 docs/evidence/wifi-settings/closeout-2026-10-01/revealed.jpg
DATA 6cad046695bacf8c82273f735d8def70ae85b1b861fa98f431a93633fa193ad5 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/overview.png
DATA 3dae42c7878555b912b7996fbcd88937a24934699a1a151be12a07df4a7bab76 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/home.png
DATA 0830a5175acc07f25e894a3a461787325056e3fabecc07c76cd9d514a54eb6c5 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/drawer.png
DATA f9fafcd198456b9f9e52a1d395643f9690e19191316bec7b81c78682f8c570e8 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/shade.png
DATA fb40be1f2fe804f8def6a4740576c22f0d151714f7c74b86c25680c9534c241f docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/keyboard.png
DATA 0830a5175acc07f25e894a3a461787325056e3fabecc07c76cd9d514a54eb6c5 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux/drawer.png
DATA 682dbe3d1e4008082e9ab3340bf95ea2eebb91693cad1156027eb4f68bd5255e docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux/home.png
DATA 6cad046695bacf8c82273f735d8def70ae85b1b861fa98f431a93633fa193ad5 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux/overview.png
DATA 925f658f63ea96fd47bf25d8c851058d363b41cb4d769d91dd45d39cf234df10 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux/shade.png
DATA group:4-files docs/evidence/shell-responsive/board/*.png
DATA 0fbb9697614b2e271a7982f02c3296fa4febf4333363d8b656e601f2f6f3ca18 docs/evidence/omawrite/board/home.png
DATA afe1289aee3bde0c258340918783f0d77f1b437f6dd0be135bc722ec5daaf03b docs/evidence/omawrite/board/keyboard.png
DATA c96077d2ab5b3a018023c40470092f0a7b776477a44b10df80bc72e0efd0ec67 docs/evidence/omawrite/board/open-dialog.png
DATA c50fc4d406ed540a96bbab5419505d128f47d40c85c2ccf595fd054ed809d52f docs/evidence/omawrite/board/overview.png
DATA 315f096b76467534d380c55ce3138cb7b608f56d7a8cccfa461a8e0d0d820ee4 docs/evidence/omawrite/board/reopened.png
DATA b4b928946c4e72e92df8342fcaf91a65f8ea7f65bfb3297ebfffae7c0aa20c23 docs/evidence/omawrite/board/save-dialog.png
DATA 9059fe3be800fedfa5ca0c7abfcd79dabc0f94fdfbdf62ea21f3556455390423 docs/evidence/omawrite/board/writing.png
DATA 8d1fc969c90546f9bb92e15906d0b37ccc79b301e3151c6021645f51fdf018fa docs/evidence/omawrite/host/keyboard-size.png
DATA 4add3162608c3aee30e5e8b4913afdc57c5a3d733463ebd75d5529a6c8e0efca docs/evidence/omawrite/host/open-dialog.png
DATA 3ba194865ba72f16bbbb014d5c83b3b08ad80ca673215452649bbe0396a68fb4 docs/evidence/omawrite/host/overwrite-confirmation.png
DATA 187ea627a844f0032897fb3d936021d08d6ab781088b535f9d95146f8ef49ad0 docs/evidence/omawrite/host/reopened.png
DATA d51a147161151986efe98d11536e0a7b773525bcda9dfec2726931bf55fdc214 docs/evidence/omawrite/host/save-dialog.png
DATA a0bde0d87901a0a6a0fa8abe1843d4535b8cdf65450cb8da18abeafe442dc86e docs/evidence/omawrite/host/theme-changed.png
DATA 7b5409158b489163e5d453f0c80364e103792da3c126d0e04fe604622b9ddc70 docs/evidence/omawrite/host/theme-dialog.png
DATA fc9db149225963e8d76393b3de5bfdde0dfa89e2b8afd3ac98b6a92d70ded8af docs/evidence/omawrite/host/writing.png
SRC  sha256-yS3GOL/kc03qx4naWzUdSZwAYxMuCjvrgmhexpwjsfA=  src:omacom/omawrite@8f98892b26768236b2c20f4e637cf4b102d898bf
DATA b822b4b32c6ce0ba6f90b203e1a61ed9736948a5fa614eefc6c5b7cf00c674fb docs/evidence/theme-picker/background-selection/home-after.png
DATA b06525298d1317b37f8cec145127b13af5907a0f3837812dab0b848afc6f974f docs/evidence/theme-picker/background-selection/home-before.png
DATA a1606e29a77f892d0500fcdbf35495136a1c1d8b625e0c0c0031ba1956664788 docs/evidence/theme-picker/background-selection/picker-after-restart.png
DATA 4536c21f2c96e81b0b143238d2f067f4b60077765a8926a402b98f678480a20e docs/evidence/theme-picker/background-selection/picker-alternate-applied.png
DATA 9f6a4608fca4fcc74c14049acaf2adab50eca8878692835d07703f7553aba6e5 docs/evidence/theme-picker/background-selection/picker-applied.png
DATA cca5e3950a6d3a739925272dc0e039f048f5364cc640c19b6ed6039d03224e6b docs/evidence/theme-picker/finger-tracking/new-before.png
DATA 515448a93291c7f39ac2d96bd252dbded4fe3945d49f620122945c9ea0908d2d docs/evidence/theme-picker/finger-tracking/new-held.png
DATA cfbdccacc6b3b43f12afd191b3823f8fc05f90f589f426fe3a53a2dc6f1d589f docs/evidence/theme-picker/finger-tracking/old-before.png
DATA 6b7f5e9626d4c26a47e31103209876acdc73d7d36865c5dae92610464d9ea168 docs/evidence/theme-picker/finger-tracking/old-held.png
DATA 14697a7cead21bb65606f637c6dda6cb77f61619b8a3831423ac22fdef6e3da8 docs/evidence/theme-picker/row-repaint/preflight.png
DATA d13d8177d2e5446a8af382d167473d8bf443a5e8cfa6c4fa704ee4fc50d63039 docs/evidence/theme-picker/row-repaint/cpu-flamegraph.svg
DATA 65c0660b3a9b4347fe64926128dbae7400bae6701df9a55df713ebc157cf773a docs/evidence/theme-picker/working-set/loading-backgrounds.png
DATA 9edf97b5508b80673db74e264d50b99746f2b7774295b30aa2454c4017668539 docs/evidence/theme-picker/working-set/browsing.mp4
DATA 6b0475c77dce11a3802cbdb7a2c52ce91f803059f2160a02aaca08c6891889d8 docs/evidence/backlight/live-hs/live-26-128-255.jpg
DATA d05da3773efa0683dbebc6b3f176a8043af7b29cd08288fe823b4ce8f4fca196 docs/evidence/backlight/live-hs/off-on-128.jpg
DATA 2a6b3795cafc5e7ed9e70a957498807891e6b0a9585ea2637d80c38d388d4208 docs/evidence/backlight/live-hs/settings-10-50-100.jpg
DATA 1756635c6a3f7aea4e80caf0a8bf909d1211a0164c6c13e7499e5c594a985bab docs/evidence/backlight/combined-candidate/live-and-settings.jpg
DATA 19e84e2647c7f0b7344e561002e5de9e600ba015f0ae2e4f36b622efb4f2a801 docs/evidence/backlight/combined-candidate/off-on.jpg
DATA 0f55de68c97eff8199d8e2a8a789b87c391589085e90605531cfc556ba5d1a4c docs/evidence/backlight/combined-candidate/settings-ui.png
DATA cca5e3950a6d3a739925272dc0e039f048f5364cc640c19b6ed6039d03224e6b docs/evidence/theme-picker/store-relocation/current-theme.png
DATA ebc175d2acd4816f5ae26f54fcca81158565c499c88146b4b1d8e693931c8582 docs/evidence/theme-picker/store-relocation/background-browsed.png
DATA fd28b3884a4b4c93e4720a931c286dbcbc7e7339c1fa070fdfad6d8b547458fe docs/evidence/backlight/runtime-recovery/cycled-26-128-255.jpg
DATA d2f33d7a70abbaaa6bc8f6e16e309536bbba828c6e51b3c8b63f269deaec3c92 docs/evidence/backlight/runtime-recovery/live-26-128-255.jpg
DATA 53d41ebcc10164feb3cd70821119b7c6a83ce62b70c339548fe3b98764928d61 docs/evidence/backlight/runtime-recovery/off-on-128.jpg
DATA a6246c66a56d7fa3c3fcc17a6c5d1038b243f76a95cbfbe2a4188bd1c14a8888 docs/evidence/card-jobs/board-panel-settings.png
DATA b5f5de398afffe85b8aabc759cc1192a4731b42217250459900b354c2d6af517 docs/evidence/card-jobs/board-panel-shade.png
DATA 3ab9fff686da3c51ada7f76c07891e971f2ee0cd1f8507fa8bf8a92c95f9a078 docs/evidence/card-jobs/board-panel-themes.png
DATA d2318655f0617eb8a3eeaa7cd60c40a716cb0dd3e5b0d4cbca8aeb27ddd17834 docs/evidence/card-jobs/board-panel-vision.png
DATA a5e85404002a301c945fdd3a80eeb878f9b0a37c9f60f07e7ded8c4c552d7d6a docs/evidence/card-jobs/host-dark-default-landscape.png
DATA d198ed2f8ade0d14f595826bac42e2f943eab14ef73fc5fc638afc144c0dcc3c docs/evidence/card-jobs/host-dark-default-portrait.png
DATA 1b2b279fa5c0735303795b0bdbaf6fa8bee94dbfc16acc22eb09d2c026912aab docs/evidence/card-jobs/host-dark-largest-landscape.png
DATA f714891ec8d8502c12b70bb22c4773e839a474ff1dbd1fabde9174cbecc0434a docs/evidence/card-jobs/host-dark-largest-portrait.png
DATA ff3e1c3856ce9e963f05304f90ad0ac218dc834023cf0d9ddb91edd8578da391 docs/evidence/card-jobs/host-latte-default-landscape.png
DATA 929a9cf9e33d008f9040e0be57c68ea4ac2b3afab0cb9403657548f1037f2714 docs/evidence/card-jobs/host-latte-default-portrait.png
DATA 35d6a5e23c99b9dc771c1b2a722ade827cdb365fe7997384b093a853a685ffd2 docs/evidence/card-jobs/host-latte-largest-landscape.png
DATA b398a501fe669fa51f7ff2593a046f8a7a41f2f0665ae1d4e6b328e3aff3874e docs/evidence/card-jobs/host-latte-largest-portrait.png
DATA d5a067cf58487b011cb292b25575beb69455e4de7fdcc496b1fab130c4c0aa27 docs/evidence/card-shell/transparent-corners/argb-child.png
DATA e2e03191c80b95f5d5447ea6c335ce7562611a3e414c6c1e8b5e2ae3b9f96036 docs/evidence/card-shell/transparent-corners/baseline.png
DATA 5194b788f0935fc0d1a20f4da641cc65aeca78c6a70c14d4635ddaec56d4fc8c docs/evidence/card-shell/transparent-corners/before.png
DATA 5e4794e3c282afc053e7e5b4cf66c3bafe0db4e108a7b8f43c9f77d2f58399dd docs/evidence/card-shell/transparent-corners/direct-switch-held.png
DATA 6340bc84c43783022abf7e8bdd38963fc9d40c618827fac427d802a2c9f13a6b docs/evidence/card-shell/transparent-corners/drag-held.png
DATA fa57f636aa9465fc361fccf67611d137b7faab3efd60a75ea3c2ad22d2bface1 docs/evidence/card-shell/transparent-corners/entry-held.png
DATA 6b850edc100741232549e13f28ca72dd247560a691e3b2a993146a31ebbad829 docs/evidence/card-shell/transparent-corners/opened.png
DATA 9f344e2b4d2f55a3aca4f5afabfdf438d38b493f5db9664e4f1c789f90c7a1f7 docs/evidence/card-shell/transparent-corners/overview.png
DATA 51a1f993644e3c65fab7988d451d7e2808f8a53f5935e652a4e3b0c4f248b7fd docs/evidence/omarchy-themes/community-board-fixed/community.png
DATA 478d3f0346f003fba5893ca17b5b85f40d7312709d888ed944d233916fbfb75e docs/evidence/omarchy-themes/community-board/dark.png
DATA ff4004c2e6c509680505ce48431fc559d949da6413488814ad5fd66185c5cd5c docs/evidence/omarchy-themes/community-board/light.png
DATA 591299a1aafff2530dc85e24dd6ceae82c930da386311dab04ad5497f84e907f docs/evidence/keyboard-gestures/supervised-installed/keyboard-shown.png
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
DATA 58d6dad5b8afcd85e08231f3e0421518a62603a9f014d5a9cac7a15fa226debe  docs/evidence/app-drawer/original-before-redesign.png
DATA feb3292a04d2163e8c5fba8bd5f23cdba91888ef72701bf1c400df1541440a36  docs/evidence/app-drawer/redesign-fixture.png
DATA 68f0da66330c9d922e8af785197b1cedfadd6b9e7379114359f062b2be33a515  docs/evidence/app-drawer/redesign-real-icons.png
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
DATA 4eb5fe1db653b5681ffa848471dedfe8b53e543ec317ab1a6eb27d57f6eb187b  docs/evidence/coherent-shell/two-axis-qemu/regression-after-fix-up.png
DATA 42310d94fd4f97d91f585c923824b9271e7a64bdab086d0e90361e9c987b5bce  docs/evidence/coherent-shell/two-axis-qemu/regression-before-fix-up.png
DATA 8d4260d119614cceb872d1f6636340cdaf770fa0a640eceb57aa226684e70cd3  docs/evidence/coherent-shell/two-axis-qemu/regression-origin.png
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
DATA 7ff575e09fa305a06f6b7e179ffa2136a4dbdbf70db77a1f157639c08f157c38  docs/evidence/omarchy-themes/wallpaper-visibility-board-report/default-deck.png
DATA 62de4f7fa2009241ca2e1ccfb1ce933f7bfa3bff27a1b108a64b506d99cef90f  docs/evidence/omarchy-themes/wallpaper-visibility-board-report/latte-deck-cache-hit.png
DATA bb056c18d3c66b61b8ee11da40b7d18a4dd07fcd4be3ab4877d6a9a4ce573688  docs/evidence/omarchy-themes/wallpaper-visibility-board-report/latte-deck.png
DATA 760ef9193a99e8cb2c527c320170ad5195e3010d73a98ec4b55fc7613ff27ec7  docs/evidence/omarchy-themes/wallpaper-visibility-board-report/latte-drawer.png
DATA cff0560e06131cd303c14a8c7a5ee0bbeea8f571bb027ea0fbc467c8cc5671be  docs/evidence/omarchy-themes/ordinary-backdrop-covers-wallpaper/latte-deck-with-ordinary-buggy.png
DATA a4a1fa6614ebdad16f09530cea4148e7313e22cd5e2f9866be0842593b713e3a  docs/evidence/omarchy-themes/ordinary-backdrop-covers-wallpaper/latte-deck-with-ordinary-fixed.png

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
DATA 36fd6e2ca65c23b2489b7dd140236aa3035aaf2d21db806895b6815dc5affcb2  docs/evidence/keyboard-drag-usable-area-gap/after-fix-drag-start.png
DATA 4019586f78af6a5ca85d733f34a757b3dd54e5ff52cfb4ce6202a343c1dba8f7  docs/evidence/keyboard-drag-usable-area-gap/after-fix-mid-drag-backdrop.png
DATA 06a2cdb171eeebd8c3d8bfd79f0c865a038ab44b2c67fada22a29669354c2c55  docs/evidence/keyboard-drag-usable-area-gap/before-fix-drag-start.png
DATA 61c3d0b2f67f7c778a7f68f14a7ba96f1d2eb68d244aba18e5c842d259bf48e4  docs/evidence/keyboard-drag-usable-area-gap/before-fix-mid-drag-gap.png
DATA 178d4f30df386e01d30e6c4ac29f59462999b28a2b4baa32bfbf8061070767b7  docs/evidence/overlay-keyboard-resize/after-fix-keyboard-hidden.png
DATA 2d1d7470c41aaf66f10982d96e7548dc62c5f83ad48e0714b230c7a07a090d04  docs/evidence/overlay-keyboard-resize/after-fix-keyboard-shown.png
DATA 178d4f30df386e01d30e6c4ac29f59462999b28a2b4baa32bfbf8061070767b7  docs/evidence/overlay-keyboard-resize/before-fix-keyboard-hidden.png
DATA 2b485137768a3e96b33bc3bc239bfb84f895f132856f72d1a07a2303e9753675  docs/evidence/overlay-keyboard-resize/before-fix-keyboard-shown.png
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
DATA 75ed77a0908f061eb3fe9f7838064ea09c86c9e33c34e1bf5ee038900463fb43  docs/evidence/omarchy-themes/theme-preview-host/catppuccin-preview.png
DATA a28b6fe0088877677cb754fa68335d6b2b813de6f3538ef7d0aac23891465c09  docs/evidence/omarchy-themes/theme-preview-host/latte-preview.png
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
DATA 574ea4b392e0e8bdc4ee5b4f46d82b800d39c43b53e343dabe85adcaa23b945c  docs/evidence/wifi-settings/paired-qemu/wifi-auth-error-dark.png
DATA 05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d  docs/evidence/wifi-settings/paired-qemu/wifi-forget-confirm-dark.png
DATA 6a93416bc16cd60e96bf196c42afe36d52b028a02efacdb204c6ced6fcfaf6f4  docs/evidence/wifi-settings/paired-qemu/wifi-keyboard-gesture-disabled-dark.png
DATA ce8dd44606ab1bbe450fa502853249e656e8aeadc50718dfc075a006c076d317  docs/evidence/wifi-settings/paired-qemu/wifi-list-dark.png
DATA 10f0f24d1816e6ce1df6efa2f48a11acb0d9d1fd44f926fb6fabe7f4581fcda5  docs/evidence/wifi-settings/paired-qemu/wifi-list-light.png
DATA 2e0916e57186db62ee52ce18959612f7acab2a5620a61c8388d5742cf756ba8e  docs/evidence/wifi-settings/paired-qemu/wifi-masked-dark.png
DATA dd3782ac477ddfce563d062bdecdef87a5939ce815e2849a30d75c7e8a41b675  docs/evidence/wifi-settings/paired-qemu/wifi-saved-entry.png
DATA e8be5551a201b2278569864505f6602965511f222c838d349c99ebd1829641c4  docs/evidence/wifi-settings/paired-qemu/wifi-settings-dark.png
DATA 13b92f1aa8f676c535318a8b0143658763f43da0ac68dad91d4ca440b7ed277b  docs/evidence/wifi-settings/paired-qemu/wifi-settings-light.png
DATA 21fac03a2ab67a15b2a1faa45f3dea6688aa2017facc1f57315f8706edf8474e  docs/evidence/keyboard-gestures/installed-preview/keyboard-shown.png
DATA cd1abfa7fcd1ccdc3a70b8b0123f2729117b9eb21896f53576df1643f6d826fe  docs/evidence/keyboard-gestures/installed-preview/terminal-hidden.png
DATA 3df8cda30a4e3d966bed5ac2ddd15ff73cd551a065ddeb75743a57b75d3ca645  docs/evidence/omarchy-themes/portrait-preview-host/preview.png
DATA c161b1bffe2cda61a86d35158caebf2d88e7791a16f1dc4394113a8d91650ac8  docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-center-284x616.png
DATA 9d1f40b0512e74d6f37a55875c3a68588f1105305c66299cf31dd2939c458c46  docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-crop-284x616.png
DATA 485ff1a1ffcf84207e1a74173303c78bbd277bb77aa7dbfc02ea3e2f726ca2fd  docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-fill-284x616.png
DATA a6335ab79253de2ac2a040d3be03c69745f86011cafbe3f27fae9cce4edfe666  docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-fit-284x616.png
DATA 66f0984c785b5403a61c76e2fdaf796a25e7bbf8f0cf14126f0301edd41c8213  docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-solid-284x616.png
DATA 23635218049dbdca1b4d493bec892daf44a027540c88519c545bfb4c57948cc0  docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-center-284x616.png
DATA 6e3de80a94cf9196d2e6c5a5abcb03ba873062bb8e6ecb21afca95a6a6e1c3e2  docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-crop-284x616.png
DATA 9a87d376703dd3ff65675744ec5ee9d6e290cfb56651c8fcf5992b4cf52938a8  docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-fill-284x616.png
DATA a614fd07d14cc7cc2b971491063a1b67e236cc88123168f15c253560f19d9e1c  docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-fit-284x616.png
DATA e93c88cc87a33a2f8ca7fff624fcd9457f4c8746800f645d10aa9d7d2080e92b  docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-solid-284x616.png
DATA ec84e64f2f63096b88fc1c03ddb63ca360ba93d72401a6764fe053d66e6d5bd0  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-100.png
DATA fea0f40dabd3aa4fd5bbadd4a7e95205d66c93a937bf9085477e1815f6cd45cf  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-300.png
DATA 4780410f54c3f47a02258d3bab73dc18acdfb993c40ae5ca1a348f1562759537  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-open.png
DATA 2ea7344df624378e1acea8a50a07e65463a88cf32d538a79542eb0c926f7ad46  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/expand-01.png
DATA 91e8033dd6d79142ec66fb0f3e8d4612d13c5942967d94c0ed06a4b20884d66e  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/expand-restored.png
DATA 98733d800ee9bed45d9010b5b4ec4615fa165f6fb7f806566863a95628753d63  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/focus-app-restored.png
DATA 8fa91114e4b65754f27d216a1b80b96c79a7ccb6e21ab7b6684efeb5ac98d42f  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/focus-search-typed.png
DATA 39468de49f9d3bf7349a8c1b05292f915908c934749ee8e0f55b0ae32f18494b  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/home-held.png
DATA 1c663bebb1df5efc2adb36c1f804b5a9ac60650154ea95046a0f2a7241c68ba3  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/old-drawer-100.png
DATA c8c53864d6dd325f0ff5d4151ae3d79e849f9b206dd5bb17c79a0c4bccb3a9ae  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-100.png
DATA 6b7296b7e4613fca5c18bc66099dce27a24ea2ec4faad3b64bcb81bb082ffda6  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-300.png
DATA fa6e0aad5a3f7a927ab57b3ddb14fb5501c85685cf1090d4e55776f8381827d8  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-open.png
DATA 5885fdf7a509f577e21b5a318592c1ac3327778c4afa004d3e5824becdec50a0  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-restored.png
DATA 60aea246794323007d2d149bdbdd07df6f18fd897c362b87df6904ed5fa7410c  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-settings.png
DATA b384d1c88c5b1ee3f33eb863b238d32db660baf70dc09cacdc6c121db1f4ab88  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shrink-held.png
DATA 23048b7408a4d2855520da2efaffca1496620dd4929a13c4c56ff1f1bba1fe7f  docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shrink-overview.png
DATA 93d6c07d5adbc1c7c857add6bcdfe992679c6510255f0fcc63b5c7abd8ff0a13  docs/evidence/coherent-shell/integration-gate-2026-10-10/close-recovered.png
DATA 71222c20cc4cf43e2e19ba9f127d476943de54fdb361aac4f2f89ad35bb5d4b8  docs/evidence/coherent-shell/integration-gate-2026-10-10/live-held.png
DATA d2e7e5d51bd74b33c29558581a0a216f1a1d240b40a5216d8e0cf8ba01d686da  docs/evidence/coherent-shell/integration-gate-2026-10-10/private-one.png
DATA d2e7e5d51bd74b33c29558581a0a216f1a1d240b40a5216d8e0cf8ba01d686da  docs/evidence/coherent-shell/integration-gate-2026-10-10/private-two.png
DATA f864663e2718f63ede79240898af5aea1fb26a1ed90febebd73f0e4c70d1f23d  docs/evidence/coherent-shell/integration-gate-2026-10-10/public-one.png
DATA 2a13ea91fa102b75dee1b75bb8d6b9c068a68b8221c814373deedddec80af296  docs/evidence/coherent-shell/integration-gate-2026-10-10/public-two.png
DATA 1596eb39f0075c6e2dfa20f75c3e31513a3d937a2360a67be2dfebc6f34169ae  docs/evidence/coherent-shell/integration-gate-2026-10-10/unavailable.png
DATA 856747c4afd9f1a223a444dd1b76f1d6dc02e1ddfc9f45991cd00b175743d827  docs/evidence/coherent-shell/notification-history-motion-qemu/dismiss-after.png
DATA d791cade02dfde4cc02756193e080d52ac007b7e141a54aa531b1173e63dc289  docs/evidence/coherent-shell/notification-history-motion-qemu/initial.png
DATA 3a8d023504d8dc638c76a900081512cf36ddbaa2d7d334a6b7040e9cc61cb65e  docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-coasting-next.png
DATA 75052edc63e86795286dd26d45b195e3f75785da13ff10676bc405c6f2a6fe51  docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-coasting.png
DATA 5332e5896c24821965190c7d69974fab359ecd627674c5c4522a0b884d974da6  docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-stable.png
DATA c4d221cc28a7cfa31da38e818561449cc7cef2564c7ea7cc86ffa094f35164bc  docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-stop.mp4
DATA cb4d0b8a85f2511b3525bb5ff724eb65fcf6dc2bd31a73eca0f22c56a4965600  docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-held.png
DATA 0170c00341405479c590e2ded085f246f50e2090f77eb42fb5d79327675c07e2  docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-return-early.png
DATA 01252e5ea0c1c839cb8ec8143badb480636aa6e90b78ad8f17841e0022324672  docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-return.mp4
DATA d791cade02dfde4cc02756193e080d52ac007b7e141a54aa531b1173e63dc289  docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-vertical-cancel.png
DATA 125bc691f5c0c8f7e426a80b5989fb4b4b45d21d44d4e476e4e6a13c62ba6462  docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-vertical-held.png
DATA 7c0236199807eef7cb68e884233eb6e1f1560389e75685b01508f1d645c4cdbc  docs/evidence/coherent-shell/webos-polish-host/dark/drawer.png
DATA d0ae67a92ccfd2f06d3ff5c9a05f0ddb36378a99c2cb4d501745cbd4d3588d98  docs/evidence/coherent-shell/webos-polish-host/dark/preview.png
DATA d6c24fdd4179650139fa605737d1e29644954662dd7dd1767e59771f2cbf95c9  docs/evidence/coherent-shell/webos-polish-host/dark/settings.png
DATA 3dff33df910839c6557f58453fd75dcf0b7e348ddcd872d5611b155ce3d131fd  docs/evidence/coherent-shell/webos-polish-host/dark/shade.png
DATA ecd12bb4fa419db0c186dff401f8dcd0664a6adc71b1ac01537291a5bf5516d3  docs/evidence/coherent-shell/webos-polish-host/dark/themes.png
DATA 2ab25d61035dc47d48e37745bb4f767936f2aae35752fed285caad02a6a75756  docs/evidence/coherent-shell/webos-polish-host/latte/drawer.png
DATA 04064a159eebdce9c757511c53e3f5ec2ea4d063e5acfa0406d71b6234d2dc84  docs/evidence/coherent-shell/webos-polish-host/latte/preview.png
DATA 1012e2c71c16d01e2af568de7bc4ba903eaa8ab47893cbeb0d3fe77c1cfe8b60  docs/evidence/coherent-shell/webos-polish-host/latte/settings.png
DATA 7920b116374b6c36684c32205a882aecd21171f86c40ec314598261430fc2ab7  docs/evidence/coherent-shell/webos-polish-host/latte/shade.png
DATA 7c9d27d5a13b8f9e0547c8e8fa3a66c3d2f666e32a3b425108265f674bc0791b  docs/evidence/coherent-shell/webos-polish-host/latte/themes.png
DATA 04bf07fc0c9b60b28662303751331092b5638d66ba48c70a26a0736c280bc0d6  docs/evidence/coherent-shell/webos-polish-qemu/deck-home.png
DATA 83f065a0dd69f605b51dadf1da77d48c628579d009ea4cd54087b229ada62a40  docs/evidence/wifi-settings/webos-polish-qemu/wifi-auth-error-dark.png
DATA 05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d  docs/evidence/wifi-settings/webos-polish-qemu/wifi-forget-confirm-dark.png
DATA de1da296526f5f6feb4d44972fc3ccd88ce495be38265a788e0463031faae405  docs/evidence/wifi-settings/webos-polish-qemu/wifi-list-dark.png
DATA e683d14906b728e6a457af6ad47cb8821ab0d8af2f803234305bcd557a030de8  docs/evidence/wifi-settings/webos-polish-qemu/wifi-masked-dark.png
DATA 95e428aaa17f01fc274d0b31ca17d057ae318904d54c58b0f4553bb4377db18a  docs/evidence/wifi-settings/webos-polish-qemu/wifi-settings-dark.png
DATA ffe9f46b8af0617145cc5d61e1df064f82275791fe1ebf7a4765473ad5b434eb  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-auth-error-dark.png
DATA 05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-forget-confirm-dark.png
DATA 0fc088b091ad33e55ebeee9a9eedb735eb02a16614fd782befafa765833e4ded  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-forgotten-dark.png
DATA 178d4f30df386e01d30e6c4ac29f59462999b28a2b4baa32bfbf8061070767b7  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-keyboard-dark.png
DATA 7216d43e5b904f28f587193a69aca9710c5ed0df45b96db6a6a286e4b1798add  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-keyboard-gesture-disabled-dark.png
DATA 0e169a208a7c78e4cd5fb5926fa1edc8150ba711a7b15dfc7dad300820665395  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-list-dark.png
DATA e8955993f0bac62bfdab2337ccedf16d5cf3575da8d3ef134e896d82316bfda2  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-list-light.png
DATA 9bce2b1fe7e1dc3d8508b8ef17be44345d1fff70c819642055d22bf370683866  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-loading-dark.png
DATA 2e474fb8b208685dfd1aee5a7ab2e50d02fb5e633ad8ae2f8297c2e962b3dfba  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-masked-dark.png
DATA dd3782ac477ddfce563d062bdecdef87a5939ce815e2849a30d75c7e8a41b675  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-saved-entry.png
DATA 9ec5bd480721d3fcba238e5229e9f8c06d92612249612b570215651f9f651ec5  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-settings-dark.png
DATA c33fb0e35b6668a9ed563f128666aa2571554beffcede4a40801697ce5cb8be7  docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-settings-light.png
DATA e2c0ba874a9bb5dcf1032bdcf15a1cd1c4817f21232ff8e5acbfb47445f85a9b  docs/evidence/omarchy-themes/quattro-picker-parity/dark-catppuccin-background-selected.png
DATA 80749cf5e3d95f1637f8ed3fa428ee035a342ec4767c3667f4f353e9d322a574  docs/evidence/omarchy-themes/quattro-picker-parity/dark-catppuccin-preview.png
DATA dfee60f07b4940903ddd9f4ac2e6ed6efb29474db1b937e24d8f4a324b5e93ee  docs/evidence/omarchy-themes/quattro-picker-parity/light-catppuccin-latte-background-selected.png
DATA f488d4bf3cc0f454c05dc3413ef5c840ee9163ca91b54067b076cc5871190e2d  docs/evidence/omarchy-themes/quattro-picker-parity/light-catppuccin-latte-preview.png
DATA 237c63820485263b53806aee8c647dcc687c0c403db80a402bfedb4beb1c8d2b  docs/evidence/omarchy-themes/quattro-picker-parity/theme-list.png
DATA 5232da07c677d4ff8436db42bb6fe3294427ebf889d41b443cb244c545b0f9b5  docs/evidence/omarchy-themes/quattro-carousel/background-carousel-mid-drag.png
DATA 500d2dcbc667f32b522cbf66d504dc6fe5ab437ff004cc1cdb26ce34fd2d488f  docs/evidence/omarchy-themes/quattro-carousel/preview-dark.png
DATA ad0deabd0bda6c823da9f49112ad737e5f20c9392f03f1656c4ccf8c13cf11a9  docs/evidence/omarchy-themes/quattro-carousel/preview-light.png
DATA cd7bb9f6733a456be5dd8d5d0a0b2701b33e3182b5c322f8f4cd2b0489007d37  docs/evidence/omarchy-themes/quattro-carousel/swipe.mp4
DATA 050f538c1c0e8d443bffae5c7ae38ca2d962f5aaeb84365c44903623c1352490  docs/evidence/omarchy-themes/quattro-carousel/theme-carousel-mid-drag.png
DATA 827b909568a30991a3cf458295b8bf56c232b57908dbabd0b42eb14f26a86dfc  docs/evidence/omarchy-themes/quattro-carousel/theme-carousel-rest-dark.png
DATA a61bde5110afc2a8affad06c7cfdd78190e9b2759563646d71a80f8105a3fc13  docs/evidence/omarchy-themes/commit-fix-board/drawer-catppuccin.png
DATA bc925fa4c5725f3fc35f682feb9f64869a300a786df0548b62329bcef4a9a75d  docs/evidence/omarchy-themes/commit-fix-board/drawer-community.png
DATA 465ae2500f90aaf1656ca0dda867475968c6be0a16811b0c30c56d70d5983fd1  docs/evidence/omarchy-themes/chooser-responsive/screens/01-list-open.png
DATA 595bfaf33d24ea6714705f1f44656385a1461533ad72624f0d859c96e8f4e396  docs/evidence/omarchy-themes/chooser-responsive/screens/02-pressed-highlight.png
DATA b7f8b3fecc4c02339978264670f42919822754d30bff9835ecafb49edcfd8134  docs/evidence/omarchy-themes/chooser-responsive/screens/04-backgrounds-mid-decode.png
DATA 227ce511962a7b82e6732016e4e309c53af1e8edba8c29121dcab00e92edec90  docs/evidence/omarchy-themes/chooser-responsive/screens/07-background-selected-resolved.png
DATA 39e1d467340c2a0b25993e2625f172c6450de74947af924ddf6c7639741515ad docs/evidence/bare-app-cards/1-apps-dark.png
DATA acb886d6e28aebf11dae1a9e63747e4a0fffdd50619f527b9e78aabac7f3a3e9 docs/evidence/bare-app-cards/1-apps-light.png
DATA 36e88179571e102210cc5f8818153b64fd4ffdc88e108a560df74b21e765f6c9 docs/evidence/bare-app-cards/2-apps-dark.png
DATA 4ae990d98333d98547d0ea4bab6cb69c3baf7a450e53f883cddb10927bb9035e docs/evidence/bare-app-cards/2-apps-light.png
DATA 158c738d0c5a5586594ca66f302c9f608e58a61cfc0129aec6dcb096595ae852 docs/evidence/bare-app-cards/3-apps-dark.png
DATA 9ce5c5a1a99261edbfcbebffd5c62e63abb2f8ff70e7569f22f714e0088074fe docs/evidence/bare-app-cards/3-apps-light.png
DATA 6b3340162ca2f6193401c440bfe2d88992bab733f70145941c18ced0213a2818 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-000-00-baseline-one-focused.png
DATA 7f14fbed81d4e8b990f44b9b64737206a5deb77a3ef344fce8fe4e5365873ee2 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-002-02-motion-x420.png
DATA 5ebdbde6ff181ad86d78ef240b328737a3383c7b0aee9a25052b58b0f9b78f90 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-009-09-motion-x280.png
DATA 79581b7f7ef9107a4f428f08f0a7e39522507876ed457b15df2311047ad4cc37 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-015-15-motion-x160.png
DATA 10597fa96b5525fce30c17450ed602125dce37da517564c0df80a9c9826579c6 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-015-15-motion-x160-run2.png
DATA b01410da3d537d7867888487260117cbb6dc7cc5f3851c33e324767e5bfe980b docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-018-18-motion-x120.png
DATA 65bc647424da961ff94be4e73062035807df5f57ae4f727f0683a2e5e3c8d40d docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-019-90-up.png
DATA 3fa695d004f85751bff63bc5bb2ac4be847629997e06e75902b14cf8435588c1 docs/evidence/card-shell/app-switch-swipe-frame-capture/frame-025-96-settle.png
DATA 04b3e7b09e714e92b292e6fd7280de077fa7219f7b9a96610675da48381ee844 docs/evidence/home-screen/qemu/home-dark-after-restart.png
DATA 6bc49a1c8f55b302c36e19fa8c3e6114d64435e45eac8c28f698bec86e985245 docs/evidence/home-screen/qemu/home-dark-back-to-page1.png
DATA 99a601a1dded8325da3ce9d01a88f9e914ed40e527ca5ca6742d181abbb60b30 docs/evidence/home-screen/qemu/home-dark-badge-removed.png
DATA 3c6358d4b6a8bf6f6bc2fc6ab1c728aa4f3f693e245e0bbcc3e7507f4a95dfe4 docs/evidence/home-screen/qemu/home-dark-drawer.png
DATA 955d4295d8e6dcf08c9f64aaa7b04fcc07731db5741c6c02897e88f9f4052fb0 docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1232x568.png
DATA 555d78d07462a33db598cc5b87c97ebf3215997c7bfc38dd1243fd16fb691b1d docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1280x800.png
DATA ff0b9adbacf9a19192e1941f9e4b5311b93f4259e3976c40d6c24639d50e87ab docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1920x1080.png
DATA 9962b8045bfecbea7ff7f5bd93fa6ee49eaae7a43f55352359dc6c1f0dab0090 docs/evidence/home-screen/widget-picker-fit/host/widget-picker-568x1232.png
DATA ae87503b0e4edd6675c49e979b1d28d1eb44e964591546b0e23729bdd1a6b29e docs/evidence/home-screen/widget-picker-fit/board/before-widget-rows-past-the-card-1280x800-grim.png
DATA e037e9aa99953431e37c96db60382a1550c2363e9e0989976cdca1073d75a2e3 docs/evidence/home-screen/widget-picker-fit/board/after-weather-row-click-1280x800-grim.png
DATA b8986ee027cb26e13b15cec247018664869958698bd6c6f2ca300adfdcaf9360 docs/evidence/home-screen/widget-picker-fit/board/after-widgets-page-1280x800-grim.png
DATA 21c2a5a523ec831a47c10fc3416aab22597abbffb2954e316fc637d587a0433d docs/evidence/home-screen/qemu/home-dark-drop-target.png
DATA 64b1bc4899bb7e4ee4dd5af7a4adace1a2344ef4dd85e7e6cb3b9756468ec77f docs/evidence/home-screen/qemu/home-dark-mid-swipe.png
DATA 6bc49a1c8f55b302c36e19fa8c3e6114d64435e45eac8c28f698bec86e985245 docs/evidence/home-screen/qemu/home-dark-page1.png
DATA 76241d47b4c6465a9e158ad7d1af1857f9a28b8672a6c3a9acb781a671f5194b docs/evidence/home-screen/qemu/home-dark-page2.png
DATA 4697a2cfe9b753a6ff75ca019f3bb103b07eb85e10cefd7463b8d735b54380b9 docs/evidence/home-screen/qemu/home-dark-pin-flow.png
DATA 04b3e7b09e714e92b292e6fd7280de077fa7219f7b9a96610675da48381ee844 docs/evidence/home-screen/qemu/home-dark-rearrange-done.png
DATA fa078c53898c978cd6e1bb69b6ed4e625cf380c6450f2155c508f512d21b6255 docs/evidence/home-screen/qemu/home-dark-rearrange.png
DATA 507e156719fa35cfee8b57042169200c8536506afd0f54e1bb929392a07a085c docs/evidence/home-screen/qemu/home-dark-removed.png
DATA 41b79abfec2fcd510338e0fd4b2594b14be0291068dc136c3f4d3aeab9890409 docs/evidence/home-screen/qemu/home-dark-showcase.png
DATA beb49bd30f0c7cc5d980cce15606ca210126ac351e78e33112a2911cf5f019ab docs/evidence/home-screen/qemu/home-light-page1.png
DATA 935aa797d7a130d0a56f16217c158032d8454b1e77921f0b0d2ecffc11fb78ae docs/evidence/home-screen/qemu/home-light-page2.png
DATA d94eddebdfaee467f70c6a285014bd45c5dfb878f688ad0cda54fb581ad6ba91 docs/evidence/home-screen/qemu/home-light-showcase.png
DATA 420942042e5084921da630bc779963b29bfa4311c13745073572351a8f8a0a94 docs/evidence/card-shell/ordinary-resize-race-fix/before-frame-000-baseline.png
DATA a0d38fec44b51778592fc3b019ccdaabf2d013e865b1ed77d2b231096fe4a563 docs/evidence/card-shell/ordinary-resize-race-fix/before-frame-009-motion-x280.png
DATA 313dffeabb458ee2c5bc809de39d86f3f4190c46158f6531cecc7c4ce6d20b12 docs/evidence/card-shell/ordinary-resize-race-fix/before-frame-025-settle.png
DATA ee4ab6fcc41de1a785277120f9689053e56d953e30df4f2481e55f6527141df4 docs/evidence/card-shell/ordinary-resize-race-fix/after-frame-000-baseline.png
DATA cfaca5ad4ca5f68342ce533adfd0807ddf557d8ec118e039eafe0b077057a87f docs/evidence/card-shell/ordinary-resize-race-fix/after-frame-009-motion-x280.png
DATA 6a5e807f6511eadc8055ff9a4a92f6b417fc27335cc02f3d316a536139195556 docs/evidence/card-shell/ordinary-resize-race-fix/after-frame-025-settle.png
DATA 2d4f8420c1db9d1f40c9217ee3d4ba646270226f2525ea4eeb8918a3e3cb50a0  docs/evidence/card-shell/overview-home-bleed-through/after-overview-home-hidden.png
DATA a4d56bc27c4eba894cb36931c3030a018f1d0945414129a800295786787dd217  docs/evidence/card-shell/overview-home-bleed-through/before-app-focused.png
DATA a1a9df92965e1208b1f2bc1d3f1b20a7f1bc26d4f9d4322db2ec18ff47e618de  docs/evidence/card-shell/overview-home-bleed-through/before-overview-home-bleeds-through.png
DATA bfc76c3bdd2e5a8db51e19243912529761bf0c382c314e09b20573bc5800eb08  docs/evidence/card-shell/overview-home-bleed-through/entry-00-origin.png
DATA 6586a5ab19bf085c36f82d397939157b112e08380e2d16367b746c9b8d7b659d  docs/evidence/card-shell/overview-home-bleed-through/entry-01-touch-down.png
DATA 857caa9d6ea4de5d6ae24a55b67f5a71368ff178d7cce9f84f72f284e988109e  docs/evidence/card-shell/overview-home-bleed-through/entry-02-mid-drag.png
DATA 5824d7199bb74acd571aa8a0e7bbaa986f664e10fdbdcec5e9e91570f9db3a98  docs/evidence/card-shell/overview-home-bleed-through/entry-03-home-idle-reveal.png
DATA e25dd43c6c9aca1f1dc57ace48a2de2a682760c5d35c095cd2536603e4e6761d  docs/evidence/card-shell/app-switch-neighbour-render/after-full-neighbour.png
DATA 099a47af0e5726fe78af086c0dc9cbbad1b6f4a9c88b30bbdcba5e22f780c980  docs/evidence/card-shell/app-switch-neighbour-render/after-held-1.png
DATA 55e6ebda0e06d3ccd1ac7b61a94a59912d993b69a30ac1ab97e7685b203d69b1  docs/evidence/card-shell/app-switch-neighbour-render/after-held-2.png
DATA f338397d2cf535385ce1e57c85756685d8bdb4c62a0856d170be35aec0da312c  docs/evidence/card-shell/app-switch-neighbour-render/before-cropped-neighbour.png
DATA 3c2cf9367ad3ef90e23ac0e5c33deca77a5f848e789f3b98196567bec0e6afb6 docs/evidence/hdmi-plug-cma/board-hdmi-plug-3h41m-black-bg.png
DATA 028ac6897682a822685435215e03ad39bcb24bc2355e41c948fafc186be7485b docs/evidence/hdmi-plug-cma/board-hdmi-replug-after-fix.png
DATA dc1e82ff86948651d0d532605ed6598cbbcbc04c3e68af2310c803060c84e52c docs/evidence/hdmi-plug-cma/board-hdmi-swaybg-stopped.png
DATA c84f70ac6b2178a285fcc3629a9345310784a4b79ea20098941bf3c7d7b4ef02 docs/evidence/hdmi-shell-performance/scene/turn180-sampler-fallback/ordinary-a.png
DATA b37fda708291fac1c44a0559dcafc37fee0505b2f6bacad9f82d88e03a5d4b5d docs/evidence/hdmi-shell-performance/scene/turn180-sampler-fallback/ordinary-b.png
DATA 8c10dd5611d5b97754603642c6c3728fa3fa4bac939c51b8e75cbe093a046111 docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/ordinary-a.png
DATA ccb7b0f8f15cadc823028d2f79f36c62a6481fa2c36009d0a6f3ae98b7950c9b docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/ordinary-b.png
DATA 1f6a9dfc97ae02e42c44c6f4a4948155786cd4356d436493cf7cc474fb43c48b docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/overview-a.png
DATA 52067082bbf8cdd97ae1e8ca47fc85743a2cb43832de91770794472e3978a26c docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/overview-b.png
DATA 254f10b379df10bc966aeab93e5e307f67c8030d0024cfe041bfaaf687ed27dd docs/evidence/hdmi-shell-performance/scene/turn90-sampler/ordinary-a.png
DATA e48de1f101b121ada8008b5cd592d01e71d2bad46d7e8cba930543b3fc0f76c2 docs/evidence/hdmi-shell-performance/scene/turn90-sampler/ordinary-b.png
DATA fcb7183acd5da12e3be0d60d0d02a22f14406135f2657aad652e509785d7aed9 docs/evidence/hdmi-shell-performance/scene/turn90-sampler/overview-a.png
DATA 5c3fe4dce16a82b17356398f7b070ec26c5dd17cb305ddd21ede874aa6058715 docs/evidence/hdmi-shell-performance/scene/turn90-sampler/overview-b.png

DATA 570d15376898cb6e6af36ff5cb3e54d9f434759ee2fde467efc198810ab40233 docs/evidence/fahrenheit-weather/weather-fahrenheit.png
DATA 07e481cec9ea72eb520c2ecc09c154e216d835381d54ac71b883c5f8e1364328  docs/evidence/card-shell/app-switch-neighbour-render/before-held-1.png
DATA 1a517e2d67ae74efbc67de841187982617f3bff88b7202ee3a4dad08c14c3692  docs/evidence/card-shell/app-switch-neighbour-render/before-held-2.png
DATA e23a93dd46e8e71e426fe69a64ff62f5b25b6f21d6775569aaaf70d8416eb14b docs/evidence/card-shell/webos-fan-switcher/dark-01-overview.png
DATA e9341f94a3051baf344738aa799a3efa0bd57d05a9e2c561ba281a291534ad47 docs/evidence/card-shell/webos-fan-switcher/dark-02-scrolling.png
DATA 6a367dc02f42de09ea0cf165fc85dc4f703b69c5c065097aef95671656d1451d docs/evidence/card-shell/webos-fan-switcher/dark-03-scrolled-settled.png
DATA 1352d062a802eddc0a63e4ef98b8be97d13bcf7d9900cf3c379ec361bdd46b2c docs/evidence/card-shell/webos-fan-switcher/dark-04-after-close.png
DATA ae096fe35939059f99ba5e8d4823874f05a0c3747b7f1e998e90e37c69c8d5bb docs/evidence/card-shell/webos-fan-switcher/dark-05-opened.png
DATA fa623975a65f8159a5af65638e0b946be46fbd74e881a358e5b7fbf5c93d270d docs/evidence/card-shell/webos-fan-switcher/light-01-overview.png
DATA 49fa7cae06dd6527a3b3d93520cd9dec7f237d19ae3d915a6846c89fa0ad5507 docs/evidence/card-shell/webos-fan-switcher/light-02-scrolling.png
DATA b2093a6bba3df6b87f48da012dec01aaf350fafe2046489d41cc781b7f3663ec docs/evidence/card-shell/webos-fan-switcher/light-03-scrolled-settled.png
DATA 05afe2e3c70959c1c95ed4ce05b827f21ddd6a09290ad50a5aa2bdd4354a8118 docs/evidence/card-shell/webos-fan-switcher/light-04-after-close.png
DATA c62d2f6b3a7fd1c4f6439955443fb0517524fb1c28617325865e24c5a0242c1c docs/evidence/card-shell/webos-fan-switcher/light-05-opened.png
DATA a078dc50d948af4d6f87fb575a1f7ebefa25edfc39725ad8888b0a3311b810b1  docs/evidence/omarchy-themes/instant-theme-swap/tap-to-apply-host/themes-dark.png
DATA e1ceaff1e53e62ee75362838ed2cc644f76c452583e02b1f07053c69d134b92c  docs/evidence/omarchy-themes/instant-theme-swap/tap-to-apply-host/themes-latte.png
DATA 656e18b2eeb9bc304411d42cc656d366bd2e8947e7692536d3f1a36b2f8c7903  docs/evidence/card-shell/bottom-band-flicker/after-max-render-time.png
DATA 839c1f58897058e97e289553d97b636d8529743161aed19ef0f95326b1beea7a  docs/evidence/card-shell/bottom-band-flicker/before-max-render-time.png
DATA aaf18fc59dd1a5084642fbe5b699e3e8a0ed27aebbb95f138745fa90c81b7908  docs/evidence/card-shell/bottom-band-flicker/hdmi-dock-band-phone-frames.png
DATA f953614e47ffe4c6f174386ef1b3a5b2dc2a0aa2a9c793a1ff133b2c475ea5a2  docs/evidence/card-shell/shade-backdrop-fade/injected-mid-drag.png
DATA 9cad0390d86d67ce59d06acc430b99ee3aceee7f3592b5e31b814fe9ef664544  docs/evidence/card-shell/shade-backdrop-fade/injected-slow-drag-2fps.png
DATA c73761499696bd030d92b58e72a4640b749de53c6a187259879397a4b78ae8bb  docs/evidence/card-shell/shade-drag-to-close/injected-close-sequence-2fps.png
DATA 94ad4dec646c0d8c58da8733b829f16576adc8a34912061a7bf71ba7861f4fb9  docs/evidence/card-shell/video-card-gestures/contact-sheet.png
DATA 536397015eaaaadb79759c5abefe19f7d7c1ecbda9eeba2eecf1cf1d84f1e57c  docs/evidence/card-shell/video-card-gestures/contact-sheet-overview-freeze.png
DATA 76883f6aba9647b6ba1a955827e81ff32958b1098926284f53584f3b6c0b63ed  docs/evidence/card-shell/live-card-cost/contact-sheet.png
DATA cbc8370a74746d24a2467c4fe7dd31bf1fc9a14a28de4cfc169bc3ced7d18b9a  docs/evidence/card-shell/bottom-band-flicker/without-kernel-patch-injected-gestures.png
DATA e23a93dd46e8e71e426fe69a64ff62f5b25b6f21d6775569aaaf70d8416eb14b docs/evidence/card-shell/android-sized-cards/before-dark-01-overview.png
DATA 7ab76ddf535b9afa85a9352c171a04bc6ae0fa13dc1ba9bb30962e218fec32a8 docs/evidence/card-shell/android-sized-cards/after-dark-01-overview.png
DATA b05dd2e4b9ba2360c3acdde92be7038c434d2a434f1dc64d03a4bcdbdbb090c6 docs/evidence/card-shell/android-sized-cards/after-dark-02-scrolling.png
DATA 162ddaff23783952002db30d211bafd24dc9077f17b8ee6b66d7e01a29cb4f1b docs/evidence/card-shell/android-sized-cards/after-dark-03-scrolled-settled.png
DATA 6e7c57bf9caab91dbaf9ff787b461fb8092284f330d253b2be969ecfce203816 docs/evidence/card-shell/android-sized-cards/after-dark-04-after-close.png
DATA 448bf14c8ddb44dcd4759148eed0aa382c0a15faa5c871f62676d3850ef31e57 docs/evidence/card-shell/android-sized-cards/after-dark-05-opened.png
DATA 1203ce115fe26c2c265557a2cd5c682d95689cb10d34c77f62a975dd90edecce docs/evidence/card-shell/android-sized-cards/after-light-01-overview.png
DATA 252fc87612016dd2d35850f6998926262bf8e5bf9430c64f421410c3b9992b11 docs/evidence/card-shell/android-sized-cards/after-light-02-scrolling.png
DATA 929f38b6fc3e08f3e897a5ebe0ff300f7590d88ffaa0b449adfeeaff24bad795 docs/evidence/card-shell/android-sized-cards/after-light-03-scrolled-settled.png
DATA 534dce6734787e1dd7592602c1681d5f1dcc05dcb26f8fcb4e15e3d180a1bc37 docs/evidence/card-shell/android-sized-cards/after-light-04-after-close.png
DATA 3cb7e6ad7c8dea8b739bbd2505b4c0e847163fa8ff501aff6dbfc1376c13d748 docs/evidence/card-shell/android-sized-cards/after-light-05-opened.png
DATA 2852867146b0c9dadd66e505c6578d3894ec54d367b69b210cf7e59752495898  docs/evidence/launch-splash/qemu/deck.png
DATA 15e78201d27f66325e51d0626d6d0dc0b36b27afa7c4a8f0585b727f09935fea  docs/evidence/launch-splash/qemu/drawer-open.png
DATA 17dcca16238de352f6777129b43cb8f5133f7efd23ac511b3a6094313d0228ae  docs/evidence/launch-splash/qemu/splash.png
DATA 4c8619c892cc140a89422463a3f38bd17868ab6159cc9bfa1a28d523ecb7c221  docs/evidence/launch-splash/qemu/handoff.png
DATA 87b87775c91bf6a05a55dfc61851de34dacfd937cf085713d90a84fd110323bc docs/evidence/backlight/brightness-0.jpg
DATA b7d742a5b4043c995e39546e348bb8e57d00f7a7b6f6ab96deff25a42a800e22 docs/evidence/backlight/brightness-128.jpg
DATA 10e963c4961fd33c126f0b49b167aa732c9f050ae04ebadb3ec8d2b37f0629ac docs/evidence/backlight/brightness-255.jpg
DATA 3debac1206e0fc716715a440fa142478acf5f5bdbed195783f0eca7eddbac040 docs/evidence/card-shell/transparent-corners/board-trial/before.png
DATA 5bb123a3d8c76bbdda5b2e0a88c9848c9d20cd4814fb8090e9fd2e389ea2572e docs/evidence/card-shell/transparent-corners/board-trial/rounded.png
DATA 5bb123a3d8c76bbdda5b2e0a88c9848c9d20cd4814fb8090e9fd2e389ea2572e docs/evidence/card-shell/transparent-corners/installed-system/rounded.png
DATA 72c95b4f6bb012234a29c2443e4d566e19189271230f5185caa8e17bc606f89a  docs/evidence/home-screen/navigation/drawer.png
DATA 5b54afe2fa2681fe89d0c3486bf9704bd621bd4d5da156aa36b5ba9bff274b20  docs/evidence/home-screen/navigation/home.png
DATA a02ac5e799c080f640123979e7c31e853ab3328870edb803c9bd2c1b659538d4  docs/evidence/home-screen/navigation/overview.png
DATA d52107ed6f51f9434beea6012fbbd0248f366fceea6d9bf38c71f7c46481c50c  docs/evidence/home-screen/navigation/restored-terminal.png
DATA 2349e999dcaf4284a54910bcff8809b7e6aefe51dfad6bae95d0f1fe4f0896ec docs/evidence/brightness-slider/settings-after-drag-90pct.png
DATA 2e2c4a9fcc2110d03fabac3f926171a656259026fa9d03dae8ab88e298e9af3c docs/evidence/brightness-slider/settings-mid-drag-54pct.png
DATA 76383912cbc1241d553b2c6a122f71e1228fd54e0ba3b448f2dd49bc4cfa7d1c docs/evidence/brightness-slider/shade-after-drag-90pct-still-open.png
DATA e9fe967ebc8e42204ee39fd5f7fa1feec9048f78ae632de014097a066cb62157 docs/evidence/brightness-slider/shade-synced-45pct.png
DATA 862c1e59404b041f72425d885943e82ac0d4942f204b2a98566894b8822a66be docs/evidence/power-key/host/power-sheet-host.png
DATA b0dbc0c909cb821e30f098c298649a599e5883800e54ee9d5f556b785551f7be docs/evidence/power-key/sheet/after-cancel-grim.png
DATA 35fc6ab0fcc71b3e5ea8bcb973a2b673eb7170f05218f1fe26b0e1e00eb88960 docs/evidence/power-key/sheet/restart-confirmation-grim.png
DATA 2ec7df41782948f46baf959c568e4a64fb8e658c8e66e47cc3abb8ab9b7858dc docs/evidence/power-key/sheet/sheet-open-grim.png
DATA d498a3f28e3b2ddf552e261f73ec823fc24eb33b0bae68e0a02a42c0174623cf docs/evidence/power-key/sheet/revised-restart-confirmation-grim.png
DATA 9d1ffe6cd11029eec3dc103a72a93d1c661362ed45127db426e94fe78a428b9d docs/evidence/volume/shade-both-sliders.png
DATA 6afe4816bc6a66f409c5d70bff41ed94eb33d1034ebb93f05db303923632826a docs/evidence/volume/hud-collapsed.png
DATA 1db2d849128d5574ea833cad147a4f75bcf3868ed3132fb7ed6b0a5b21a65401 docs/evidence/volume/hud-expanded.png
DATA 04b3e7b09e714e92b292e6fd7280de077fa7219f7b9a96610675da48381ee844 docs/evidence/home-widgets-folders/home-dark-after-restart.png
DATA 6bc49a1c8f55b302c36e19fa8c3e6114d64435e45eac8c28f698bec86e985245 docs/evidence/home-widgets-folders/home-dark-back-to-page1.png
DATA 99a601a1dded8325da3ce9d01a88f9e914ed40e527ca5ca6742d181abbb60b30 docs/evidence/home-widgets-folders/home-dark-badge-removed.png
DATA a0dee5ffeabaaf70874ab28a8cc0c9b86e724cbe942f494e810c538e0ac54b4d docs/evidence/home-widgets-folders/home-dark-drawer.png
DATA 21c2a5a523ec831a47c10fc3416aab22597abbffb2954e316fc637d587a0433d docs/evidence/home-widgets-folders/home-dark-drop-target.png
DATA 46823848726efc3212d9a1c998aa747304bd1ee38cc52055f257f470318caeba docs/evidence/home-widgets-folders/home-dark-folder-created.png
DATA 102592293e2878f74e145debbc064b303097207174a04036fd4158ae85b50b5f docs/evidence/home-widgets-folders/home-dark-folder-mid-drag.png
DATA ca16460ae30929b4705133a496b75905e6182b9fdc1deb561ee5f7453e737fce docs/evidence/home-widgets-folders/home-dark-folder-open.png
DATA b30265ae56ec5bd37df0073832546dd420327777ea254c0022c3fb822ee035df docs/evidence/home-widgets-folders/home-dark-mid-drag.png
DATA 64b1bc4899bb7e4ee4dd5af7a4adace1a2344ef4dd85e7e6cb3b9756468ec77f docs/evidence/home-widgets-folders/home-dark-mid-swipe.png
DATA 6bc49a1c8f55b302c36e19fa8c3e6114d64435e45eac8c28f698bec86e985245 docs/evidence/home-widgets-folders/home-dark-page1.png
DATA 76241d47b4c6465a9e158ad7d1af1857f9a28b8672a6c3a9acb781a671f5194b docs/evidence/home-widgets-folders/home-dark-page2.png
DATA 4697a2cfe9b753a6ff75ca019f3bb103b07eb85e10cefd7463b8d735b54380b9 docs/evidence/home-widgets-folders/home-dark-pin-flow.png
DATA 04b3e7b09e714e92b292e6fd7280de077fa7219f7b9a96610675da48381ee844 docs/evidence/home-widgets-folders/home-dark-rearrange-done.png
DATA fa078c53898c978cd6e1bb69b6ed4e625cf380c6450f2155c508f512d21b6255 docs/evidence/home-widgets-folders/home-dark-rearrange.png
DATA 507e156719fa35cfee8b57042169200c8536506afd0f54e1bb929392a07a085c docs/evidence/home-widgets-folders/home-dark-removed.png
DATA 693b0de82051da47e505b2cd987b16ee551265bc6171fb55a73e0826812e377f docs/evidence/home-widget-design/dark-battery-absent.png
DATA be4bb9f3177e475782a1570d1978cbe59e5f9bc6ea68a6d7689eb78c130d4dd3 docs/evidence/home-widget-design/dark-battery-present.png
DATA 1398af67e82fddbb1237622ceec17a1fad39e78ecee7594446d2cd9b05d0d152 docs/evidence/home-widget-design/dark-clock-analog.png
DATA 2a827346e51964ed56484b701bd720287f3db5f10f773845bac25c0939faa5a8 docs/evidence/home-widget-design/dark-clock-bubble.png
DATA 7b9aac0da67ffd94d4341c930ed26032fa882cb3be44065f0229bc8bc5d4c125 docs/evidence/home-widget-design/dark-clock-dotmatrix.png
DATA 924a309fa318f37dd57d80beec57c09b4bb30568370c47b08fecf5adc97551c2 docs/evidence/home-widget-design/dark-clock-thin.png
DATA 4981926068b22c68ee61c61b11e13be7589c243086b5c83b3830e0d05840d574 docs/evidence/home-widget-design/dark-drag-edge-indicator.png
DATA b3b4a5cb991f4aeb1175625c52b7acff6df77c39a81a1d080baa33b1029910b3 docs/evidence/home-widget-design/dark-drag-no-room.png
DATA e23ba26c6ea31d98907fa9777862d538630b69072a6c22dc7ce93c1f65d891fd docs/evidence/home-widget-design/dark-overview.png
DATA 1e98894b8b078dcb74b6bbde47e0065c8389faf52f8be6e1a93ffe25e82773f3 docs/evidence/home-widget-design/dark-weather.png
DATA 2d64b6efc8a868f958df8ef7adab930ecb5f6a6c8cf2bc4423985021b3ffa172 docs/evidence/home-widget-design/dark-widget-picker.png
DATA 400f8cbcca06a5a2224205a5d071fbaa2d4c47277c6e838a34d84e910d84b008 docs/evidence/home-widget-design/light-battery-absent.png
DATA c315804f242a56ba94b303010fffdba6ad44b27140d008725aad444414ed2107 docs/evidence/home-widget-design/light-battery-present.png
DATA 03c49c1b67ab215b4ea175ff600c7598a52bda59f0b004a81e3d3c13d0cf909c docs/evidence/home-widget-design/light-clock-analog.png
DATA 2f7f323fd3a809fe0db577b2d831d9a5d2c1099a8c743970967d880384f8fdb3 docs/evidence/home-widget-design/light-clock-bubble.png
DATA 8eb5077bd38fe42a124a5f498a6a23ef689e4f5918f2148b851c046479ef4e30 docs/evidence/home-widget-design/light-clock-dotmatrix.png
DATA 44315e00614738c83c9854879a5177ce8625e94f2aed87bf43e19a7e6f223679 docs/evidence/home-widget-design/light-clock-thin.png
DATA 7480e53a2d166f6046ba735d5a47ee9fbbe9bf274054de367df87a8fd3abc747 docs/evidence/home-widget-design/light-overview.png
DATA 78843e3a5835a341a2fb9801fc3c367b9e74ff8ff56be3b10c6757950a44f847 docs/evidence/home-widget-design/light-weather.png
DATA 9b6f45195710d80e950dc8659a43e879cfe0b1ace4b0d579e0f5cb14a38caf03 docs/evidence/home-widget-design/light-widget-picker.png
DATA 1edb7ac0fc9bd85bb2853bfb4013bf082e7a52ed29c47fae473972971a7445ff docs/evidence/files-app/host/portfolio-dark.png
DATA 373198612a7a7ae65d933697b400d952c5982415e4fce232c827a57bff3cae8f docs/evidence/files-app/host/portfolio-light.png
DATA 6219142f5fed441b5021980b3c0f8383228f1417010bf8f9922ea936572a9b68 docs/evidence/files-app/host/nautilus-dark.png
DATA b5c553f6b0d419371460c005b7aaaff96ffce504794591f336e113fb3f688b5e docs/evidence/files-app/host/nautilus-light.png
DATA group:20-files docs/evidence/shell-polish/{before,after}/*.png matched production host paints with real pinned dark/light appearances, synthetic services, and no board claim
DATA group:2-files docs/evidence/theme-picker/row-repaint/pair/*.png native scale-0.6 board captures after injected-input timing; not real-finger acceptance
DATA group:16-files docs/evidence/shell-responsive/*.png host renders (render_responsive_evidence example) of Home/Drawer/Settings/wallpaper at 568x1232, 768x1024, 1080x1920 and 1920x1080 for the-shell-adapts-to-output-resolution
DATA group:24-files docs/evidence/drawer-search/host/*.png host renders (render_drawer_search_evidence example) of the drawer search results at 1232x568 and 568x1232, 100% and 200%, from a fixture catalog for the-drawer-search-finds-settings-and-app-actions
DATA group:40-files docs/evidence/panel-landscape/**/*.{png,jpg} landscape panel: host renders (Wi-Fi pages, theme chooser, open folder, shade with notifications), native board captures (CLI-opened and injected-touch, trial and installed image), one bench camera frame; not real-finger acceptance

DATA 3972517849acf787538122127db17d5a4875a82a53cdba427ee25d5d16629af4 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/pointer-drawer.jpg
DATA 94c4c7ee5068f9a2eadc959ca4c4110eef3b6c64960b990f8768e05487708322 docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/pointer-calculator.jpg
DATA 3296929bf7f69cd70bc404d8b881486928b4bad42dc59546875d5c40c1c35e4a docs/evidence/the-shell-is-navigable-with-a-mouse/before-overview.jpg
DATA 2c27ebb72c882065eb21e2c79e3a3d9b844bb29f00b319d81459f70094380f17 docs/evidence/the-shell-is-navigable-with-a-mouse/after-overview.jpg
DATA 29ec4e126cd46e052ebf1247d248fc795b135299e3912116e3d2535588dcc00a docs/evidence/the-shell-is-navigable-with-a-mouse/after-drawer.jpg
DATA 1e872a35ff03d6ad526fe06fe990f583c9ab240519e53b1b02e8d8e7ca238797 docs/evidence/the-shell-is-navigable-with-a-mouse/after-themes.jpg
DATA b828078184dd6dca6e529a1b06025c3305fea75b483ddfc30044e5c9d3d8ac18 docs/evidence/the-shell-is-navigable-with-a-mouse/after-calculator-click.jpg
DATA 64da29b4e8a6d62346bab76b1c9424bf10abf0a5809f1a49f9524cccbaa2df4f docs/evidence/card-shell/overview-home-bleed-through/board-2026-09-30/overview-native.jpg
DATA a76ca87ac3d0823659559f297258be51f2719e8d95efbcb10186a3f68f17040a docs/evidence/card-shell/overview-home-bleed-through/board-2026-09-30/overview-panel.jpg
DATA 10397318a531c607f6291ba17ea983bc7b0d32f27ad5e07d964dc269d236b505 docs/evidence/clock-restyle/board-panel-100-home.png
DATA 34b645eed7ca5d4eda9062d1f56db2c689ed07b3e084097a28ecaf39e376fd05 docs/evidence/clock-restyle/board-panel-160-home.png
DATA 1922e250fcd30619bd99cd9c3a3aaa55ca4e4b66f011a335268d1fcf277d47e9 docs/evidence/clock-restyle/board-panel-200-home.png
DATA 4fa62684019d7645bdd6a432367b0e24ad791e113db75fd3da0ebd1b70639c1c docs/evidence/clock-restyle/host-100-before-after.png
DATA ee2ee568349d2934b8b8c6950b9278d9b0f41203f6b71ced033796e4bcbc8974 docs/evidence/clock-restyle/host-130-before-after.png
DATA a030cb1e75d983468dc23384351c0c4c411dac03ff5db25022e8f62bf3cf37c2 docs/evidence/clock-restyle/host-160-before-after.png
DATA e590ff3c14c7c08eeba6acc7ec745eb5f63e4e0b0ad46a88ecdad3d0903069ad docs/evidence/clock-restyle/host-200-before-after.png
DATA 9e258d5a07a483381d428302c67f39a9d8a799d94461e51d1ea4a86604f27f22 docs/evidence/clock-restyle/host-200-high-before-after.png
DATA 928965287512f34e9111f2428f00d97aed21ba3668557aed880f1d87cf336439 docs/evidence/clock-restyle/host-latte.png
DATA 8e3fc56d90f9fb9b02d709dec1384e37a0b07dc2c6574334f2f3bcb80f0b5db8 docs/evidence/clock-restyle/host-portrait-steps.png
DATA c8862c1934628c68c99651f932dc05a6078b6a9e1504ef8d2b5df9de63e1e177 docs/evidence/clock-restyle/host-retro82-wallpaper.png
DATA 65816b008ae9ef83de1cf0554ce401b813e1652890a3c62f80fafdff3488f154 docs/evidence/clock-restyle/board-theme-change-catppuccin.png
DATA d57e58fa7477047188e3b5ae243dd40830ceaf2ab0baf2ada6a9c81d09567041 docs/evidence/clock-restyle/board-theme-change-retro-back.png
DATA 1f89ef9f8642bb3962d9ebc4324e5c4585e3504a8f82388112d8bb88efdcbbe5 docs/evidence/clock-restyle/board-theme-change-retro.png
DATA eb97830d3b2c407b8a1a9559f4547c5faf30a528c36085c065ede0d2971e5eb6 docs/evidence/coherent-shell/accessibility-scale/board/01-settings.png
DATA 067bdb088d7d3b137a2586058819ab40830bef98aab4bf2daca440413794e7a6 docs/evidence/coherent-shell/accessibility-scale/board/02-vision-default.png
DATA 1052f94fa56517b0116ce10500455c31e71e37504080bdea57fe91a6eff8d4f1 docs/evidence/coherent-shell/accessibility-scale/board/03-large.png
DATA cff3cb07a0352355135064f7bf06cab6bce6205543e5a887a463009c5d256634 docs/evidence/coherent-shell/accessibility-scale/board/04-both.png
DATA 8561484aa92a536a8f8e77b2af098c6e7652ce0d208ab757b0e4e3636825435b docs/evidence/coherent-shell/accessibility-scale/board/05-both-settings.png
DATA cc1ff616181a6d33ad9c18698d485ef00d7cdd4eed46753110efcb254866ee76 docs/evidence/coherent-shell/accessibility-scale/board/06-reboot-shade.png
DATA 8f4271009116c7434853a184bd2abed64268f5c1f906004a1d49a56a1237876e docs/evidence/coherent-shell/accessibility-scale/board/07-reboot-vision.png
DATA a78135472bc20453af4e66d04d2f763213c9af1957e9d77cf8537cba28d5d2e9 docs/evidence/coherent-shell/accessibility-scale/board/08-restored.png
DATA de500f127e58fc24ef83bd2edfe1900261d6a860bb783220edebebe3f5d44b78 docs/evidence/coherent-shell/accessibility-scale/board/09-panel-home-ring-overflow.png
DATA aa00afa77299964895e68c6109bc7a25e917f0ef1b570620adbe0b36710bc9dc docs/evidence/coherent-shell/accessibility-scale/board/10-panel-shade.png
DATA ad27f354a55b2b54eded7af38c6789f81a1a4f63e875f01ee94346e610070ed1 docs/evidence/coherent-shell/accessibility-scale/board/11-panel-drawer.png
DATA 791fcff532c7c076224578d631b6587bbe1450ef8be4c3a129863d27fcedd180 docs/evidence/coherent-shell/accessibility-scale/board/12-panel-home-ring-fitted.png
DATA 1c57ab07f2058492b26073f4e2834ec15378cf9fb3e1438e93d7d4cf5858c0de docs/evidence/coherent-shell/accessibility-scale/board/13-panel-200-home-before-widget-fix.png
DATA 59d901943da9ae4b13f66046e22040ad3468464a95cce481ed3023fca6fd5cc5 docs/evidence/coherent-shell/accessibility-scale/board/14-panel-200-home.png
DATA e5e9fead973ff511aa531fff97dc634d474ab1146e195a40a52bc27f68549112 docs/evidence/coherent-shell/accessibility-scale/board/15-panel-200-drawer.png
DATA dabdc3a817ab2e5cf7f92f0a20af8d014e2e9b3a785a74f98ccc8d58acd7db04 docs/evidence/coherent-shell/accessibility-scale/board/16-panel-200-shade.png
DATA 9dc943b483576575d6c0246858994d4538c2f00c300b62f284d07f09821bccd7 docs/evidence/coherent-shell/accessibility-scale/board/17-panel-200-settings.png
DATA 081748268574b23d1a2c566e0b1e90adc7795179eb7d7241d982307f718a1683 docs/evidence/coherent-shell/accessibility-scale/board/18-panel-200-vision.png
DATA 0e296b6de50c1d1f35094a9ee3065c3aa00719aa2e4d5592ea6bc7d90589cd60 docs/evidence/coherent-shell/accessibility-scale/board/19-panel-160-home.png
DATA 304ff44b7577876d4cb7027fca17dd8a55830c257d9cee75c803effcc004e3f7 docs/evidence/coherent-shell/accessibility-scale/board/20-panel-160-drawer.png
DATA 32ef2f1a1a209da25bc7d0cdc760dfd0832e4b852158442e439a88b689bbda75 docs/evidence/coherent-shell/accessibility-scale/board/21-panel-160-shade.png
DATA 8b2170d72776931c93e7962d6c74775fff6a75b13f9441bf979eed5c1cb32e39 docs/evidence/coherent-shell/accessibility-scale/board/22-panel-160-settings.png
DATA df892e6f7500c072368526e0ce3803f1763064bc6e01d680dbdcfab5bf7c0502 docs/evidence/coherent-shell/accessibility-scale/board/23-panel-160-vision.png
DATA bb12d1dff29516d0ccdda0d6dc101d4c1ea689c16e8bff8196a17601d71c63dc docs/evidence/coherent-shell/accessibility-scale/host/default-drawer-568x1232.png
DATA 9ff798c8d1dbd81ec456a4e4dc7b2a60b868068372520fbd17b7c17c677a6099 docs/evidence/coherent-shell/accessibility-scale/host/default-settings-1280x800.png
DATA aec4b6cd890a30a32fdb64d8198b5ea0ba768ca332e2409855c72ffaefbe0219 docs/evidence/coherent-shell/accessibility-scale/host/default-shade-568x1232.png
DATA eb0966f9e06fb2fd729e399a95be0dc88b3bbde15b3c64ae3c9a6e9ef3aa6216 docs/evidence/coherent-shell/accessibility-scale/host/default-vision-1280x800.png
DATA 1c9722b94ae0ceb7794a06261355753f47fcf5af839c9ff50eb7cc03fb366747 docs/evidence/coherent-shell/accessibility-scale/host/high-drawer-568x1232.png
DATA d59baab1b86d73dc76ee757b6b2e1a736192b30dc712cee7a69708199ad08b4e docs/evidence/coherent-shell/accessibility-scale/host/high-settings-1280x800.png
DATA f7d7e549d62de45b1b966f6dfb6e37018eafc19f3a2beca5aab06ac99daa4b59 docs/evidence/coherent-shell/accessibility-scale/host/high-shade-568x1232.png
DATA 20799378b0b226aa7d6e7c4b86b017b4bddbfb2bfec6fee8a77d439df21b2f85 docs/evidence/coherent-shell/accessibility-scale/host/high-vision-1280x800.png
DATA cecaba3362fcf98c497ba5003e6d9b06567300c382f392588f64c48b5c44eb2f docs/evidence/coherent-shell/accessibility-scale/host/large-drawer-568x1232.png
DATA 8c12a940d3d9f450e6242a11b351c7f67b4562851035d6f97781a3f85be17854 docs/evidence/coherent-shell/accessibility-scale/host/large-settings-1280x800.png
DATA 7a80080d9cc38fa489186c9cf36c783b260053bfae53d386608db32ca76b67b2 docs/evidence/coherent-shell/accessibility-scale/host/large-shade-568x1232.png
DATA f9aa254f793aea91f9d252f9b7eca5ac74e55b2398b7dfb500d22c598f536f27 docs/evidence/coherent-shell/accessibility-scale/host/large-vision-1280x800.png
DATA b57527ed8b935caa251d4a3c3d03415d2e2d3cb93ebbce4a5b1d2c428eb47080 docs/evidence/coherent-shell/accessibility-scale/steps/drawer-landscape.png
DATA 41d8d67c9106929727b05681ef330e9714424d6c889e29265416ad7745521f57 docs/evidence/coherent-shell/accessibility-scale/steps/drawer-portrait.png
DATA ec16c90d82f9148aa3149b9a9a3373763ef6ad2d2e88dcf2a6d90654add5e027 docs/evidence/coherent-shell/accessibility-scale/steps/settings-landscape.png
DATA 074a5e48c842ac24a4451bbc8dc593bd55bd1618c239c5388913dd8259d6c3d8 docs/evidence/coherent-shell/accessibility-scale/steps/settings-portrait.png
DATA fc002a81567f1145d64fd114b4a4ea51688f9a5aaacbf2985c8e31985953a29a docs/evidence/coherent-shell/accessibility-scale/steps/shade-landscape.png
DATA 552fd356cd0127033d99cf14d0c39ed47193592aaae4881a836059a5189b46db docs/evidence/coherent-shell/accessibility-scale/steps/shade-portrait.png
DATA cdfa8107560a13eef7f41cf821f258cd14ba4e7a5e3eab3f8b8ac8a66e97caef docs/evidence/coherent-shell/accessibility-scale/steps/vision-landscape.png
DATA f389d7bff4f2709452e977f790ab05dd75ca34d4687ddb0e7abbcf4e0408c508 docs/evidence/coherent-shell/accessibility-scale/steps/vision-portrait.png
DATA ab692d4cf10500b1f737e07eedaa293c4019a690f6eaefddd3403187c81e9efd docs/evidence/coherent-shell/shade-quick-toggles/board/1-shade-open-1280x800.png
DATA 607b5d2fa0da79866348880d213226bfa14bc8a7fb67167ef70a585a5aa1e77d docs/evidence/coherent-shell/shade-quick-toggles/board/2-kbd-on-1280x800.png
DATA 00a780185adb986b07179cadca333d913ae74e17bac542dc3afffa174cdd4a1c docs/evidence/coherent-shell/shade-quick-toggles/board/3-kbd-off-1280x800.png
DATA 5dfd00e95b0a2caa969b26e0c9122d43078ec45a17aff770330c0e00531c6920 docs/evidence/coherent-shell/shade-quick-toggles/board/4-kbd-unavail-1280x800.png
DATA dbd0c23161743e4fa646959d59e735417504bf8467e50aae56038ed595847ba6 docs/evidence/coherent-shell/shade-quick-toggles/board/5-kbd-unavail-tapped-1280x800.png
DATA f09c700423f41faa8ad3ad498bc8eca54ae42c5b44f8f0e45fa8c33e9bfcfaf1 docs/evidence/coherent-shell/shade-quick-toggles/host/shade-0-keyboard-available-568x1232.png
DATA d7b177631a6cd72159e9f2496f5ba15cb1dc96a4dbd00cd87c185fce22c811c0 docs/evidence/coherent-shell/shade-quick-toggles/host/shade-0-keyboard-unavailable-1232x568.png
DATA 077089feb942b867b69e5b70f6701b0bee46ddbee07005d27fad8df49c32ccad docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-1232x568.png
DATA f6ed9b1cabf3b12a43d6be2f834e7b3706cc25f9bc11f1608fe231dbca6da57e docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-1280x800.png
DATA 0795a42e09634432b9b5ce3b612f0a705a69283a45c9c81a3493ce5d07e9dfc3 docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-568x1232.png
DATA 2b7f1d9461d73fe5bef505bba781a69a26b01d933188282340df0fceae44b06a docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-unavailable-568x1232.png
DATA a923f91bc32054b92985b36ac490cc876a587938193b3ee31664d8e98fa0fdb5 docs/evidence/coherent-shell/side-edge-back/1-shade-open-1280x720.png
DATA 304ff44b7577876d4cb7027fca17dd8a55830c257d9cee75c803effcc004e3f7 docs/evidence/coherent-shell/side-edge-back/10-panel-drawer-open-1232x568.png
DATA d54b1413153069e85bf3a66260c3b506cf0ce484d2f9bf1ba079d8b31909a13c docs/evidence/coherent-shell/side-edge-back/11-panel-long-press-menu-1232x568.png
DATA 316eaadd642c70f771db6fac8f98fe386daf63dd7fe1307fe0dc2a858abd15f2 docs/evidence/coherent-shell/side-edge-back/12-panel-side-back-closes-menu-drawer-stays-1232x568.png
DATA bccb1b73882504d6f50ff58326dee2ff26bd0d5138180e721a0a4325609d43c0 docs/evidence/coherent-shell/side-edge-back/13-panel-side-back-closes-drawer-1232x568.png
DATA 2d181a2927d4edbdf3a2ea92c87f049fb307940b4d5ebeb4c76a26d53e62869d docs/evidence/coherent-shell/side-edge-back/2-after-left-side-back-1280x720.png
DATA 82d010631988c5b7e6ddf21c414f01bfed772d95b7cb30dfc8b79be32ca06f17 docs/evidence/coherent-shell/side-edge-back/3-keyboard-shown-swipe-not-claimed-1280x720.png
DATA 90159f4d0e109d3bcea7e43475192eb2a70d5c5f3f97ab000210753c9b23ef6f docs/evidence/coherent-shell/side-edge-back/4-panel-keyboard-shown-1232x568.png
DATA 3f1c2a9d463503c376fa0b6745719017f5c33883a2f950dbdebef61a686cb2c6 docs/evidence/coherent-shell/side-edge-back/5-panel-keyboard-top-pull-opens-shade-1232x568.png
DATA 90159f4d0e109d3bcea7e43475192eb2a70d5c5f3f97ab000210753c9b23ef6f docs/evidence/coherent-shell/side-edge-back/6-panel-side-back-closes-shade-keyboard-stays-1232x568.png
DATA 94c9f0e9c72180df1285874d58e1e8a078b52db25d77a4fb69e2d813621265b8 docs/evidence/coherent-shell/side-edge-back/7-panel-side-back-dismisses-keyboard-1232x568.png
DATA 05c42a66e1b7e442162994f261e40d0a19cb8f0ba2ba48b149680869c7bdb903 docs/evidence/coherent-shell/side-edge-back/8-panel-settings-1232x568.png
DATA 5c8a10703c36ec7fe5be5eeb103f943ab5c778e38b2149179124e24baa652609 docs/evidence/coherent-shell/side-edge-back/9-panel-settings-side-back-1232x568.png
DATA a5002406911c3ae20a410d989c6e1ad0a31e46f32062eaec14414873e46d37d2 docs/evidence/hdmi-hotplug/panel-recovery-2026-09-30/native-panel.jpg
DATA f2ac6301f82eba7310bbe777bd01d05562a8a3eed7a567e5ebae8bdc53f53121 docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/files-before.jpg
DATA c9c05b81fb3d12e81f2b5f61135846d7779f4246d1fbda106e2ed5653cc165f5 docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/files-header-menu.jpg
DATA 032b3a6635590f6a8e8bc2b976b5afe89a1bc3c7a03648a6cee50a7f21b29062 docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/home-handle-overview.jpg
DATA c0f4155dee9e0a9f65f2db9aa231e9d8e481563d5ff3ff1f0ba46466081d59f0 docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/search-backspace.jpg
DATA 0e4ea4bbd724e66ca03867a762bc00b24f67c3504dfe9f6703719401edae85d0 docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/search-q.jpg
DATA 602664b30c1ad73b92262f18eeb04dfbe8a4feb722f4e5ff616f75ebe1ea3349 docs/evidence/type-roles/board-hdmi-100.png
DATA 8ef18c9fab70530c8a3a2f70229a2bfe0ed2327668fb29d94f5b50643ca4c3a9 docs/evidence/type-roles/board-hdmi-160.png
DATA 240e7ed0d3c042b68eb33b4eacf9eb2116dbb664fc98b66825177c3903c193ac docs/evidence/type-roles/board-hdmi-200.png
DATA 1afbe66898b6e3e1d236a3d4d9aa10021e3c40ffeb4ebcc11dda7e540e7c3e1e docs/evidence/type-roles/host-settings-landscape-steps.png
DATA fee1891f2f96bd4e4291c8e32d675cfb5ff1e61591679489d61188d537be3800 docs/evidence/type-roles/host-settings-portrait-steps.png
DATA 6537a53dbe93d30db9eb3f196c4b0402a823de793f9495703e3a006ecd090193 docs/evidence/type-roles/host-shade-landscape-steps.png
DATA 91219b4a683ef259842b3a97054c3f5fea5d1f038ba8b0afc3c349c42abc93f6 docs/evidence/type-roles/host-shade-portrait-steps.png
DATA ae5a5b24de9f4ac3fa96d6ad528df09ad30eb4975e70abb87fa5c744423c6020 docs/evidence/type-roles/host-vision-landscape-steps.png
DATA b9d91f77f6185d650801e5f003338c68ccebdca3d481f88a80e734bcb527d8b8 docs/evidence/type-roles/host-vision-portrait-steps.png
DATA bbdbcdff21dbf352505f6ec56ab00748083cc520c875b22a8996f954e50c3786 docs/evidence/files-app/board-2026-09-30/portfolio.jpg
DATA d96761dea749db42ce7df9f015c216ad7d7ef85be4ef209fe6060b5ecac84864 docs/evidence/files-app/board-2026-09-30/nautilus.jpg
DATA b702b254e1625c060c50c3a9feea34ade7821b0602d707868b8a1cb68d3bc2f5 docs/evidence/files-app/board-2026-09-30/nautilus-panel.jpg
DATA a7968af7e10d550affd1bddf59ec069c069caf2516af16a7003b224b37b279a3 docs/evidence/app-drawer/system-keyboard-qemu/app-focus-restored.png
DATA 511b39b65e5210df3036f6f98c2e472acf293d0b75ced63150d2548ecba4ed0a docs/evidence/app-drawer/system-keyboard-qemu/search-corrected.png
DATA 1d76f9906d40788df8f1d39ec9d731212e21b8d0883ed6ef9b04cf7583294152 docs/evidence/app-drawer/system-keyboard-qemu/search-focused.png
DATA a42873650f6c21bc6d5febccd76fcee671c52d9bb08acbe13cc9adc97ff4c592 docs/evidence/app-drawer/system-keyboard-qemu/search-keyboard-dismissed.png
DATA dc0bb35cd2db00175a49625c4cbfc35db455bd13029ea743254f52cba22b43cf docs/evidence/app-drawer/system-keyboard-qemu/search-typed.png
DATA 7898de9b3679b7c30a6411dcbe389493c787ab87dd9b785d6c376358eaffb497 docs/evidence/app-drawer/system-keyboard-qemu/search-unfocused.png
DATA 2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7 docs/evidence/app-drawer/system-keyboard-board/corrected.jpg
DATA 59882fcd6820777010fc0e6fb7d553d5fc85a9f1a2bf266af0a10b9774f33096 docs/evidence/app-drawer/system-keyboard-board/dismissed.jpg
DATA 2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7 docs/evidence/app-drawer/system-keyboard-board/focused.jpg
DATA bf9fe2f637ce3ef69b37bbdb7fe37195e996d428cb028c88f67c7cab5579ac23 docs/evidence/app-drawer/system-keyboard-board/panel.jpg
DATA 2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7 docs/evidence/app-drawer/system-keyboard-board/reopened.jpg
DATA 913ee16cc135ef498930ae55d25938f9920ef4f6265b2188ea3f3549258e672e docs/evidence/app-drawer/system-keyboard-board/typed-q.jpg
DATA 59882fcd6820777010fc0e6fb7d553d5fc85a9f1a2bf266af0a10b9774f33096 docs/evidence/app-drawer/system-keyboard-board/unfocused.jpg
DATA bbe2a1db5210ff7da9a821583e2232e4e27f884adaa0ab550def78f4598b88f6 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-after-restart.png
DATA 3fb3ce1e8b330e3fd455a2caf53aea7b67b07baed43260c4f31626948110172a docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-clock-widget-placed.png
DATA 741a8d2a5c2983fe01a883e480993b334179134a9a926fa350fe30b698ccaf59 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-dock-folder.png
DATA 9a91fa9debf2b38dd276966040b7c9a318de20f8044ab8e28a9eaae775dd0f98 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-created.png
DATA c0f16c81ef09b464beb034f86286782a6480032e5531906c87a81a60c03372a9 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-member-extracted.png
DATA 5df90eb3a83cd4f47427e690b64f742b7795daef9fde3269ae3f7c661721b400 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-open.png
DATA 828040b58ad7ad46924fc18d4bf5afad2ddf703037b7323a2ebf0d4a5bea7c22 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-rename.png
DATA c32798981358a1dab29599d3437dd7d9ef0643a55d13f2fb28f65d327c9186d4 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-renamed.png
DATA 1f13d06090c24cc8eec0535f2ba2930e33f2e03263599eb589160e022c0982b2 docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-picker-widgets.png
DATA 032f6ab6426c97cdb08ecdb95a32b2c27ed32b848c50d0a747ffa83a91190a4a docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-light-page2.png
DATA 7cade2185d5426edfd571520dbab37cb60a04256140b2fc45efd3495b0832a6a docs/evidence/home-widgets/clock-date/board-panel-100-home.png
DATA 9fdc354f6d9436cd342992b59d836c458b78d7c6faf2cf0e728349cc60184de6 docs/evidence/home-widgets/clock-date/board-panel-160-home.png
DATA 02ce7b1cdb66b9d684be9c9f951cd611420c7da18f141edb7dadf6856689498d docs/evidence/home-widgets/clock-date/board-panel-200-home.png
DATA cbd3efe5b9aca037e04fec956d8cfe4ede3dfaeef71538588201185891bceec8 docs/evidence/home-widgets/clock-date/host-landscape-steps.png
DATA ab1ccf5557d0dd75dcce28795ba670ea2c855a75b471ddb544bb7dbe98b34c79 docs/evidence/home-widgets/clock-date/host-portrait-steps.png
DATA 0ca9d2b169c3e0612a920c08333a610112cd480324c26fc7a30769d6402841eb docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-analog-dot-matrix-weather.png
DATA ba630cbadc8406ed9cc8aed992b3bee046be68bbb48a3a6d0b5a4411d831b79f docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-clock-bubble.png
DATA ef30699ebb39259b995f81a6b3a266b0b7410965975d81b39143428a665d702a docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-clock-thin-fling.png
DATA 4a2e198e3085b10d99599fb9e4949441b2f13b668baf2cdfd5c4591b76f7ea6a docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-edge-indicator.png
DATA 09f2c39d77fa5ef7146bc3c750bca8df3c2235ab035f4d517ba50f7b3dcabe21 docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-last-edge-new-page.png
DATA 5007dedc8ec8342188b82d2b4f5c779113f2e4183915ba43f7c12411c9210860 docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-new-page-drop.png
DATA 8d76e0a35939afc53c59d3265b7f68fe5021042bf11be763cec82632c9a57e2b docs/evidence/boot-verification/2026-10-01/normal-candidate-panel.jpg
DATA 62cf1b9ed0eeabb10608660522a577cd5fbd2923787a21c10505f1795b012af8 docs/evidence/boot-verification/2026-10-01/normal-restored-panel.jpg
DATA d37a34af2e23014328b1de92c46a696e9d66c2a961c8e770bd9937a45fc2052c docs/evidence/boot-verification/2026-10-01/runtime-restored-panel.jpg
DATA e3e93fb0e742aa910f90df9dd611c5923f3f8d63cd3b063cab2476c842bcf51a docs/evidence/boot-verification/2026-10-01/normal-baseline-panel.jpg
DATA 4af73a4e81494f5be1b8d207f67721345bc565b41264353d709bc987465f0bd8 docs/evidence/boot-verification/2026-10-01/runtime-home-panel.jpg
DATA ba5e8a4f411fad3bc8b2ae0bba9aeaea5c501ebdd2d51f5dd3f8c387af89dc53 docs/evidence/boot-verification/2026-10-01/normal-candidate2-late-panel.jpg
DATA 7d9faa8d4dda52bbc207f2a4ba798c1688f3fbcc7e09728ca0072d7bbd02b07b docs/evidence/mainline-display/physical-2026-10-01/panel-boot-text.jpg
DATA c227b66f47d51885f41bb7a13b1da3cafb57355cd1fefa448399e775086f6491 docs/evidence/mainline-full-shell-2026-10-06/console-after-ddrcp2-fix.jpg
DATA 7887bc93e8d1ea584a164af871391bb5236306453972a3c324315cd148b3c02b docs/evidence/mainline-full-shell-2026-10-06/full-shell-mainline-top-vs-normal-bottom.jpg
DATA dcc114f12b60c087ac0663b8cf1109c2b21bd025bb333b872b596447baa1f7c0 docs/evidence/mainline-full-shell-2026-10-06/panel-purple-background.jpg
DATA ee179c2bd5acb9061a3af48f53535a44026d5e9b9771628b0a77218b13b91e23 docs/evidence/mainline-full-shell-2026-10-06/touch-finger.jpg
DATA d2af9c82e952991b11d9a3259ceabb0bca7491f948053d7096a8e1e6ef4ef73c docs/evidence/mainline-shell-parity-2026-10-06/after-touch-camera.jpg
DATA f211031020afcea2fe58537b82bc16635ee2773c34af41df4cde6f8c3d895d8f docs/evidence/mainline-shell-parity-2026-10-06/power-sheet-camera.jpg
DATA dc7f1191e55daba719f8f0898c13a89f748de8d1880b4edfb395f93e469aecf9 docs/evidence/mainline-default-boot/installed-home.png
DATA 5405de961a963cd1446cb7f42382329048367cdbc9866a248c4445666c6a6bbd docs/evidence/mainline-init-exec-transition/camera-repeat-2026-10-05/panel-dark-candidate-120s.jpg
DATA 31c010bb635bc85bdd6980d8fe602098d4f83ac52a9d36a1c011b50f90fd1b68 docs/evidence/mainline-init-exec-transition/camera-repeat-2026-10-05/panel-normal-shutdown-text-21s.jpg
DATA c2d7bd67952385a6729cb1ade6fae9ef1169f585461deea15def08c26f8b4698 docs/evidence/mainline-restart/physical-minimal-2026-10-02/home-panel.jpg
DATA f57f30940e3323594f29181beb8ea21cd7ca1fdc5a0f210e4e66e798f45ed875 docs/evidence/mainline-restart/physical-shutdown-debug-2026-10-02/recovered-home-panel.jpg
DATA a938168c80109d82d88683faf251c0be44fd075748c8f47dd5f8a9ebe4ed898b docs/evidence/mainline-restart/physical-shutdown-debug-2026-10-02/boot-panel.jpg
DATA 952197f416b79597b2b237f6e37b5bcc16a6df735439af5c4a9700a7221aaa81 docs/evidence/mainline-display/physical-2026-10-01/normal-restored-home.jpg
DATA 8584b78379a3ef16d4da74bcbb2c59af9a23967f48741bd254580ff87c8c2302 docs/evidence/mainline-display/physical-2026-10-01/final-runtime-home.jpg
DATA 09fa5c7a05a14a70de5910a8a95f3a9e7f0f51d20cbfc7a192a619f6870849c6 docs/evidence/mainline-display/physical-2026-10-01/power-swap-recovery-2026-10-02/home.png
DATA bdf4467268c6416f3b862b9a4e33a5b956367acc26c4585995eeebacc5c27d9e docs/evidence/mainline-display/physical-2026-10-01/power-swap-recovery-2026-10-02/home-panel.jpg
DATA 05840b3a48bcb8643008916196c458d3a59f2e4780a810d23f0762bbfe4e4fa0 docs/evidence/mainline-display/physical-2026-10-01/corrected-probe-recovery-2026-10-02/home.png
DATA fb3fcb4c7f8c886ff0baa1de97a95f2670ec1440fb2556f9c7737aaa4cc9be62 docs/evidence/mainline-display/physical-2026-10-01/corrected-probe-recovery-2026-10-02/home-panel.jpg
DATA  9944c9fdef515ee3fc71c5a00cc46d6619d6142d6de17fcf3198d9b653cd44b8  docs/evidence/omarchy-themes/settings-notifications-themed/board/dark-settings.png
DATA  5cb9ac53740657f87d06e2c9667605bd1dc197ea1f0c8850ea9592019adda1c9  docs/evidence/omarchy-themes/settings-notifications-themed/board/dark-shade.png
DATA  4094b29193330d905cae36305574359b8564e35bb11f7ad2d095bc4b142dd23f  docs/evidence/omarchy-themes/settings-notifications-themed/board/light-settings.png
DATA  9f1b063491fa5e4909d29723dbbde3816c43c2b9268b91ee4906ea4bf3db8505  docs/evidence/omarchy-themes/settings-notifications-themed/board/light-shade.png
DATA  9944c9fdef515ee3fc71c5a00cc46d6619d6142d6de17fcf3198d9b653cd44b8  docs/evidence/omarchy-themes/settings-notifications-themed/board/rollback-settings.png
DATA  f96bbf535aa2e78a5b09781c996c7ad4d2359dca838d15ccc28b9c195225a87d  docs/evidence/omarchy-themes/settings-notifications-themed/board/rollback-shade.png
DATA  5fdcbf526530d7d11e5a0f658f69a09b8957c3d6ce1923b30b1b21bf533f48b2  docs/evidence/home-screen/app-actions/qemu/home-actions-right-click.png
DATA  27a43617fdf643598ab4a2a946ba8a1d10c0604f39585bc526f3974e9dfca302  docs/evidence/home-screen/app-actions/qemu/home-actions-touch-grab.png
DATA  ac2be7a175f501ea58ee7fb25fd7a8ecbe60a11b271050ead68ab105dd722454  docs/evidence/home-screen/app-actions/qemu/home-actions-touch-placement.png
DATA 1a3859a823e401a64123eb793af2c764025fbcbbfecc7f4784a8dd6c64a18430 docs/evidence/home-screen/widget-hit-area/long-press-in-clock-gap-1280x800-grim.png
DATA 97b7d126f407e0b8ac292b935fc6e65ec4ab7c41bd17159c31a83a9d1dc91068 docs/evidence/home-screen/widget-right-click/right-click-clock-rearrange-1280x800-grim.png
DATA ef0a2f4190a3912f9fe60b5e8255be09ce09be200a4c204cf47b86eec1bedcc8 docs/evidence/home-screen/page-settle/page2-right-click-1280x800-grim.png
DATA 144823739da80239aa5460a0f0168345a2a3106d6596b9429ee1c8421816b254 docs/evidence/home-screen/page-settle/before-fix-blank-vanished-page-1280x800-grim.png
DATA 6a8a491c6605b7539979ffebb43c8968eeaadf73e0b1455598685dcbfcf453bd docs/evidence/home-screen/page-settle/after-removing-last-page-widget-1280x800-grim.png
DATA f7d82ddaed45d073d32865f61180c6a2a4a3e9ddfa14c5b767f129a5d35a3b06 docs/evidence/shell-polish/settings-volume-layout/dark-settings.png
DATA f51202b93578dbf965c365c3174a9eb11d24522d4965c0f0707b7be63db47d3f docs/evidence/shell-polish/settings-volume-layout/light-settings.png
DATA 4877486f4942ae363c0651664294e0c78fbfafa52a588071fa2b4eb5a04ec61f docs/evidence/shell-polish/settings-volume-layout/board/output-picker.png
DATA 65da519ed8e6c2013dea69b4b97ef671b2552d21a39aeee4d7203d8cfbebd52b docs/evidence/shell-polish/settings-volume-layout/board/dark-settings.png
DATA 76360f2debadb7ae6796ceb177d7702067fffe0af0abb155fbcf44984a1536bb docs/evidence/shell-polish/settings-volume-layout/board/light-settings.png
DATA 882ad1253db77ea4253b2c3536bd5fbff35d0e058c2d1dbee5c8f7b4975f5866 docs/evidence/boot-verification/coherent-manual-candidate/home.png
DATA dbb35a801c8ca1d4fafd0a74efd41dc544bd7190030085a2b3bcfe45b82c63bb docs/evidence/boot-verification/coherent-manual-candidate/home-panel.jpg
DATA a97c7db6d21d50160bbd33877291eba61245b9778728e4c8624df9253c4a16a6 docs/evidence/boot-verification/coherent-manual-comparison/baseline-home-panel.jpg
DATA fbf3f991f1b88f3ba08b2b7b784ea622ea70fbc3749b468dcd33c1acd9601805 docs/evidence/boot-verification/coherent-manual-comparison/candidate-home-panel.jpg
DATA 4e178a71d8ed608b6c4fead588c1c083f88ebea474f8290a0176594bf44d9e17 docs/evidence/boot-verification/coherent-ordinary-boot/home.png
DATA ebb2147f1f632b9d824775d9f010db51061bf87f1241c80b052481e56fb9be82 docs/evidence/boot-verification/coherent-ordinary-boot/home-panel.jpg
DATA 00e73f26a9c1a369b358c42113030b9fb746d39527a7c0c1ff7dcf7460d8e35e docs/evidence/omarchy-themes/drawer-card-generation/dark-card-qemu.png
DATA 8ecd5d4d0e23f3ea9e2337ecef9cdda69a3ebd61f9d721f2541132129e5a8c8d docs/evidence/omarchy-themes/drawer-card-generation/dark-drawer-host.png
DATA 0779dc3360a5f98a39491ac79a1f3bcb050ee486f5614a4af4e34e77215e037d docs/evidence/omarchy-themes/drawer-card-generation/light-card-qemu.png
DATA c675526827cc922b051f30d402807cc6b13afb226756bc8d47ef17aa630f583b docs/evidence/omarchy-themes/drawer-card-generation/light-drawer-host.png
DATA 1d1c0a97fb4998450f271b580db263aa21bb8e1ed00fcb1a123cb6b8ab68eb18 docs/evidence/omarchy-themes/drawer-card-generation/light-drawer-qemu.png
DATA 86a97d3beb06ec564a69256328060642dfbdaacabc59886e0e616bae9a4e07d0 docs/evidence/mainline-restart/physical-runtime-trace-2026-10-02/boot-panel.jpg
DATA 2c033a1688ad58506e0211539185a97ddaf3c5c86e39a39a392c567d57e2502d docs/evidence/mainline-restart/physical-runtime-trace-2026-10-02/recovered-home-panel.jpg
DATA d197f47569dbd4b00ffc4e88caa8f57a090707c5d5b54ad255765742f62f8de9 docs/evidence/mainline-restart/physical-runtime-ready-2026-10-02/boot-panel.jpg
DATA 4c396ff3b029fb82ccd6c39d9f3ae5a22b06fb8d9329c991af856459d9be88a5 docs/evidence/mainline-restart/physical-clock-comparison-2026-10-02/recovered-home-panel.jpg
# Mainline ordinary-init trial and protected normal return camera stills
DATA  b7616d6dfc744893c4f52af15cdea1b4fe81f909fe251ea54ac1ced9563484c8  docs/evidence/mainline-system-trial/physical-2026-10-03/normal-return-home.jpg
DATA  e633d697f387c1d6d4fa7fb827be6bc5665ea54ab3e9e6f1b536724c94d01f10  docs/evidence/mainline-system-trial/physical-2026-10-03/ordinary-boot-panel.jpg
DATA ab2199317d89f02e711c934b7a453373089c084e12b413e9d636c16bf68f7b38 docs/evidence/launcher-curation/drawer-native-2026-10-08.png
DATA bbf09476cc92fa4efd0002fdf3efd415c4b2722deb0ed091d7096892f06f000f docs/evidence/mainline-sd-image/fresh-home.png
DATA 6c8632fb3cc8f1871cdf90d06ee54b6841535bd7500fdb94b05869b1610187b1 docs/evidence/hdmi-mainline/fixed-native-home.png
DATA cc2d10af36ae21000abaa1911dcbad1e225dda5d3c603cbde016f0cae4577fed docs/evidence/hdmi-mainline/fixed-native-terminal.png
DATA 1193184ac0aba5f9e6b8bdc1aa270fc4db3f640ffe77a50a763bff560af2c868 docs/evidence/hdmi-mainline/live-mainline-hdmi.png
DATA c30fbdbc85783130e8a4606df061767724d2199c07426fabf151349f713c0908 docs/evidence/hdmi-mainline/live-pointer-native.png

# Manual HDMI switch: host-only production Settings paint, synthetic controls.
DATA f2f4c25452eaf4d89d9039890238f59faa7398a9fcd13aaafb526243c77fb1f3 docs/evidence/hdmi-hotplug/manual-switch/host-confirm-1920x1080.png
DATA 7dbe61332db45d9205343d03de556efb9a8a6498d6e40acb978bc34bdc900320 docs/evidence/hdmi-hotplug/manual-switch/host-confirm-568x1232.png
DATA 19ba27a947777a66004ad7eac0900d0abb4c8e90325c35dacb4e6716fad585e6 docs/evidence/hdmi-hotplug/manual-switch/host-confirm-800x1280.png
DATA 5490312c11c4c5fdbb92a0f9745a83dce0c316c148cc78379ada559f180e09bf docs/evidence/hdmi-hotplug/manual-switch/host-settings-1920x1080.png
DATA ce417f85b6a8de46d73fb7b4955524e3463106b90b7e0f09185618ec926aa98e docs/evidence/hdmi-hotplug/manual-switch/host-settings-568x1232.png
DATA 7139fd4be7aecff236b5df281a2c0a8b62aaad8b8df96bd03a174572183bf3b6 docs/evidence/hdmi-hotplug/manual-switch/host-settings-800x1280.png
DATA ccbde505048655fa68d53a8719b9fc0081c36bc65175053d6c4f9773dee3a448 docs/evidence/hdmi-hotplug/landscape/hdmi-plugged-grim.png
DATA 8c53f15f85acc02f9ec7a5746e0edb40e0e24f76e0116cbff55f5f64787e2d7d docs/evidence/hdmi-hotplug/landscape/panel-after-unplug-grim.png
DATA 8751565df5b1e63c87b9ea5a219306acdb6b6a8b3e9ccc75e185dd2cac5c313c docs/evidence/hdmi-hotplug/landscape/host-renders/drawer-1280x800.png
DATA 0a74244d895e2fec50725501a172a7bf480e6ab66413fa5f78600d818d7056a5 docs/evidence/hdmi-hotplug/landscape/host-renders/drawer-1920x1080.png
DATA 343ac491a42bbd1c908ba3c18709052ba877216ebee89fa7b3bd2efb0b5d60ae docs/evidence/hdmi-hotplug/landscape/host-renders/folder-9-1280x800.png
DATA be707130ee63e5f173d4f0773eb69cbda52902ab9797ff70c01abc5e2b5bf805 docs/evidence/hdmi-hotplug/landscape/host-renders/folder-9-1920x1080.png
DATA e2ba3efb1c87ee88676ff749e8c4dfbcff5ddcddd98c86ce081a0399e21b3f20 docs/evidence/hdmi-hotplug/landscape/host-renders/help-1280x800.png
DATA 7045157b5371d1b8cdf736f431e306b0496faee2ebe476aae761766d2e9c3ad0 docs/evidence/hdmi-hotplug/landscape/host-renders/help-1920x1080.png
DATA f45596248a932840e6078564d77d588bb61c2746c3c4557af81d8e51cc681e01 docs/evidence/hdmi-hotplug/landscape/host-renders/home-1280x800.png
DATA 0ca331a217bdac0a5661b18d31c65cdfc60e4bf841b070fc63a3503c9af8d489 docs/evidence/hdmi-hotplug/landscape/host-renders/home-1920x1080.png
DATA 5f05afaa389d467e4da022aa89b0e28954f5c5781560e0266f4033069aeccd35 docs/evidence/hdmi-hotplug/landscape/host-renders/power-1280x800.png
DATA 809be86682262ef7aa5a9a10ad16b738c2cc2cba3a177b73705c3ee50967ff24 docs/evidence/hdmi-hotplug/landscape/host-renders/power-1920x1080.png
DATA 467f4bc7cecc80febbcbb90ade203ea1fd0f147fe7ce76429449dfdb1551a489 docs/evidence/hdmi-hotplug/landscape/host-renders/settings-with-base-1280x800.png
DATA 1daa524fb299d72e539fe30e89a885e9ba1560b591a81d06d6477628b726a121 docs/evidence/hdmi-hotplug/landscape/host-renders/settings-with-base-1920x1080.png
DATA 14cab0c1cdb7a05d3e53c9102458283e95bebfd93f8c04f257e1e695476b1101 docs/evidence/hdmi-hotplug/landscape/host-renders/shade-4-notifications-1280x800.png
DATA efd77f7f6efd13ca4611cad029513ab067e438808422d59e918fb8027adc0bd8 docs/evidence/hdmi-hotplug/landscape/host-renders/shade-4-notifications-1920x1080.png
DATA e40919972c198c05d6ca6be10bdc15655cb9d0caab1154c34736f13f7d0fd63d docs/evidence/hdmi-hotplug/landscape/host-renders/theme-chooser-1280x800.png
DATA 50711fa4810c7df0137c97eeaa1f63e03e98bedbf15fb4bd280b0c3d58121e3e docs/evidence/hdmi-hotplug/landscape/host-renders/theme-chooser-1920x1080.png
DATA 3f35ec0b8fb115a14e45a9ef968592c2f14d0d5c79a6126909aece1537ab892b docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-entry-password-1280x800.png
DATA cd5c5d4814aaca240e997b7cdda4dc5ae30ebb2651a2addcea4aee309068ada2 docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-entry-password-1920x1080.png
DATA cfb96550e14595c1cc6ff249cfb25620d789ad0a02e10947c30adad0f6f9139b docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-list-1280x800.png
DATA e66227f34bdb80eb23e88dc0a624591af9b738fc038f9b12a6d26fd389332dcc docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-list-1920x1080.png
DATA 4f9b1ccace0647bd8c3f0ba72a72734b937b1b29b474976bb74ebffc26dcfcca docs/evidence/hdmi-hotplug/landscape/board/home-hdmi-grim.png
DATA 7372b8293e14bfffa47d05c68097ad2ad9a38d520296f7d520566f157b5deac7 docs/evidence/hdmi-hotplug/landscape/board/settings-hdmi-grim.png
DATA 23ebae22bc1c15024d46c406068ce4ee9fb70d308aaf630424a71b44765f87e8 docs/evidence/hdmi-hotplug/landscape/wide-dock/board-six-slots-1280x800-grim.png
DATA af2a55cad5fe45f24c3b09bdc59b833472ef7f95fd1555375aa9a4bd420fe43a docs/evidence/hdmi-hotplug/landscape/wide-dock/board-video-dropped-in-slot-6-1280x800-grim.png
DATA ee3b2919d25c128292035f7c8f81734bf5196df86b3d1f2f2bb5e8db88a4cf4e docs/evidence/hdmi-hotplug/landscape/wide-dock/board-video-in-slot-6-1280x800-grim.png
DATA 0c2812db3da2b2039cfd41bff317c05d4af90ef45012b944bfa8af19e1cabbc8 docs/evidence/hdmi-hotplug/landscape/wide-dock/home-1232x568.png
DATA 7b7cec0fa311bf9096cbc49cfa82581640fc7591cb81a0704b474ddca61c96d3 docs/evidence/hdmi-hotplug/landscape/wide-dock/home-1280x800.png
DATA 9159a4f4c5d3100624614443d41fd5b093b0ef163f3d20e30b07daa0ee05001a docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1232x568.png
DATA 84b6d97127f8ceb1e70f4c3b85cf1994b3fe4637f8372f88afa93364713fbffe docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1280x800.png
DATA 3b6245127cef76666a1bb2f9a087aaf775b080e1f7f1a473b69bf18888a5112e docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1920x1080.png
DATA dbcf4e69ccb55819790044eee32ab81094b6773f9f2b7987e667c7ba80642216 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-password-1280x800.png
DATA 72af6843161ef7f354866d72a281a46e8497397f64b44d1cd69a4750b43c14e9 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-password-1920x1080.png
DATA 6ed36c0bee95582a91d5c228597ab54138c7b2b0d24004d59e98ec408708b3a2 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-saved-1280x800.png
DATA 32f507d9192f4fd49b870800b1cb0ab4faf5fc9228f65745538e8d9740127ac8 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-forget-1920x1080.png
DATA 8b0f1bfa6b50fd0ae6fd1db609decbc22e800a8ceac84f746e01bae6f4e46f61 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1232x568.png
DATA f08588cb20f272da51d3e69f941e5130a1d040e13b5b7f8b0d36e74cd58585c2 docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1280x800.png
DATA 95178d12ade837cc1fda9a03e7a58bbed213230e845e0a64eb79e4185fe1c65b docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1920x1080.png
DATA 0938edbc429fe58e4ccc4f16e4f25e163b8a8c3664f8a298bed8b8c19bfc7f1d docs/evidence/shell-responsive/board/acceptance-2026-10-09/home.png
DATA c98b920c65045ce8343e8bd247fcc1fd7ad7cd15c671477017475c10f2b063f2 docs/evidence/stroked-icons/board-panel-settings-scrolled.png
DATA b0d3c684830cd403884f4f61c7ec7b72661a5fb9a4167c305723c8ff9dcc492d docs/evidence/stroked-icons/board-panel-settings.png
DATA a51cada8f2a82729c14c2f1264cfb951e93776c00de0c1f4132575c3fbce22f8 docs/evidence/stroked-icons/board-panel-shade.png
DATA ef106ae06c7ac7ddc52a993cfab2f130bfba6cfa013ed85c996008b4ab9a1a5d docs/evidence/stroked-icons/host-dark-landscape.png
DATA 5339bfa0b2b08d8ea00a063436fbf49a7ae5ae372029cfaab4b926c81208ac9c docs/evidence/stroked-icons/host-dark-portrait.png
DATA 6c3d4ea48118e0b022af08ee0e73e3ca62ccc59f453a780c4620f6254e5a6f66 docs/evidence/stroked-icons/host-glyph-sheet.png
DATA 4b8a9e1e62f86d1b73e363abecbf30a86e95e54f0a892374519834ee8343d933 docs/evidence/stroked-icons/host-latte-landscape.png
DATA 04dc1e1199800310f48125df1fe9764373cd9eaea5be0834fcb68852391b112c docs/evidence/stroked-icons/host-latte-portrait.png
# Current UX candidate native captures — 2026-10-09
DATA 83c8b4261beb9621eaaeed8c8e6c1d4fe25bb16abbad63de4234355d25e16de8 docs/evidence/ux-review-round-2/candidate-2026-10-09/overview.png
DATA 2d009ee5c0b97bfc21e04592bd099b0f21643bafe660043ed9d0a3e7c418b286 docs/evidence/ux-review-round-2/candidate-2026-10-09/drawer.png
DATA cabe8ccd9ea9e02dab94e4b12cd4a849b5f3c640ed33dd6d007694a4a2592830 docs/evidence/ux-review-round-2/candidate-2026-10-09/settings-loading.png
DATA 28d54e2559cd392b108649241ea60bbdafb4d17ac8d653e84b0e7cee638aa931 docs/evidence/ux-review-round-2/candidate-2026-10-09/settings.png
DATA  e5c034b1ca848a75afc32f7f37e88d49df6079986e20dc23fa744c3726a0af30  docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-entry-held.png
DATA  83d4d2abb9f8dd0a3857365b7f748742d165edcb331220b175de3b9103d77375  docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-entry-reverse.png
DATA  5cc5752bd9f8c643f7fe9e07b1a77064a5526d25e01bcefb9266f4ff72dcccde  docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-expand-middle.png
DATA  af1e532589fb73a6a499dcdce1055460dc60f5b644383a1b3603c9a0d9d9633b  docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-expand-reverse.png
DATA  298b3d4a631e79af2a7781e07346e8f994d965da6c578d5619a53a3a55905945  docs/evidence/coherent-shell/interruption-gate-2026-10-10/entry-held.png
DATA  09d0b1beeb684359bc181bb597351a48164bae9b3c3d86bfd9efeda5dd2742c4  docs/evidence/coherent-shell/interruption-gate-2026-10-10/expansion-unmap-middle.png
DATA  5deb1e9485c678175369348ebef3d953cb58403ba35a726621523e07edb3b8ec  docs/evidence/coherent-shell/interruption-gate-2026-10-10/expansion-unmap-recovered.png
DATA  19a2b3247c4d649369d209ef8db7221e0a7b1ce8e0b71ef9cedca9397bb39764  docs/evidence/coherent-shell/interruption-gate-2026-10-10/finger-reverse.png
DATA  0dd90de10d007f694e62dad536a4a727a418759a440fed8ac3c4a03f868301cf  docs/evidence/coherent-shell/interruption-gate-2026-10-10/new-contact-middle.png
DATA  7b0e552f4353e45388f53087dc13c4112a62f43afa1d65d9351499f9005c0e02  docs/evidence/coherent-shell/interruption-gate-2026-10-10/new-contact-reverse.png
DATA  ef21f6b9ec3318a183a23afa3684831db45af1db9fa8a6cc49b828812ef2d8d7  docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-placeholder.png
DATA  1deb07b5d46be0a31537402f5361ee5c502f8eacda9e18b1f1f00ac1998c5638  docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-public-control.png
DATA  b2a1f9fd9d44da437eb3d8259818399947b26932ec27e417b964cb311940b14e  docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-transition.png
DATA  388e599604519b8cb1c2460eca20a263b9dd2bf242a39a07b0e82efe74906a0a  docs/evidence/coherent-shell/interruption-gate-2026-10-10/refusal-pending.png
DATA  b3e22611d1edb2af5ffd758c2a8611ff8a26e2904bac8ff8bb4fed15ffed0878  docs/evidence/coherent-shell/interruption-gate-2026-10-10/refusal-timeout.png
DATA  8a86045ce2e93f57e1e03dca703b9eb9cc623d77b2d5bb792eaef2f8f6825c8e  docs/evidence/coherent-shell/interruption-gate-2026-10-10/second-contact-reverse.png
DATA  d1bae5b45118c28913e28e0e12c5fa66e82203366920f5b378b14c65be52bb87  docs/evidence/coherent-shell/interruption-gate-2026-10-10/source-unmap-recovered.png
# Native Help after persistent ordinary panel boot — 2026-10-10
DATA  2f81e737d0511f644884883876d82572fb67d86ccde475a54fe3bddeff3ad164  docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/ordinary-help.png
# Native Help on the volatile mainline HDMI candidate — 2026-10-10
DATA  3fb102a889e56bb760935320dec9e14e546d1b79743cef05ba91a35a97a4e57f  docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/help-native.png
# Deliberately opened Help/navigation aid host evidence — 2026-10-10
DATA  b39cf837f2429aeac1c57e9a3da431f636d3d8cfcd1dad5d1bfef112d62666e9  docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-buttons-hdmi.png
DATA  732d489086b9e9b71addf83951602b1df519057fa668717eb6b7124b676d7509  docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-buttons.png
DATA  9a39433788953784ec03217f05c1db3b3aa11a370f014108aebfe1f7def99c15  docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-drawer.png
DATA  dc51a79c53b67e1ead64c32b1ce4be9fb2908b8cdb6f632846b314b77cf4d190  docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-help.png
DATA  be876d1bc6515c1e346450c8f8c0f0d5b477fcbbe7a51515c95e284ac753f244  docs/evidence/coherent-shell/navigation-aid-2026-10-10/drawer-568x1232.png
DATA  55423d4699800eb9b55e3353e111039a6535fb040b81afd04637c0a2fb4bc4c0  docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-buttons-hdmi.png
DATA  923cfcc3bb698118306399317dd241a8dfa51435629007fff38903358d934791  docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-buttons.png
DATA  5e698163701ee1c86962c53a459b9e7aff68dc2d11fc8fa961887dadae099087  docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-drawer.png
DATA  193bda0b9be35ad0a5f637c9324db54ae582299e86ead4660f63cec881debb26  docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-help.png
DATA 1858054405c18a6f9236793779eec16d900195d2ca0846814d8fb0a218037eb5  docs/evidence/coherent-shell/notification-preview/banner-trusted-1232x568.png
DATA d30df0ee7fb7c7ae12264847173b10afbd83e0d6d41b7611c4cfa6f71f325980  docs/evidence/coherent-shell/notification-preview/banner-trusted-568x1232.png
DATA b86059e9249f9018bbff16dba9557df0e59eba09b741fda9b61218d31d967ca2  docs/evidence/coherent-shell/notification-preview/banner-unknown-1232x568.png
DATA 89ec298b9ce93940f7d923f2f60b606477c39f7c2385c85beb4f7669bbb4d648  docs/evidence/coherent-shell/notification-preview/banner-unknown-568x1232.png
DATA  658ff706daf01c54667144e023b8a4568e3079736668d1a210e726104fadb887  docs/evidence/coherent-shell/notification-preview/board-banner-over-terminal-grim.png
DATA  a114b385868a612bec62da7f9db8a6fe9fa6b438e63683078f4cec6b0764c738  docs/evidence/coherent-shell/notification-preview/shade-open-tag-replacement-grim.png
DATA  89fb5e30e2319141d86165b5d2cf341a200cd28cfb524d01ea14343e3bfcb2de  docs/evidence/battery-details-widget/host/charging-1232x568.png
DATA  3e592c07b4052e7ba5337ee314ab7455402b0216f810f85b707a9e6cbde9f03c  docs/evidence/battery-details-widget/host/charging-1280x800.png
DATA  7da2af5ea9c40498b74d8308fcead6242a76bf8fb2bcbcfea1fb069da8d9de4c  docs/evidence/battery-details-widget/host/charging-1920x1080.png
DATA  60b7996a8c7278f843b10265c1ddf9f51ee7faa7c7beda7590a2d38037a85b03  docs/evidence/battery-details-widget/host/charging-568x1232.png
DATA  0fae56c2b143e1e698f0faa6c8be231f1a91fb266a32784845cf2ab563bdbb23  docs/evidence/battery-details-widget/host/discharging-1232x568.png
DATA  8199e0d4c040ba068b2977ffde96598caee1b1c8de8018b49a1e9464c81eaf75  docs/evidence/battery-details-widget/host/discharging-1280x800.png
DATA  28dfa0fa0b1f92082a6f28fae3750cb413706b0d130f5896da6a008c090402e0  docs/evidence/battery-details-widget/host/discharging-1920x1080.png
DATA  dbc9d9af23a4a61f023d824faf62c130267d06db5bb4edee2ae2e82b7ca9978f  docs/evidence/battery-details-widget/host/discharging-568x1232.png
DATA  b3f33ed0528e88aa17841a8557006bce65b2e96394e05ad11b33ca3961945ec3  docs/evidence/battery-details-widget/host/no-battery-1232x568.png
DATA  1168261a0da7bdf63f4159a1f88c4ba69e19ae14d03861000fdd7b7172b52ea1  docs/evidence/battery-details-widget/host/no-battery-1280x800.png
DATA  020462acd02e38f9e85e5145a19da89f1084a6003eaf6cc4494a5357ed0110e9  docs/evidence/battery-details-widget/host/no-battery-1920x1080.png
DATA  a03c125e64c86fec1b327dba56c78254508ab60af71e55efeac3b43b16cb96ca  docs/evidence/battery-details-widget/host/no-battery-568x1232.png
DATA  e954fab750d4099ee4d7120197cda001f7692b4c1add50c2a35e465360a721d8  docs/evidence/battery-details-widget/host/picker-568x1232.png
DATA 418b3422b4a9b0f79b1ccc46ddf97740956762fc12e727182eb17f88eb332009 docs/evidence/battery-details-type/board-hdmi-home-160.png
DATA 85c42274fdbbd7132eef19e3fdf26e867c4f0d50821e3f2f11ded1d3123ae178 docs/evidence/battery-details-type/host-landscape-steps.png
DATA 64642d60967ca79da8135460fd7b381a24d16e77e1fc212424b14bfde449fb81 docs/evidence/battery-details-type/host-portrait-steps.png
DATA 7734298d1350e5de05032c5196b9bd43beddb97fd92002b8fbe4176d69438416 docs/evidence/battery-details-widget/board/home-page2-battery-details-1280x800-grim.png
DATA e359c679fef4cd256b634ba0f50b538a0d9137699b92535b7a9bfb42cbd4d21a docs/evidence/battery-details-widget/board/picker-widgets-page-1280x800-grim.png
DATA 95cdbd8c9bef73f125dddfe09bede8f788f1449279e051a6cd3fafd5e895415b docs/evidence/battery-details-widget/history/day-1232x568.png
DATA aa7fda60f081d96aced6385caa21ceba5f76313a442b446c99221bfb96acbb28 docs/evidence/battery-details-widget/history/day-1280x800.png
DATA 3dd5441b85f70a7ce9e71fe1a5c673445ed42d6f706b81a949315dc8a9040ad7 docs/evidence/battery-details-widget/history/day-1920x1080.png
DATA 73b75361db4c657da09396de2d83f70e33ed2fea73121fa2dc2eeabba7b41f64 docs/evidence/battery-details-widget/history/day-568x1232.png
DATA d4af3b4854df0ae0d7cd904c4546bd9673d518f163d696a6adef5aa5ac7ecc30 docs/evidence/battery-details-widget/history/fresh-1232x568.png
DATA ecadad5cc7bb0f213f2b8a491582a27c91c5a56ca00ccb4e1097e98e644cfae5 docs/evidence/battery-details-widget/history/fresh-1280x800.png
DATA 1a658f6118544201ef42abcd7b8343d4a6e1b69fac925a218f44823e7e252220 docs/evidence/battery-details-widget/history/fresh-1920x1080.png
DATA 672fe3c7ee2c05b7cc1b009f379e510f2e8426600b2a681c190fdf3bed0c22b7 docs/evidence/battery-details-widget/history/fresh-568x1232.png
DATA fb49616a25f887cd0f983c825729929cce2b99775c691bea78c1e37aa7dc6447 docs/evidence/battery-details-widget/history/board/page2-graph-1280x800-grim.png
DATA  4bc927d031126339723be556a533c0b2e7e37435d15bf55a5273771469712ae7  docs/evidence/recovery-routes/touch-app-menu-qemu-2026-10-11/drawer-actions-touch-hold-menu.png
DATA  a3ae45784cee598cd059ad936fe21e25e74b8410ddfbe506674a2c2a0206ad97  docs/evidence/recovery-routes/touch-capture-2026-10-11/window-list.mp4
DATA  e4cb7a888f92d37b8145d5751d516dd4bbdd2d98fe4fe21a0f90937d225b6da7  docs/evidence/recovery-routes/touch-capture-2026-10-11/brightness-denied.mp4
DATA  eaf032fdc191224528a5c91d2fbcf3377d730a752047f4bf1c44738e1e273f02  docs/evidence/recovery-routes/touch-capture-2026-10-11/video-cancelled.mp4
DATA  f0a3a6dd1be3da1aac8cd966bbbffb84a6284567d5de684cb5ccf837f1f61a7e  docs/evidence/recovery-routes/touch-capture-2026-10-11/video-stopped.mp4
DATA  b5506ce563292b714551bb6a35de3e378b088ed60651fa05a6265281b1d7675f  docs/evidence/recovery-routes/touch-capture-2026-10-11/settings-denied-native.png
DATA  f078407d50b5b949a6ee29f6f41e649f0ad74a0c3b1cc263c099073f9ca98181  docs/evidence/theme-picker/combined-install-2026-10-12/home-after-install-native.png
DATA  d5e9e45aaffb221acc1a7a56d9951d8176a4d8e37e5b4c2340c096959c473efc  docs/evidence/theme-picker/default-backgrounds-2026-10-12/themes-without-saved-choice-native.png
DATA  03df501db91377f9ba381c07dccf9b0000a1d358a717696e4d3de953f05a8e77  docs/evidence/theme-picker/row-sprites-2026-10-12/sprite-build-picker-native.png
DATA  a74cd1ddb6b77674c23ef6255a09cd09a90bdc471fda3ae8ef6d5cf495bb2ba3  docs/evidence/theme-picker/board-session-2026-10-12b/18.3/position-curves.png
DATA  ca4d7726de8bd0b39760a5b4a10858f0fa12e9ad0b80d360ff397f413385015d  docs/evidence/theme-picker/board-session-2026-10-12b/18.3/velocity-curves.png
DATA  f299986e3fcee4497bc64680d1e0d8ef8f1ccff26efc18a3af8976a22a4cd0a9  docs/evidence/theme-picker/board-session-2026-10-12b/install/installed-picker-native.png
DATA  99b2ce3c66e9f30ba473638d6cf0e33c0e2e33cd1035f48782c536e7959af99b  docs/evidence/theme-picker/board-session-2026-10-12b/install-2/installed-home-after-apply-native.png
DATA  57ac5ab689645e6836f75f06c27b01c3aaf261909ccd5e2d8652b4c2fea84c2b  docs/evidence/theme-picker/board-session-2026-10-12/10.7-6.6/panel-bottom-full-resolution.png
DATA  7e131b309e4159af7095a885c20504b1f96f6eb3eb3acba0d2517a40e44e8d8e  docs/evidence/theme-picker/board-session-2026-10-12/10.7-6.6/picker-dark-light-dark.png
DATA  dc35b46841c36e893c0e2486b323f09af3c68d33c293da7eb8be802d716a8afc  docs/evidence/theme-picker/board-session-2026-10-12/13.4/browse-base.mp4
DATA  95e2e17c3924071e0c90b13d2a9dab4451b7c0743a081bd9f6693a05b0526fa0  docs/evidence/theme-picker/board-session-2026-10-12/13.4/browse-cand.mp4
DATA  5deada975fa50bf93d7a953937843fc4deca474fba7efd4d37163460a1705013  docs/evidence/theme-picker/board-session-2026-10-12/13.4/vis/baseline-open-theme-background.png
DATA  e55929ec58bc52e2f8d959894ff55174b1596eec86f76d9175179b3e1ad53619  docs/evidence/theme-picker/board-session-2026-10-12/13.4/vis/candidate-open-theme-background.png
DATA  d29948d090aa47dbe99fd62e54b7ec2dc089c5197548eba3a37079060b838d54  docs/evidence/theme-picker/board-session-2026-10-12/18.3/gesture-release-to-rest.png
DATA  7e44fb5c7a4443aefcd3be11549af1d26815501a5f98f0248dd4af75d91eefe6  docs/evidence/theme-picker/board-session-2026-10-12/18.3/gesture-timelines.png
DATA  2b5b76d5e25b4fe5f35398c06fc339b2863468a1376245f5846418783d30c115  docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-ca-bg.png
DATA  7997913ea7ddfc13ba865c7614052838da147851b0e3fe9f4623c66923d006a9  docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-ca-theme.png
DATA  7884f1bbaf1cab44ef5a91856f97c98ada66d5db3eea8d2632725083d6c28924  docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-mo-bg.png
DATA  854cacdba026a85315abcc61b565ddebc3293fc50009c7c5b2640ab17c069726  docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-mo-theme.png
DATA  379ebd25d4a0f224c33d2651d7aaeb134fa7258b625503b12e1e4a2d3e2f5cc5  docs/evidence/recovery-routes/touch-capture-2026-10-11/stale-splash-camera-zoom.jpg
# Mainline boot splash board trial camera stills, 2026-10-12
DATA  d848b4231cde223d49f29d2392cc9e5aa0f53a696604921b1038f5ed1f8dea1e  docs/evidence/mainline-boot-splash/board/aruco-target-at-uboot-prompt.jpg
DATA  1d9e4f9fb666eb675f387c8c20790548f8a3f35bafbd429a27ac051975c2ead1  docs/evidence/mainline-boot-splash/board/fb-poke-after.jpg
DATA  498f1bc8d346615497735748e413f8981f1798384ad741a281a3f5e22f4e2d75  docs/evidence/mainline-boot-splash/board/fb-poke-before.jpg
DATA  4dd87701a7449f6e5e2bc62c4a20b313c2501a8c060ca167f7fc96ceeb971c97  docs/evidence/mainline-boot-splash/board/handoff-film1-strip.jpg
DATA  40fbecd977357ed567f28d5253c5d502454fb0422a05c3be7cc4f02891123a6d  docs/evidence/mainline-boot-splash/board/handoff-film7-strip.jpg
DATA  2c11206efc4b2a5bb0ec471f0ca738e1e3c8fb52e2d8d899d3b4b37c9765ef33  docs/evidence/mainline-boot-splash/board/splash-at-idle-kernel-prompt.jpg
DATA  b7e0c5fa9b1f9cb9e327d310bbeef5c05df6ea15c4103c3e6708a09b125cc463  docs/evidence/mainline-boot-splash/board/splash-at-uboot-before-kernel.jpg
DATA  dc38dac11ae7f6129c9433fe43db56dbfdc01fd2e0d3c7fdc101e14fa129e43b  docs/evidence/mainline-boot-splash/board/unreserved-kernel-tear-film2-strip.jpg
DATA  a6a8591d874042351b5785b57b87277c1af63eeb007045ebb220960a896a03e8  docs/evidence/second-core/linux-start-2026-10-12/cpu0-start.png
DATA  e618055416a78cf92d162d4ab6fcdcc24da5d0349e19af82886d7d9e48e45cd9  docs/evidence/keyboard-base/shell/host-renders/settings-with-base-1232x568.png
DATA  104cc64446e119ada93a262fb8cd42c4edfbb71351fe1240e23af9608bc4dfef  docs/evidence/keyboard-base/shell/host-renders/settings-with-base-568x1232.png
DATA  289e8fdf6ef299338eef4531648a680f111e86022a96e7320bd720b00eb3dfac  docs/evidence/keyboard-base/backlight/settings-slider-board-grim.png
DATA  297e1020fe8fee839a7cc438ad0188e9854570ed3f6dd0972e099624b62db857  docs/evidence/keyboard-base/shell/host-renders/settings-without-base-1232x568.png
DATA  8bf60ecef682bbd3096389c6fd385dd5bae0442ec0e8ff4ace14ac32a94abd9d  docs/evidence/keyboard-base/shell/host-renders/settings-without-base-568x1232.png
DATA  2b291140f4b245f798056e3464f81c7e7b2842f366b312e53052326aba43e79a  docs/evidence/keyboard-base/shell/host-renders/shade-with-base-1232x568.png
DATA  f5b353a2e56808b422a389db46e05ba66942f180dfeac519812dc334d2e58711  docs/evidence/keyboard-base/shell/host-renders/shade-with-base-568x1232.png
DATA  6200cdc038df4f5cfcf74422c60f13be70a32444e9221637f93e4af3157df22d  docs/evidence/keyboard-base/shell/host-renders/shade-without-base-1232x568.png
DATA  f3689f64b1d76d8cddaa38b41448d23af3191c499a3b84cbeee3ac123e5a4dc5  docs/evidence/keyboard-base/shell/host-renders/shade-without-base-568x1232.png
DATA  6c17a39b1e712ed00ad8bfd58a1b25898683ea60b202dadd98a0445fb4c28ac8  docs/evidence/keyboard-base/shell/board/settings-landscape-drag-injected.png
DATA  6c17a39b1e712ed00ad8bfd58a1b25898683ea60b202dadd98a0445fb4c28ac8  docs/evidence/keyboard-base/shell/board/settings-landscape-grim.png
DATA  b41da29af5be0df5d36eba405099ca982ca77038b201c19221cb770800f13f0b  docs/evidence/keyboard-base/shell/board/shade-landscape-grim.png
DATA  58829059cff1e99ef81e09d252af7c7203d0957336c79c764d56f90eda1dd9a5  docs/evidence/keyboard-base/shell/board/settings-key-backlight-off-injected.png
DATA  6e52317412dd88c019d15fa08558b59ce63bf68c5b7656d206ba1179c7f48a91  docs/evidence/keyboard-base/shell/board/settings-three-column-grim.png
DATA  0b84ded661718cd1b9306ef2327c4a4218f6e4e85143c244526130f1bf5457d3  docs/evidence/keyboard-base/battery-policy/shade-countdown-grim.png
DATA  35392bb82d2662916a720b29ebeb5594de6d1490e040f07686ad69b8aab7a726  docs/evidence/keyboard-base/shell/board/home-battery-widget.png
DATA 15db802b2ecd6922ddea88a9241ef1ac2c1170f03239c04eada585e206ef5e0c docs/evidence/display-touch/trackpad-restart-and-long-press/first-swipe-after-sway-restart-page2-1280x800-grim.png
DATA 72969291055b086c99065f7f595d78a04ecbe8c3609958c6aede900abf581e42 docs/evidence/display-touch/trackpad-restart-and-long-press/long-two-finger-press-clock-1280x800-grim.png
DATA 1e858f92dd9f427097d33a4b98dac5b37511b5c19b33020fb63c3147ffdd1212 docs/evidence/display-touch/trackpad-restart-and-long-press/long-two-finger-press-page2-after-swipe-1280x800-grim.png
DATA bc20c47de804c4f5527101e6f8398009d47de992c8434b397740d17b321094f6 docs/evidence/rest-of-text/board-panel-100-home.png
DATA 25e9fbda189c1349dd464f2e741065fab1baa77ed140369c4790bfdc9559b704 docs/evidence/rest-of-text/board-panel-100-home-weather.png
DATA 6e222d41121d2e15b3e0a882577b0254fde1067a2716aa50fdb044673eaf893a docs/evidence/rest-of-text/host-banner-1232x568.png
DATA e7d43131d2a871cf09143d8e3b5f304338fc22c66522d8f01e3c753340b1090e docs/evidence/rest-of-text/host-banner-568x1232.png
DATA ca4afb3558abc30f43505beae2499dbc7410712f9cbb33abdb76731b942a1cd6 docs/evidence/rest-of-text/host-help-steps.png
DATA e0bf987dd554a51d571177549278875a59a03f7da38cdf863690d69f124ca427 docs/evidence/rest-of-text/host-help-wide.png
DATA 40af3196323e16637a133d30834077dc82233204c4d55d17edac781342786b07 docs/evidence/rest-of-text/host-themes-steps-568x1232.png
DATA 536e64bc9f493912259970e5a137678db4da9c78505137dd8f136d71c02ea21e docs/evidence/rest-of-text/host-themes-1232x568.png
DATA 7ed97151eb5301a3c567ce5e62f2e32fad72ee8e7296afb1db073b1fd08061b8 docs/evidence/rest-of-text/host-menu-splash-568x1232.png
DATA b537a8fb335420c5812d18d81b0ea6c9ee3880390a81b4db884594de703476d7 docs/evidence/rest-of-text/host-menu-splash-1232x568.png
DATA 64c0fc8b9758247af7bdf85f2457d88ac1a695bae7fd387eb42a3dc6d543c3da docs/evidence/rest-of-text/host-themes-1920x1080.png
DATA 84944d451c4c5266e381fbac4b859350e3c50e7b36d9f583f3b2de2ea22c5dea docs/evidence/rest-of-text/host-home-widgets-steps.png
DATA 9a6dbcaf060694446bf9c1aacc827cf46e47c118f638cf8a0462a91ccdab845a docs/evidence/rest-of-text/host-wifi-200-568x1232.png
DATA de6d2d21d69ae2665761c63868da86a650829570fc4c84d77b4ae88f9e6e2de7 docs/evidence/rest-of-text/host-wifi-200-1232x568.png
DATA 81ff11de0912324f6ac0f0a6de8605474c80b9c331be793a442c5fbed05c702b docs/evidence/rest-of-text/host-wifi-100-568x1232.png
DATA 1416ea0b21de344e7d619a22ffb3a88636fe5aa51be06c10be1558a6f540e5a1 docs/evidence/rest-of-text/host-wifi-100-1232x568.png
DATA 9a9b114124f744820f581a8eb43f8ff6f9db4aec88de5205269f60d8a99390e7 docs/evidence/rest-of-text/board-panel-100.png
DATA b5415580d0ea62acb239e220ebd320fab3b35145a245e79da39e433632fa46fd docs/evidence/rest-of-text/board-panel-200.png

# Current splash baseline film, 2026-10-20 (diagnostic; task4.1 open)
DATA  3cb362a67335b160be5a16e7dca5a8be56e2efe52bbfcf025e4d9713781eb91d  docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/baseline.mp4
DATA  47c4afcb52a2d17c8adbf0db51c970f31f8013c2a4dac2e79ea48f6cd22a1fdd  docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1426.jpg
DATA  069973fa256f5b48a1cdd2463141fe9f887ec03a11d83b37fd8504da060cdfc5  docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1431.jpg
DATA  3fd83b6c03c5b15f3980e793acca5072d97fb20a537a4e115aa10ea5fb3f1875  docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1436.jpg
DATA  6407b53f691f0fa16e814fbbc1eb0e6561b5427505442e58f1758446976716e7  docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frames.jsonl.gz
DATA 1580c39907dbfa971f3d8bf8236689d734341ddda8a17e2fa3ce0b835176abd9 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/camera-calibration.mp4
DATA e9c1e3c374d9e6cdfdf3b2c62884dbdd45a8b06f3f398477d475ca9b8786ac26 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/calibration-frames.jsonl.gz
DATA 53d58204ec7eb7b6860d3d3564a40ff9421033c5df421253851d70264829717e docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-boot.mp4
DATA d10957f38c4a58990b76473ae92bd5771e3f68dbed1606f6a2649802a4d9ed01 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frames.jsonl.gz
DATA 750bc4fab6ce79dc1d5cbee5fb7e65b108c7959768ec9f843a1cf3f123c5a387 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1489.jpg
DATA 095abfef584a31411c3428f197cdaf169f0071b6eb86bffbf4aa2dc06c22f318 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1494.jpg
DATA 56583fb3d151f0134cfb9df79f30a5151d0cdc1b6bf76adc2300998dae7d424d docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1499.jpg
DATA db46cd51f93504cf2ad6e63473ba512c45af7b9be6286cd1fd056adee2ae0289 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/boot-and-calibration.mp4
DATA 530c7ed5bfdd2ebd7cb06f6d2bc855ced16d3b60a1fb7d3d847c5d93e6f489dc docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0350.jpg
DATA fe32471546f39087964a47bb032e688ebce9adb9350c4122018d63b5e640a8b6 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0355.jpg
DATA df21ce7f4c3b35cd1bbde7573c0c70876294bafcc2df37deb80c12f049cc7a0f docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0360.jpg
DATA ad29534e4fdf62d2540480c8a88bae22cd939d18a49e976f7a8b24f1cdbc6483 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6922.jpg
DATA 035b04a22e5de9fd5f5a2a41e9b5df0a30cdcefd3be0ce2402fb0b1cec6c35e0 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6952.jpg
DATA 978cbf2119bae4803fb9fef6edd6fd67947ff81388480f75f53711a84a8b842d docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6982.jpg
DATA 877160f6475b5e1befb89d6d320d0555430238f2394a182835203bc146a5ec45 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7017.jpg
DATA d8cfe3266ef3aeb3c43f7ecfd32de6013d32bf637db58f840669db109c1698c9 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7048.jpg
DATA 4ace712afa9bc03b4f7022be525e46aa8a35ba523ed3cef36a09b57f66ec63a2 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7079.jpg
DATA 01b5c5ef63de3fed38058f55863d6cb1cab6e1996cb96af3c2f9f996ddc61ae6 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7109.jpg
DATA ae75797fbec9a5fb7eb855595b7f2b2c7ec0562406d6c2bcdc0bf6ae06da86cf docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7139.jpg
DATA 95bdd638c97cfca7b5bf739a3e0f4ba4bdfbbbdf67033f91e2b8c9fee5080771 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frames.jsonl.gz
DATA 3fb586fb415d67425bb69b622de0a64818b2eddd43f0bf12a117ceec5aea34c6 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/host-clock.jsonl.gz
DATA 09a52ca5c5b3b3732cec96e68ca4c5a7c3acffb6f42f00cc14540ffbce2cef61 docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/timing-analysis.json.gz
DATA b0f531e19c7ea4a8d64c911e57c996a784374ffd7552ab6ff4ca57f258a28051 docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-covered.png
DATA 38d331f1606562c4cc6b359cfb4e7ef472a3be8f2c6b12f70b4aa7ae4f2c7899 docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-panel-video.mp4
DATA ac95204a3fbc83d8cbd0e7ee60359809c96b88be8c0ee923698a24d0aeb2fca9 docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-static.png
DATA bad4d7951fccb5f1238a63703be1d701b6a62a9fd5545cbbaae6364e56abc421 docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-video-second.png
DATA b6525a11d4555f88dfc7fc37e501b0baa1d2a88e0c052c464fc96b9be3593323 docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-video.png
DATA 99a2c6b0191ee7147957f6d9dd6c0df9745b2d7150f64148c3b28a8069851461 docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/panel-pause-resume.mp4
DATA c751f7951fccb20f9f5b5048ce070d9c731516a9e5edfa625c38ac1b4993b44d docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/postboot-home.png
DATA dac16dda343c1c88ed8888357c78bd83d690f037d9580a0945eb45528c0bd54e docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/reduced-motion/paused.png
DATA 01b122e485f94d6198afbc0eb8502cc06391277edf382f895d8c63d3c5d53ff7 docs/evidence/shell-design-review/build-1r8zfd5s/r3-themes.png
DATA 1812d04b9e217008ff82a7834baa363d79189e00c6d9d7792411aa391517dbee docs/evidence/shell-design-review/build-9kam3kq9/files-buttons-zoom.png
DATA 69bfb72118c3256f4356b77a2710d5e61c171e45d2b0ea411028fa75cc625603 docs/evidence/shell-design-review/build-9kam3kq9/r2-drawer.png
DATA 7ea1fce0beb946d4a82aa40a4ea0b35f38ff35e76d76973c7d13588e5f67404e docs/evidence/shell-design-review/build-9kam3kq9/r2-files.png
DATA 4343c20dc5e30f0445ce030cf121b68044afe36bca884a3622a1f10837d716ca docs/evidence/shell-design-review/build-9kam3kq9/r2-home1.png
DATA 34e366cb0bb5b36e61057258a5819193ebb8a9dc15c7ba506a6d9268ee0e9247 docs/evidence/shell-design-review/build-9kam3kq9/r2-ov1.png
DATA 85e1c182777512c610f2629a7ce62be0ddd27c0301355fe2262a638b51a9b941 docs/evidence/shell-design-review/build-9kam3kq9/r2-ov2.png
DATA ed400d49773fcfa67bb1059062bfea76b6fe889b11234d598191e4417352d44e docs/evidence/shell-design-review/build-9kam3kq9/r2-settings.png
DATA 03337109f40e66e8d74ab77c42d007340a864cc34040254ebe375a22b70a6e1c docs/evidence/shell-design-review/build-9kam3kq9/r2-shade.png
DATA 91a7ab0408513305fcbde2180dcce8cabbf0a9a99f4400afd216dbbfe5937005 docs/evidence/shell-design-review/build-9rbjw6vl/04-settings-scrolled.png
DATA 36cab3e01df021bb06a38d244df12c8f6ccf6890d30c77ad3fda0b706f658cfa docs/evidence/shell-design-review/build-9rbjw6vl/app-2048.png
DATA 5dc1f1b00be815aff60431c57aca46db89de9ea4bf902583076caebd3735d832 docs/evidence/shell-design-review/build-9rbjw6vl/app-clock.png
DATA 3c0827cb2de58efe9e1306e20989620c2d158addbe1aaeb8ca97680b68e9b408 docs/evidence/shell-design-review/build-9rbjw6vl/app-fifteen.png
DATA 69a8038a2d73680c6c00b41dfa78831b0547a987936db32a4952e52ba793bfcb docs/evidence/shell-design-review/build-9rbjw6vl/app-galculator.png
DATA f01245f4ac1379cb56c757e2de832b330bbfb3faa5d0b7c65c1b95b761fc289d docs/evidence/shell-design-review/build-9rbjw6vl/app-net.png
DATA ae0dd731fc9c405e6f0a1e70abc4048e1e203b6196457efbbe01548278d805dc docs/evidence/shell-design-review/build-9rbjw6vl/app-nethack.png
DATA c74e282b77e30a09409e1b1406f612768bb651ee035824b112914b586c137f32 docs/evidence/shell-design-review/build-9rbjw6vl/app-samegame.png
DATA 32a96813757fe7feb0d533314aa1de7bb72c7d4094c72edb3588369731101fbf docs/evidence/shell-design-review/build-9rbjw6vl/app-sixteen.png
DATA 2f99703c82316d3c4752faecfabbb59cd36a5e35ea04bc58357320ec21e8e3db docs/evidence/shell-design-review/build-9rbjw6vl/app-timer.png
DATA 4cea40933d790e29bd13cd92b5004b8b22388eb8bac1fc8945b4c8808218f035 docs/evidence/shell-design-review/build-9rbjw6vl/app-viewnior2.png
DATA 008f58267065c92f33871018f7d6f9e909d7326fea8efbc215224eab12bec22c docs/evidence/shell-design-review/build-9rbjw6vl/app-zathura.png
DATA ea4ec7c895a41d1650724e712607beb0c2ef0c6b9a18c104bbefb1ecffbf878c docs/evidence/shell-design-review/build-9rbjw6vl/files-buttons-before-gtk4-ini.png
DATA 9d3efc0ef39905ff634d3f3bd842cad02022d1ec894240c12760804639295ec2 docs/evidence/shell-design-review/build-9rbjw6vl/ov-2-after-side-tap.png
DATA 921656fafa16535c04dcbe8cf22c52b94a72b596d0a1ec601e8dc12891225fa5 docs/evidence/design-review-leftovers/build-qh3i7b3f/home.png
DATA 6af9d299f51851fa1f88dc0233920e6432cdc9b4421e53b550f8ca7f7c94403f docs/evidence/design-review-leftovers/build-qh3i7b3f/themes.png
DATA 2f99703c82316d3c4752faecfabbb59cd36a5e35ea04bc58357320ec21e8e3db docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t0.png
DATA e6035e1ecd65eafc79b32e6c978bac2c44da61262f730e48811b52dfdc7cbe79 docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t1-plus.png
DATA 643da8791a919160b1d0b84b58616025febcaf0674143ffaaf3b8f618e8c2712 docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t2-minus2.png
DATA 3963702782ed820274a077e7f8985bee545317fc43a8ae57193a1ac0e6c3f685 docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t3-start.png
DATA 643da8791a919160b1d0b84b58616025febcaf0674143ffaaf3b8f618e8c2712 docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t4-reset.png
DATA c85f4021902b8189254f6683290c85abc90314592827aebf283cd09a0b0070a9 docs/evidence/nrf9151/shell/host/cellular-no-sim-1232x568.png
DATA 799a4c333cd811e18a245e8c78d4321641617b7ac7099311fd81c1f378efdd9b docs/evidence/nrf9151/shell/host/cellular-off-1232x568.png
DATA b5f780d2421ceab8f1b00a930d4c4815334759d82099d4f7e5a83c4df14deea2 docs/evidence/nrf9151/shell/host/cellular-pin-1232x568.png
DATA 2219d75492bf0b6ea234d9394321c3c74eeb9444f59e0d31413eadfe6751ec22 docs/evidence/nrf9151/shell/host/cellular-registered-1232x568.png
DATA bd9ddb325b0de1968dfd44cbbfb1847186f9d340e3759a89211763db61051652 docs/evidence/nrf9151/shell/host/location-fix-1232x568.png
DATA 0e3a0380935ea6f252b3808669b10ea2ffc2395f6df929c9b0c2e13828fb41bb docs/evidence/nrf9151/shell/host/location-off-1232x568.png
DATA f2349ee140e8c47a067c17da59ada989de2b0b85623592568c8f56ecef1cdc64 docs/evidence/nrf9151/shell/host/location-searching-1232x568.png
DATA b5da8264118b3ed15c47ebedac04580ab237b694965508532880607783a4fb3d docs/evidence/nrf9151/shell/host/settings-no-modem-1232x568.png
DATA 3008eebb06ab7418fcaee1d030f688c0997b2628f6fac6241ccf4a90c9261804 docs/evidence/nrf9151/shell/host/settings-with-modem-1232x568.png
DATA c5addf45b783fa6bc7535490d240cf9b2ece6fa918f5c6e3d451a5c1cdcfe90e docs/evidence/nrf9151/shell/host/settings-with-modem-no-sim-1232x568.png
DATA 97ae17b3b6f5f9134bcac568a2b5da42fce12f1786bff574895fd80097d16e4f docs/evidence/nrf9151/shell/host/shade-both-off-1232x568.png
DATA 03ca1b30d63eccd95480330ce8c1bbbde74d70db7d2d60e5ab9d47097a77dbb1 docs/evidence/nrf9151/shell/host/shade-both-searching-1232x568.png
DATA 387a0f55f3eefe14779b63c7b8d7d0ad19c51d82e4ea96c7806a57e55f045e15 docs/evidence/nrf9151/shell/host/shade-both-searching-no-battery-1232x568.png
DATA b8a86e5bc1196becc6376911e78b5bae384f4d6fb70c6da5cafa62fde7ba857b docs/evidence/nrf9151/shell/host/shade-cellular-3-bars-1232x568.png
DATA f7ba6d11898be9a13ebf17d8f043b056e88d56ae483c138b7e4d715f231e33ea docs/evidence/nrf9151/shell/host/shade-fix-no-service-1232x568.png
DATA 97ae17b3b6f5f9134bcac568a2b5da42fce12f1786bff574895fd80097d16e4f docs/evidence/nrf9151/shell/host/shade-no-modem-1232x568.png
DATA 647017c9fd5c13394d9f802b8c33519a6b7cc1b755df662893b27b2710f3b0dc docs/evidence/nrf9151/shell/board/cellular-off.png
DATA ffe2aedcb932831363b5fe0f47672478f1cd1c960dce341b1ddc30ad2bcc3a7a docs/evidence/nrf9151/shell/board/location-off.png
DATA b7b162ede1268ba8152699d63252d77debbb00d04ac51b75fad0256b6c4ca2f3 docs/evidence/nrf9151/shell/board/location-on-searching.png
DATA 7fbef27941c78089dd1dfa23197585dd9555a255b61bae29fbfa15fa24d82535 docs/evidence/nrf9151/shell/board/settings-rows.png
DATA 4ffe1aee3d9c123f6a97264824126d2c830145dedafa22879e2155910f45224f docs/evidence/nrf9151/shell/board/shade-location-searching.png
DATA 555d3f164a39bf46442619ca1f809f2b799d8cc58325f3d22f70372c6f88229a docs/evidence/shade-pass/host/shade-modem-location-off-4-1232x568.png
DATA b05ead37b6e068cfc444d518712c8e18c86f3d806ea760557a9c1ff76eb2453e docs/evidence/shade-pass/host/shade-modem-location-on-4-1232x568.png
DATA de4e1a572029cd2dcba7aeab262ad9805beccc7bd304dcfa1abfde7596eed831 docs/evidence/shade-pass/host/shade-modem-location-on-4-568x1232.png
DATA ab62897f52ec497470d3d0f95fd012fb5341937b63e6ae7d6ad8cb251626e040 docs/evidence/shade-pass/host/shade-no-modem-2-1232x568.png
DATA 8c767bb158c66c366fc42370d088844df6a68c9dd53e8d66f50a431ddc74ffe9 docs/evidence/shade-pass/host/shade-no-modem-empty-1232x568.png
DATA 72f5b59602c2f755dfe7377fe6e361974799186b957e0d6152755cb7713f38cc docs/evidence/shade-pass/host/vision-100-shade-1232x568.png
DATA 4fb9f45a606c35906ae0088d5ccf40eb3a3e48631838343373a43c6754246e1a docs/evidence/shade-pass/host/vision-200-shade-1232x568.png
DATA 5a763fb2bd58bfaa97a1772cccadc9840a781494ef3afb05a3ad1cc55f611455 docs/evidence/shade-pass/board/shade-open.png
DATA 647017c9fd5c13394d9f802b8c33519a6b7cc1b755df662893b27b2710f3b0dc docs/evidence/shade-pass/board/tile-cellular.png
DATA 5932c81af1c19334cbd9743c6bb44b9a04ab07fda4afa2dfd6bcb106f430dba5 docs/evidence/shade-pass/board/tile-keyboard.png
DATA 87f59585fd05235620a5269a4bcf65d4a194d1bdab3e2015fe0a41137ab5792b docs/evidence/shade-pass/board/tile-location-off.png
DATA 3bc2788b3b27066248c37349f56d892822df1d24782e2b8a2bd62f60cbf4832f docs/evidence/shade-pass/board/tile-location-on.png
DATA a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6 docs/evidence/base-keys/board/keys-after-enter.png
DATA ee7513ae8fcfc031781673cfef7cab622fc831f615df553c9507c0bea46f6b12 docs/evidence/base-keys/board/keys-drawer-open.png
DATA 10f202da0963924b537d5a768e30ff7a30ae1309fb52204edbbbf8bec4c0ec0b docs/evidence/base-keys/board/keys-drawer-ti.png
DATA 97ca6176dfc6c5e8a5cdbe45e807840855e652b0ea29cad1c30245d3a4270b0c docs/evidence/base-keys/board/keys-overview.png
DATA fac69f720ae8595aa5c6c9e8fe1c404cdc6bbff7da2014b551a3f57ec3055661 docs/evidence/help-refresh/host/help-landscape-1232x568-end.png
DATA 4df953a8f63c648fb98e4d9b3f3384aa875ad7aeb4f9a0825ff1c264de0f3eb4 docs/evidence/help-refresh/host/help-landscape-1232x568-top.png
DATA b7b8131dadb638854b5f0d0cadb4cd8d4bf3588ea16c73134f3ff076cd5bce8e docs/evidence/help-refresh/host/help-portrait-568x1232-end.png
DATA e852cf5374353cfd8f06fab09aa5553df316da619c36590bafd73458bda0934d docs/evidence/help-refresh/host/help-portrait-568x1232-top.png
DATA cd13a6de926d5f23e04f9de840f731f55539da7a12a92cec4f9f2c49c0bc4f6c docs/evidence/settings-about/host/about-100-1232x568.png
DATA f4a36975306e53dfbab3d21ad7b03fdaf557ce399d69f3d397e60ea0168b15e8 docs/evidence/settings-about/host/about-100-568x1232.png
DATA 9466b3d658de0a0d4ec4c7d2b19ce60533b93f6794f4e6a9d2fad23528d14705 docs/evidence/settings-about/host/about-200-1232x568.png
DATA 439715e345321a22b333f73d4a91ce5dffdf616e985eafec9909d2819e2cd5a5 docs/evidence/settings-about/host/about-200-568x1232.png
DATA 8d3f07c82194d46c6cf1ec3e665d7800deabdcc4d3bebd032cf7070d0d51d293 docs/evidence/settings-about/host/date-time-100-1232x568.png
DATA 3061985905c888bfdda28d9aa59fdc9354e0b682d58f03527a32df8a8dbaa73e docs/evidence/settings-about/host/date-time-100-568x1232.png
DATA eba08d7e6fa17267dd36fc8f4947bd7353b7df4fd89a61b4678105ac9fe760f7 docs/evidence/settings-about/host/date-time-200-1232x568.png
DATA 1496cfa8ed436effba327ec09a5d3f2dbfa7a72355d7d92d82aa651fea3a26cf docs/evidence/settings-about/host/date-time-200-568x1232.png
DATA 35a944ae92b2c49f3f447a87e9cefe0500693680d15735ed3c156a87adcc07a5 docs/evidence/settings-about/host/settings-100-1232x568.png
DATA e44d2b81c60d348ba3e6c396d8cc13e16fd24bff9c9a8db6ae49ac5e9b0bd754 docs/evidence/settings-about/host/settings-100-568x1232.png
DATA 2813bdad2345e8a71f89c134e528744bfb3fb681acbc70c8a138e18eaf3185cf docs/evidence/settings-about/host/settings-200-1232x568.png
DATA 86aa7eca83e2fd517d58f9d26e9ee2d0b76818569bd2f43d2ef55ed0fd13e416 docs/evidence/settings-about/host/settings-200-568x1232.png
DATA 15dec396047d94d1aedf26f1ceb70dac174711285627106def9c585a1d65a0a3 docs/evidence/do-not-disturb/host/settings-modem-dnd-off-100-1232x568.png
DATA 2ad24f78fb2c4dc2f832491e6083f5b8fadbd0778bb35a00bbaab41d6b049da1 docs/evidence/do-not-disturb/host/settings-modem-dnd-off-200-1232x568.png
DATA 4684ddab1dda35dfc3f687c2bc5f0f546d06b06cbad24a0523368d0badc4cab7 docs/evidence/do-not-disturb/host/settings-modem-dnd-on-100-1232x568.png
DATA 2ad24f78fb2c4dc2f832491e6083f5b8fadbd0778bb35a00bbaab41d6b049da1 docs/evidence/do-not-disturb/host/settings-modem-dnd-on-200-1232x568.png
DATA bc448a0e7be03d738432bf3437ce21cfd3ed6f4e1242aa74aa02a1733a7b8e26 docs/evidence/do-not-disturb/host/settings-no-modem-dnd-off-100-1232x568.png
DATA fba3b014bcf4c6de0752258cfe8134fd2543c55f2b102e2bfa654327bd9fe513 docs/evidence/do-not-disturb/host/settings-no-modem-dnd-off-200-1232x568.png
DATA fee1336c96da1c6a42f26223a282bab45aecfef88432431f7ca94279154d8639 docs/evidence/do-not-disturb/host/settings-no-modem-dnd-on-100-1232x568.png
DATA c0fbd05aea4d7bb9e1f325f9c79d923d6562f35b76d397cbedd39d00dc9bc00a docs/evidence/do-not-disturb/host/settings-no-modem-dnd-on-200-1232x568.png
DATA 983767feab09655959f4b07df6ed880c8def0d67eb801762a79153e0f0f1e3db docs/evidence/do-not-disturb/host/shade-modem-dnd-off-100-1232x568.png
DATA 2ef0c71171fcdd5a83da761efa0b20d7d16813ca41c67840d305f76efa9904de docs/evidence/do-not-disturb/host/shade-modem-dnd-off-200-1232x568.png
DATA 606d263c15ff8f4308d023049ab462c7b0b08fd31ddc1e39b7c3c8343693e4d8 docs/evidence/do-not-disturb/host/shade-modem-dnd-on-100-1232x568.png
DATA 93c471d5a0aaccf4f87d2c818022dc51130d75c4309ac8f69f345a43b8295187 docs/evidence/do-not-disturb/host/shade-modem-dnd-on-200-1232x568.png
DATA 7155ae4fa8442848b6a58a7f126efc1a328101f6505ef1d5a46084283157ad7b docs/evidence/do-not-disturb/host/shade-no-modem-dnd-off-100-1232x568.png
DATA d1e08c6a3cfeea0b9d727ebe3da13ccf7d011c617b51957ba52323f900990298 docs/evidence/do-not-disturb/host/shade-no-modem-dnd-off-200-1232x568.png
DATA e76b806b6e6ab1feb082b3d61a64d7a2150ae25507bda362886f6833272245f7 docs/evidence/do-not-disturb/host/shade-no-modem-dnd-on-100-1232x568.png
DATA 55015f7afe14eb3039ac9c3748aede809a4763b8f5b08599506789fd7e21cdd5 docs/evidence/do-not-disturb/host/shade-no-modem-dnd-on-200-1232x568.png
DATA 92bd21cfb151dfd57daecc902631064f1fdf77b7fcfa0c6e01cf20c698e5343d docs/evidence/help-refresh/board/help-landscape-1.png
DATA 2d7b38beb80c40e57368e45d08aeae55f65adaa7df11b5a589ed82e749427ec3 docs/evidence/help-refresh/board/help-landscape-2.png
DATA b4da560e3ff60590e114fd9be71714ae1c4b9caa5d9568f7fbe089ef32f279c1 docs/evidence/help-refresh/board/help-landscape-3.png
DATA b4da560e3ff60590e114fd9be71714ae1c4b9caa5d9568f7fbe089ef32f279c1 docs/evidence/help-refresh/board/help-landscape-4.png
DATA 7b020e6c5d2966120e47ab8060047cb63c7cfb4bb073ea0399385c2a994c4206 docs/evidence/gtk-touch-floor/board/files-landscape.png
DATA 0972065dac53965f8d04136a7102a3a78654a41cde4cfd2e1c3cf3250a5e5f7e docs/evidence/gtk-touch-floor/board/net-landscape.png
DATA 9a8a1484c0bf835b8e1db51cba8fbd43db9304b806b09a87099ec158bafb59cd docs/evidence/apps-alert/board/banner-critical.png
DATA 9a8a1484c0bf835b8e1db51cba8fbd43db9304b806b09a87099ec158bafb59cd docs/evidence/apps-alert/board/banner-shell-claim.png
DATA b5a84ae6de237ea79d49c7d1968230ba1449d60b4a46877fc14c4b589abed1ac docs/evidence/shade-pass/board/tile-location-searching.png
DATA aa49129286a0bc7a64317e140d8eff66a333d683ebb3057d9d1709765057f428 docs/evidence/overview-all-apps/board/after-tap-drawer.png
DATA 228673f5089241367a5e42a2a220898d92b8b5d0ce09c25e7b48e64d3576798e docs/evidence/overview-all-apps/board/overview-title-row.png
DATA b2f023db4e9850349a87acdc556e3e592acde2a40cdfd574ac872ae6522476cd docs/evidence/idle-dim/board/after-wake-tap-on-video.png
DATA 72e64e56d9eb7291647bf4b5ef1031b0bda88821c444f8b17ae93690c936f51e docs/evidence/a-focused-text-field/board/overview-keyboard-lowered.png
DATA 4e2e9d23596e3775f1a6d44ae4ad1d78cbdf77f920f7c4f5de3d1dc294cbe265 docs/evidence/a-focused-text-field/board/terminal-focus-keyboard-up.png
DATA 9cb6b59a3a2c1f84a714320d30a57e93daea00191e1221d9fc0bdc08138f035e docs/evidence/settings-about/board/about-landscape.png
DATA a806edf12f14f2e36e7fdb7b6b944b6385cb104dc0a421e67f770cc5120f07f1 docs/evidence/settings-about/board/date-time-landscape.png
DATA 80010bf1889149b71c6214cd678e44e3deb640f066137e1654a17ec58ac7f67b docs/evidence/home-notification-count/host/home-count0-100-1232x568.png
DATA af9dad629c977316c22a67cb1b3b776ef7e6a2ec082d5134bcd39d400701f6d7 docs/evidence/home-notification-count/host/home-count0-100-568x1232.png
DATA 80010bf1889149b71c6214cd678e44e3deb640f066137e1654a17ec58ac7f67b docs/evidence/home-notification-count/host/home-count0-200-1232x568.png
DATA 2460a23bcf6640f7f0597b517b123329aae0e7a70cb638259730ebf38e8f80f3 docs/evidence/home-notification-count/host/home-count0-200-568x1232.png
DATA 13049fd83f80a62a1262ff3d5507525588fd63f3d0d2929c72678ad51700eeae docs/evidence/home-notification-count/host/home-count100-100-1232x568.png
DATA 512670ef6c0f2fe4ad35642e59c675be1e924348fa5525bb22c736eb6bf6483d docs/evidence/home-notification-count/host/home-count100-100-568x1232.png
DATA ab81f67c8fe591dd21b99d6344c5fa9efe33fb48b42b45b3cde75ffabdbe85f3 docs/evidence/home-notification-count/host/home-count100-200-1232x568.png
DATA a53fbcf615bdc46a19122de89fcbf6ed30f5d64fcda44c316fa5d25d2676de7c docs/evidence/home-notification-count/host/home-count100-200-568x1232.png
DATA ca476068973c1ab5d96817129fb129c8fa30c472e52fdd6be0441655d597b19b docs/evidence/home-notification-count/host/home-count3-100-1232x568.png
DATA edd9ea707a12271eded1a961224418217323d0677fd7d4be9865799fe82f8426 docs/evidence/home-notification-count/host/home-count3-100-568x1232.png
DATA d0971b44ef6604cc9f0b5c11d07586a3a03636d66c36b57df382e3b61c84fa2c docs/evidence/home-notification-count/host/home-count3-200-1232x568.png
DATA 01097affc6893ea9e3278d8ec8676e04926ca5489d0d343d25bca12c083a72cf docs/evidence/home-notification-count/host/home-count3-200-568x1232.png
DATA 945cb4443ee71bdec39ad1e2fef64607872b73d6a018be0478a728e22cefa191 docs/evidence/apps-alert/board/banner-timer-card-open.png
DATA f2ab317e35c30c7e9c7d88327eb66ced42332be2be79cc02132d11d2f21b7de6 docs/evidence/apps-alert/board/banner-after-shade-closed.png
DATA f2ab317e35c30c7e9c7d88327eb66ced42332be2be79cc02132d11d2f21b7de6 docs/evidence/apps-alert/board/banner-after-shade-ordinary-boot.png
DATA 36ad1f8093998f5f3d59d19227729d99b07c0beca28b5563410bc425997b7522 docs/evidence/apps-alert/board/shade-gnotification-history.png
DATA 0c07a5f9900750d6e2e7f4bf53225fce58ea25c7418ba67ca59b2db030352ee1 docs/evidence/apps-alert/board/banner-gnotification.png
DATA aa4d659e60e2c11e8da922f1b4ba1f1b74156b4d5b70fdc2781e105958da8a9a docs/evidence/apps-alert/board/banner-timer-card-closed.png
DATA 2ae369648201e9488c80979ce602087aa6c3de5717a0d0669cd8402beab4fd2b docs/evidence/apps-alert/board/timer-reopened-resumes.png
DATA 9f3c0ab48bd43a4750b9961fc4978f09108e55486834401b0b6eda50bdbb8186 docs/evidence/a-focused-text-field/board/timer-focus-keyboard-down.png
DATA e0628f324b14cc57e9417a21b67f3680c679af4e52176d8f4f60fda588aec89d docs/evidence/do-not-disturb/board/quiet-ordinary-no-banner-top.png
DATA 945cb4443ee71bdec39ad1e2fef64607872b73d6a018be0478a728e22cefa191 docs/evidence/do-not-disturb/board/quiet-timer-breaks-through.png
DATA b058ebff6eeaa61525733ce8256e7470f85e5ebd024c113e355c396d43dfb529 docs/evidence/do-not-disturb/board/shade-quiet-off.png
DATA c00d29cabbc74b916ed778d2a34e0a41abea9824d41184ec7603f80d5582fb5f docs/evidence/do-not-disturb/board/shade-quiet-on.png
DATA 921c91ba84c9a2d8bc3d2fcdfb8500a3fcea606edfc8fe8fcd0bb2e6ad4c7391 docs/evidence/home-notification-count/board/home-count-1-with-banner.png
DATA f0efd92d6bba85833b24a870b39797d45796c17095a4494883cc90ea087e62ec docs/evidence/home-notification-count/board/home-count-3-quiet.png
DATA 8b16c49b640f76d6be5603489d8b691ebb304fe2e8457e9cba9093368c8a81c4 docs/evidence/idle-dim/board/video-focused-playing.png
DATA e0abacfe4af194dad1d36ba3ebd1bc0db81889d1ef0b2119ff0cca3e65077faf docs/evidence/home-notification-count/board/home-count-3-2-cleared.png
DATA 704fc685540b6d5b80d2ed86e2f58a1015e79fe63e6301dd01faa9a595256943 docs/evidence/do-not-disturb/board/settings-row-and-tile-agree.png
DATA f84e898df83a60269a81e48c65b2a427551d67a0bee6cb1cb83e58046c8321b6 docs/evidence/a-focused-text-field/board/gtk-search-no-keyboard.png
DATA 7f87db522bd6faf4abd885b5d6d2ccc144c5b3b4b77a64ec018b834e6a8f1202 docs/evidence/a-focused-text-field/board/gtk-search-keyboard-up.png
DATA 4e147d7adf71287b85acd4520cf7f86128c921d6f5a15016842a4d93007ab7ce docs/evidence/a-focused-text-field/board/gtk-search-closed-keyboard-down.png
DATA 3a0f023dccc5734c7a1505817d7074cec3565d3a91a0b21392ac49175c512428 docs/evidence/a-focused-text-field/board/foot-typing-no-flap.png
DATA a43ab84ac42f8ff53470b7457ffc0a7062079e16e84a894c0eb633a59de5159b docs/evidence/home-notification-count/board/home-count-paging-and-shade.png
DATA 18503cd696af72eaf4e2bf09bccfc0a28d01d867046cde5a30dea50ca720014c docs/evidence/clock-display/host/settings-modem-charger-clock-100-1232x568.png
DATA b24c9e82ebdec6312c53dc2b6383afbc00b23082d2f57c28d9c15a450a7ffcbb docs/evidence/clock-display/host/settings-modem-charger-clock-200-1232x568.png
DATA fedb89f7175f65e28d8094b09d1aec18920295313b5bbe0fc4772cb2db5a9d14 docs/evidence/clock-display/host/settings-modem-charger-sleep-100-1232x568.png
DATA a7b22b301f436bc8a9d9728bfac5665b0f769f4bb08d43177c6c60e32c23787d docs/evidence/clock-display/host/settings-modem-charger-sleep-200-1232x568.png
DATA ced3dbed070f2c6544af0e655650e279edb58bbcc8ee5d9f636b73935cf0bb78 docs/evidence/clock-display/host/settings-no-modem-charger-clock-100-1232x568.png
DATA 7d64e3a4ba90c53b084eff25f7f3ecd5e7f19c4bae3df148fc05c17828d8d4aa docs/evidence/clock-display/host/settings-no-modem-charger-clock-200-1232x568.png
DATA 0135b004c98b8e966e35873b5944db39f8f10cd5c6cdece1cb2d572fba5ee102 docs/evidence/clock-display/host/settings-no-modem-charger-sleep-100-1232x568.png
DATA 802ee26b6d5412269cd2a136e10a96aed417a6c706fe7a0cbd478cbb646ebc8f docs/evidence/clock-display/host/settings-no-modem-charger-sleep-200-1232x568.png
DATA 2254e49d60b6e76e2165f749c8920d49655348662e07207ae5797fe576beaa8d docs/evidence/clock-display/board/docked-idle-70s-clock.png
DATA a5fb249aa9a39cc6db81dcf032c531990b1e1144a25f361f1c2324aea33201e9 docs/evidence/clock-display/board/first-effect-top-left-cursor.png
DATA 1c4caacf7439f364abe723f25da69267291e6c9e51b27a310e2b67bbefa6ef10 docs/evidence/clock-display/board/centred-k230-expand-effect.png
DATA 23927a2d1e9cccf4773df366e47f8e943408adf9f39676b388ade0cd265d2f3e docs/evidence/clock-display/board/centred-k230-banner-174021.jpg
DATA 8804722be7641e327facab6b5f9e1694cbfa2f2aee5eef5ee0b8aedbeab15636 docs/evidence/clock-display/board/tap-closes-card-over-files.png
DATA 67e63eb27db01ffcc19d94d7b110e3ce6e9eea2f9ce289bfcfa8852025e24285 docs/evidence/do-not-disturb/board/quiet-before-and-after-reboot.png
DATA a4fb19ab2774388d6c22c726774c9ac4738086a6a6a9de00463fa22e78667fc6 docs/evidence/open-with/board/files-dtap-folder.png
DATA 3558f509fb40553a76c15ddee08e645cc763f9cfe491052fb6096e2338f2c5ea docs/evidence/open-with/board/files-dtap-pdf.png
DATA ab5a1211e9695364e4aa6e09535bba8ebecbfc8d19ee6a20782c794a97f07117 docs/evidence/open-with/board/files-dtap-png.png
DATA bc645c03983cdbff49931ed519aa674760c42f181b7119988e87b316e829ab60 docs/evidence/open-with/board/files-home.png
DATA 4e737d34cb70a7fe9e2df2fbb4ef68d63bec85a37c4d207e37aa765e0b1cfe6c docs/evidence/open-with/board/files-longpress-png.png
DATA a1156285e2904a96917d241cac8ffbcf717976ff0a69d11fc3314294c6634780 docs/evidence/open-with/board/files-open-with-list.png
DATA 8f4b6df4be7e88126d385c469f852afe0b3b48b3b355153e3890f55973bad7ee docs/evidence/open-with/board/files-open-with-list-scrolled.png
DATA 3558f509fb40553a76c15ddee08e645cc763f9cfe491052fb6096e2338f2c5ea docs/evidence/open-with/board/open-pdf.png
DATA ab5a1211e9695364e4aa6e09535bba8ebecbfc8d19ee6a20782c794a97f07117 docs/evidence/open-with/board/open-png.png
DATA fb06fb94750cc5fc7132f648028e07c6e5a523cbb5037fb4a4980b05efa585e0 docs/evidence/drawer-search/board/about-opened.png
DATA d4ff501cf6f6093d1dc311b1238e2fa90bf834583aa8abb5673a3336e9417bcb docs/evidence/drawer-search/board/about-typed.png
DATA 824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1 docs/evidence/drawer-search/board/osk-raised.png
DATA 20104e075089ee23fd7bd29d80d783bff6e72ae7c4701363bead07c57bf7ea35 docs/evidence/drawer-search/board/osk-te.png
DATA 4ac701d78889484debb9e1c7031496e77a9111cda391d7eb2fa71dbeb5a9c655 docs/evidence/drawer-search/board/osk-t.png
DATA bc4e05491816fd0381ab7479f3a1a826828a9a093df4d6638df4aa2906c79e0e docs/evidence/drawer-search/board/term-after.png
DATA 0974d81adcd6cb57f75f816ed3b1a28852f569989ec067c47c2193e8c5290805 docs/evidence/drawer-search/board/term-before.png
DATA a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6 docs/evidence/drawer-search/board/ti-opened.png
DATA a84b2af4f626e66bb0a061d41d72124bd430ea5a4620beab473f52991ba8c6c2 docs/evidence/drawer-search/board/ti-typed.png
DATA 2e9b9de52d48eb758f34d58207256e7fbcb3fac86b923686c7f0db1ab59b97e1 docs/evidence/drawer-search/board/wifi-opened-title.png
DATA 5b10ffef6f627e2e221c5025429a88257ec535ddff44313a29f39f122032eace docs/evidence/drawer-search/board/wifi-typed.png
DATA aa14e8407f0bca6a0dba1281a59f4e2cd862d0a0449750b0afc4de84ba59a654 docs/evidence/drawer-search/board/osk-bug-keys-after-enter.png
DATA 5128d5fce7c844fa623e089c6254e00200dc028d509b32d1235316dc6584bd8b docs/evidence/drawer-search/board/osk-fix-after-open.png
DATA 899bceb716007abd22c18adfebc4786d1db42e7f8c1599e2a64d5c6c4cd7b9f3 docs/evidence/drawer-search/board/osk-fix-keys-after-enter.png
DATA 5128d5fce7c844fa623e089c6254e00200dc028d509b32d1235316dc6584bd8b docs/evidence/drawer-search/board/osk-fix-later.png
DATA 824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1 docs/evidence/drawer-search/board/osk-fix-tapped.png
DATA 6f82c3e12c1a791527d1cf82e46a0c020af7eb5c21d4f94418a50dfb4b7cd18e docs/evidence/drawer-search/board/osk-fix-typed.png
DATA 824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1 docs/evidence/drawer-search/board/osk-raised.png
DATA 20104e075089ee23fd7bd29d80d783bff6e72ae7c4701363bead07c57bf7ea35 docs/evidence/drawer-search/board/osk-te.png
DATA 4ac701d78889484debb9e1c7031496e77a9111cda391d7eb2fa71dbeb5a9c655 docs/evidence/drawer-search/board/osk-t.png
DATA 5f46cefc1acdb313f64688c448d1c1cc3bd4c67d322c14dbe090a39d7361f873 docs/evidence/drawer-search/board/osk-under-drawer.png
DATA 324f2c4c41a65ecbac2cf194fd740b1ebee8390e8c5bd266beef8fe1850c77bf docs/evidence/open-with/board/files-stays-short.png
DATA 85f7fa0d98d8d5e6eb3dda2c79a100c3bf5f8a9cb76eaa032c34a0338df038de docs/evidence/open-with/board/viewnior-rotate-icons.png
DATA 5c580a11e0473ed864c890d72b86eac27d68dd3d08ecaa5b061f1578b016b30e docs/evidence/resting-display-follow-ups/board/clock-dot-0.png
DATA 8f4137e04f1b7571f4d8d0670466d048bc58901ebf2657c47b5b91bf1b41dde1 docs/evidence/resting-display-follow-ups/board/clock-dot-3.png
DATA cdad9e553f3d513f28b33aa9d1b60744fcaca7000a43e2ebb9121695271a9d37 docs/evidence/resting-display-follow-ups/board/settings-idle-rows.png
DATA 96c4071fd2bac7bffefda7761c1836a98e3362620ab06886925391a59b7aeef0 docs/evidence/resting-display-follow-ups/board/shade-clock-tile.png
DATA 670e0bc5d06dd3442f2adb071c9c6248832b6b8da0c485b73cf71dcda40bfa72 docs/evidence/resting-display-follow-ups/board/clock-tile-battery.png
DATA 0f150ae1e483e3c5f16fb0eeebac502a7d9dae3b83c826f252c8942cbb049495 docs/evidence/resting-display-follow-ups/board/clock-tile-battery-tapped.png
DATA 630806f60e55b9133c3e52db7bd4a1a3f762d89f229eaac3f90875de30c6971c docs/evidence/open-with/board/files-full-card.png
DATA ee7513ae8fcfc031781673cfef7cab622fc831f615df553c9507c0bea46f6b12 docs/evidence/a-focused-text-field/board/base-attached/drawer-tap.png
DATA b1eb68ec503f1e5a9abe40b356781fb49fc2b269104241eb793191e9a5fa46ac docs/evidence/a-focused-text-field/board/base-attached/drawer-typed.png
DATA bc4e05491816fd0381ab7479f3a1a826828a9a093df4d6638df4aa2906c79e0e docs/evidence/a-focused-text-field/board/base-attached/gesture.png
DATA 266249167404404b297e63352a2cd8a92e7c07bd32ba8f07059343566b80bbae docs/evidence/a-focused-text-field/board/base-attached/gtk-typed.png
DATA 8aac4e8af34c0feb4f1ffd08c83c94c1fdbaad11cb7922c816dd02d71d750bb7 docs/evidence/a-focused-text-field/board/base-attached/terminal.png
DATA b21e4a13398385ec0bca98caf796173bc6b6afc2c658c4c69d8f0f29f271686e docs/evidence/a-focused-text-field/board/base-attached/osk-typed-ls.png
DATA b7de5b5f60f5e8557d76abe378082f879362438fd771b6dc81634e308b852879 docs/evidence/help-refresh/board/help-portrait-1.png
DATA 4d99cafc7a9befb0b0687e448570cd7decfea1bc5017d5068f73190f45a7fc30 docs/evidence/help-refresh/board/help-portrait-2.png
DATA d33b368c2fc269e3f735efbcfb6c2f08d69874f01a9920b0a45f86496c789e42 docs/evidence/help-refresh/board/help-portrait-3.png
DATA 3bfd17d7c9701e4dd7347aa149f40b05f3d018ea6c6a99705e7cb5d38e39ccb9 docs/evidence/settings-about/board/settings-portrait.png
DATA 72c682ae4ad0d7725cf7ee2419625ddfbccc952ce8e4cadbe939356a0fc8bc7a docs/evidence/settings-about/board/settings-landscape.png
DATA 8988895e711fcd3b23f132d11dfe52f0f20f546b0ea78fb73bd9d9378260bd66 docs/evidence/settings-about/board/about-portrait.png
DATA 53c95d02b22e27f7611a2aa0e381bbb17ee678735f236649b25e850cbc66a80d docs/evidence/settings-about/board/date-time-portrait.png
DATA e4593e4358dbc9bddfe37b3adced8877f94131eb52ac034e4c9f8fe4d8775387 docs/evidence/do-not-disturb/board/shade-200-quiet-off-again.png
DATA c96425b5fb7e4eedc9c6fed9973c5e3494b437e209d1b2516e4e7fca8f56daf5 docs/evidence/do-not-disturb/board/shade-200-quiet-off.png
DATA 3a8597980c2d7babda0d46b8d6d98708c95f5e3a70cb0a7bb5746d67cbd87f20 docs/evidence/do-not-disturb/board/shade-200-quiet-on.png
DATA 47f43cfafed7267fcf37c32ce1eb4f4406498025c1da7079a8f31391085f01a3 docs/evidence/a-focused-text-field/board/base-attached/base-echo-terminal.png
DATA 3cde93ea0f347c4044ad22f79947032ee112f6b65d568078384321d766d7635f docs/evidence/home-notification-count/board/count-8px-before.png
DATA 2c960160ea76dc15f684488de7696f8d46f5a1308922592c84bb926c23cc1f66 docs/evidence/home-notification-count/board/count-24px-after.png
DATA ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286 docs/evidence/gtk-text-size/board/files-100.png
DATA a49355f58ae58ce7aadd60e689bd30861b12211fde63cf4b1e2ecdde8a21a5cd docs/evidence/gtk-text-size/board/files-200.png
DATA d74b7ff84919caf261dec14864a7ab743e6fdeacdc17e1bd379318a3a9cfe9d4 docs/evidence/gtk-text-size/board/files-old-config-loading.png
DATA 3f9d0d96a05413066dfe64384698342a86331a7519860c2859244fa1c07e25f1 docs/evidence/gtk-text-size/board/net-100-menu.png
DATA fa37d89428cb4942be14d61ab3cbc2e131f42d74cb1d7f939f1fe9ef1c1e2d7b docs/evidence/gtk-text-size/board/net-100.png
DATA 288157ea33cc4796876d3776cb0e4a761635bea426f5dd2aba733c0572ade5c1 docs/evidence/gtk-text-size/board/net-200-menu.png
DATA 48b323e7268aa04ed653de7cae0759d95970f4194995dfbaeaf0fab18f0fa654 docs/evidence/gtk-text-size/board/net-200.png
DATA 8aac4e8af34c0feb4f1ffd08c83c94c1fdbaad11cb7922c816dd02d71d750bb7 docs/evidence/shade-pass/board/ordinary-boot/boot-2867.png
DATA 275fe8f652588360252ded26f73a54eb834547b32ac80d940478b22f07c384fd docs/evidence/shade-pass/board/ordinary-boot/boot-2867-shade.png
DATA b7a2c501962463cdc82acc1580671567efa00f49906ef9b0a23c7aa70aade589 docs/evidence/files-app/slow-load/stock-loading.png
DATA ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286 docs/evidence/files-app/slow-load/patched-loaded.png
DATA ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286 docs/evidence/files-app/slow-load/system-build-drawer-loaded.png
DATA ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286 docs/evidence/files-app/slow-load/ordinary-boot-loaded.png
DATA 70f938e352231e8c5f2060b6a6f2e8a18037c8da13b8f54e76a0f4707e2cf85c docs/evidence/clock-format/host/date-time-100-1232x568.png
DATA 0d2d5567e01969fd5a6f5249a2361aad0bac46ef5c655f74aac3ffb66cf4dd17 docs/evidence/clock-format/host/date-time-100-568x1232.png
DATA cef29c9a0f6ba2e69df80c975e1bf3f6dcc126b71ad73aef91128f38c6e0e4af docs/evidence/clock-format/host/date-time-200-1232x568.png
DATA 2e38ee1899a4aa2ad29027ad33fd5f2e3fc2f90b4d5221d35861f7f9d318cafd docs/evidence/clock-format/host/date-time-200-568x1232.png
DATA d8b150502bd1efba570372524ef344963882935c5a95f779a12eb1f65c2556d0 docs/evidence/clock-format/host/home-bubble-100-1232x568.png
DATA 5aeb0d493d3781fafccc7f391b47ed508fa6a985d4d8e0ce625bcac0b59b89a4 docs/evidence/clock-format/host/home-bubble-100-568x1232.png
DATA 98141ece1b8acfcc98d4d4c55bbbf2b4d3ed22ed52f3fafb81fcd915c68548f8 docs/evidence/clock-format/host/home-bubble-200-1232x568.png
DATA db95218fcfe2c415e6f273bb1aeb7fc4eed5ef7b02de03d3bf81f6cbfd9602b9 docs/evidence/clock-format/host/home-bubble-200-568x1232.png
DATA b962cf4fef86edf4c26b900981363cd430c40f28673205fa11e82a15055e0678 docs/evidence/clock-format/host/home-dot-matrix-100-1232x568.png
DATA d73a2f09abbde3e8fe7cae79a3fba230b068d5221860ac1573a1ea818bb5dfe5 docs/evidence/clock-format/host/home-dot-matrix-100-568x1232.png
DATA 8a52c2c69ec2bec2462c3c7253202ff25de0e913aedf58ef63df5539b76ce1e7 docs/evidence/clock-format/host/home-dot-matrix-200-1232x568.png
DATA 1336a38b34d97b85d581b31acafd495b89f224c62cadb028fedeefcd4614ede3 docs/evidence/clock-format/host/home-dot-matrix-200-568x1232.png
DATA cdc08d6da89e4b80f791f8eeea255fcaa1e66c6de8b9775855432390f539fe1f docs/evidence/clock-format/host/home-thin-100-1232x568.png
DATA 9b8e7c04b7c729d5acfd77302d0ef0e2ddad5e0c7210fcf78527b3a41cdcb368 docs/evidence/clock-format/host/home-thin-100-568x1232.png
DATA ed7d541dbcc536ea23b2a7c4db8061e9f187881b9110c2d9bf495c8d952d98e4 docs/evidence/clock-format/host/home-thin-200-1232x568.png
DATA 4a82174b3a3572b483f216ed775c32e7c5b3c30ba18cb8df4a4a46d029df1dfe docs/evidence/clock-format/host/home-thin-200-568x1232.png
DATA da118b47ca6d35e125175c95376d5f2530c81d0b096e365ae5b71a95cc61530f docs/evidence/clock-format/host/shade-100-1232x568.png
DATA 68ba0fa8e9393e034d20ce795302d35e4df5996511285dba278dd1e5360442ef docs/evidence/clock-format/host/shade-100-568x1232.png
DATA bdf0196eebf3870eb031c189a7da663f0ebdf157979d0b33879abe8aea823906 docs/evidence/clock-format/host/shade-200-1232x568.png
DATA c467bb52efc01cc48b818580016dd4f73699a5b47dc43629b151c52276e4262b docs/evidence/clock-format/host/shade-200-568x1232.png
DATA c7a9990a9ad519a472f109967724dda79ffd588111f9e9f724fbb9c8125f5bee docs/evidence/clock-format/board/clock-app-12h.png
DATA a786cf3934dd41af56fd5e54ff171724eddbc003a85e8bf8bc6e4d3cf3733a9a docs/evidence/clock-format/board/date-time-12h.png
DATA ee2d76db051a67ac80ebfb23ee7d48c617b5b91a0a72f03cd2659c7662d078a0 docs/evidence/clock-format/board/date-time-24h.png
DATA 2e9c19d1f3850cbb253550d9cf0eb5bfb8d4e027bc7abddab37606db6161bbec docs/evidence/clock-format/board/home-12h.png
DATA 3419f1f76acc0ebfc65d1db7d2f95bae864a8cac769b048dea2f9f9a3436d50c docs/evidence/clock-format/board/idle-clock-12h.png
DATA da9815f72c176b21fefd610fd39e2a8306327f644a67b29a04c487b71643679d docs/evidence/clock-format/board/shade-12h.png
DATA 2486277ce5d309fc856b62a8b85999f3931fca8d9c1f5db945fda2dc82f98002 docs/evidence/clock-format/board/shade-24h.png
DATA 9acd2bed1022d59ed6bbb18a3c963aaf7594da941c66dd0ad7058eaa804550ee docs/evidence/clock-format/board/shade-after-restart.png
DATA 426ddb2f197b9b76c2cf0428720f11121af32d139ec9977a7fbe061156e429c0 docs/evidence/clock-format/board/shade-after-reboot.png
DATA f23366a3fe42967983075726827e500dd3d267d27c79a078f0c890f49ebbd481 docs/evidence/clock-format/board/weather-12h.png
DATA bad249ac1a72a51da8e54c44406387e1f5c7cce27bc76bcda60ac66d2c36afad docs/evidence/time-zone/host/areas-100-1232x568.png
DATA 1fcc5cbebba96be09ec2eb3fe49f156663feef5dd5bd7336ffa5afca5855a4ce docs/evidence/time-zone/host/areas-100-568x1232.png
DATA 545f18ebed5132d151103ec1bc7aaa91882fc734c443fc0a5fd605e7faa67c3f docs/evidence/time-zone/host/areas-200-1232x568.png
DATA 800dd0a0b89897515d4109eaff95928839770422eb5e09f64806ab7d1892b3df docs/evidence/time-zone/host/areas-200-568x1232.png
DATA c6153e1a49708e678d96ad31d5160b5b94666970528ae70ed3e4d6bb3a103a14 docs/evidence/time-zone/host/date-time-100-1232x568.png
DATA aa541c6a578948c18e2cafaa11b35f1a628ff963954e854d0f810792956b0567 docs/evidence/time-zone/host/date-time-100-568x1232.png
DATA 52b65e948701b087ca743f6badbaab333f91bf787fac636c09fc936dc45431a5 docs/evidence/time-zone/host/date-time-200-1232x568.png
DATA 42e5ec730dd8fadf5ad738baeb3d73e252142f2dbeefda24b684d70ff79cb6c8 docs/evidence/time-zone/host/date-time-200-568x1232.png
DATA 03ec6fffb9198ec34006ef51b3b5c60d17de3bda42c78f8d81a3313ae6f3f4cb docs/evidence/time-zone/host/date-time-network-off-100-1232x568.png
DATA adcdb6546044fba42f9fe94cc07bd7ce0dfaa824aa94b08a1700ce7fb093cde5 docs/evidence/time-zone/host/date-time-network-off-100-568x1232.png
DATA cdedcaecaa8f4dc7ebd99486d3d196110bf2bab018e551d251deeaf2375cb23e docs/evidence/time-zone/host/date-time-network-off-200-1232x568.png
DATA d10e00173dabca7bf572b406a442a5211ebbe26111d256ab48c6405c0411345e docs/evidence/time-zone/host/date-time-network-off-200-568x1232.png
DATA bff033edca3ac55f5d7008aeb199db2b8ce8747b3c39103989efcf8d7d5a9b07 docs/evidence/time-zone/host/europe-page-1-100-1232x568.png
DATA 6f19b3d3131eee0993315faec085c9f9173f2782d5d5ab0ccc20f77948ed14f7 docs/evidence/time-zone/host/europe-page-1-100-568x1232.png
DATA 6a91d06a83f5a0b218fce4d827632ce42366dd34058786c76e96b754d791c0dc docs/evidence/time-zone/host/europe-page-1-200-1232x568.png
DATA 96f0f8596c229365c0b36c3a946cc14b2603763089e8d55d6bb5d63cb1d37dd4 docs/evidence/time-zone/host/europe-page-1-200-568x1232.png
DATA 10e900c1a0e24918f70388aefc64135972ed062a0028ef6bfcf36ba2ebf582fb docs/evidence/time-zone/host/europe-page-2-100-1232x568.png
DATA ad608683fb9e6c2f1bba69f87a1f162285f05961120611828b300b477f0240a6 docs/evidence/time-zone/host/europe-page-2-100-568x1232.png
DATA 3dadd48d7000b418d72ec1c1692793ffe5ed849c2ac57df307666a2625a6826c docs/evidence/time-zone/host/europe-page-2-200-1232x568.png
DATA 30cc3802ef27fbdf0e7c41d9fed8dd979df778cbc4d8d928bd7b31d6b0971b73 docs/evidence/time-zone/host/europe-page-2-200-568x1232.png
DATA cb2bed6826b8ac07bebbecb5130bfd329a43f0eb16d8612d91fb6c80316ffba5 docs/evidence/time-zone/board/tz-01-date-time.png
DATA f7d7613d27999a164a9dd8eeae279191979ad8b1759f9f1e0b5ac53e32a627a1 docs/evidence/time-zone/board/tz-02-areas.png
DATA 8e681d41720f7ee58320fc67610cf43b1bd89a88f021dc39d22b2bffb61bc0b7 docs/evidence/time-zone/board/tz-03-europe-1.png
DATA 15e44bdff760367f35894641c25c51d4ea1c200f839daa0977d6afbfba4ffe77 docs/evidence/time-zone/board/tz-04-europe-2.png
DATA 17f1935ff386fc83518a9dcb32f64a1056845bd3d29c77e3b17b49f43c2cb31a docs/evidence/time-zone/board/tz-05-date-time-london.png
DATA 1af4237a65f066aab18a2bb41087c8c32ece215b30f1ea270126302a0d7dc474 docs/evidence/time-zone/board/tz-06-shade-london.png
DATA 134dc09ba5911187924bdab79317d2f8415797e1b9fe1816a8d18fed8759db90 docs/evidence/time-zone/board/tz-08-clock-app-london.png
DATA cc98d7f17bc149d9d1b83397db62e7860f8164dc2ba80b229fb75cc2d031741a docs/evidence/time-zone/board/tz-10-network-off.png
DATA 53cd47895761b1f174c611dfa88d7a75a5d6a1a8ec92c0de522a47a8db4cab24 docs/evidence/time-zone/board/tz-11-shade-after-reboot.png
DATA 55fc62e9b2af0e35ef7d2df82e9ecd912a28eac5024ccb2a4b436800331a0aed docs/evidence/time-zone/board/tz-12-date-time-after-reboot.png
DATA 074d24ce73861ccd2e7c4c01ee97943fe0e4bddcb20b45d0399c7f0aab9cd3ce docs/evidence/time-zone/board/tz-13-america-3.png
DATA e2d1d3f73c3b22becc3089e86350235fc91d31dc9a70db48c55b289e911f25f8 docs/evidence/time-zone/board/tz-14-restored.png
DATA 678367829bf66639c943f97576391d288f68e61dda66db7ec999c4e7c35fbbc0 docs/evidence/notification-actions/host/shade-actions-100-1232x568.png
DATA 9f8cdafb7e50f19be53f31d00f197f2a555254914059c9386a65ed3d1d3450a1 docs/evidence/notification-actions/host/shade-actions-100-568x1232.png
DATA 047c2616339b278350d069d5e899e6a9911ba08af72119d5db7a1bd302b58ded docs/evidence/notification-actions/host/shade-actions-200-1232x568.png
DATA 9b59aaf70f5e2090ac2ee43d219eb2da44891d89f26f93bcc297034bcfbaba11 docs/evidence/notification-actions/host/shade-actions-200-568x1232-scrolled.png
DATA b73e5e22cdf135f25ecc0bb9a5fdec208a043c22c0a43abd25a4c46c59c195ab docs/evidence/notification-actions/host/shade-actions-200-568x1232.png
DATA 1c5681a1da7b97f9134b358d775789eeb682f4609f5fa92439165fe6615e8e66 docs/evidence/timer-restart/board/tr-10-set-2min.png
DATA e8d06358d50e99e6da66362e826c3111dd0e9227a40dd91ef1e961f027fa25b3 docs/evidence/timer-restart/board/tr-11-running.png
DATA 580d03b18dcde77746a0859bee41c1b466062bb3a0a8a8e0dfe5d59eda4f197b docs/evidence/timer-restart/board/tr-12-shade-finished.png
DATA 9c7023203bc718725d99f2edddd8ca71144e5f62a69eb09f322eef938f1597bb docs/evidence/timer-restart/board/tr-20-reopened-adopts.png
DATA a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6 docs/evidence/timer-restart/board/tr-21-reset.png
DATA 01a84a243268886658f98dbee3a32f6bbb1bf6b015a4d9ce5a3c8301892ac850 docs/evidence/notification-actions/board/na-01-shade.png
DATA c6d0d1c54541827f945726bdf375fcf4ddcaf94a26b91bafa08c9918c845714c docs/evidence/notification-actions/board/na-02-after-snooze.png
DATA c6d0d1c54541827f945726bdf375fcf4ddcaf94a26b91bafa08c9918c845714c docs/evidence/notification-actions/board/na-03-after-swipe.png
DATA a59a8f680c2e8f23837f7c51db888580f94439fafe4b7662d82d1c976edf0f83 docs/evidence/notification-actions/board/na-08-top.png
DATA 0ada06ad166889c23312655338977a0c945debdb3d23075f25dbe56ddfb6ad2c docs/evidence/notification-actions/board/na-09-after-swipe.png
DATA ec33352904f609ea9a2011bc9c778ebae84bee96bb71a0cb35a693a73ecf38dc docs/evidence/notification-actions/board/na-10-after-restart.png
DATA 5cb895b8ed8376e0dc403566d5c7acdb5614b8032856a283565cfe76de99313a docs/evidence/notification-actions/board/na-11-after-open.png
DATA ba9ca84370dcf3083e2e8a6f00d866b79fe640baef49a83e17fe160d7e1ff2cd docs/evidence/notification-actions/board/na-12-cleared.png
DATA d83931bd84b2f22b006d9723d0bb3502da57addf5f67feeaaf56778ac6c9b7d2 docs/evidence/notification-actions/board/na-13-before-dismiss-all.png
DATA 3af44cf361cc8fa9bc1aa1c648885cbf18c4fba13057b10e3def76862ed002db docs/evidence/notification-actions/board/na-14-after-dismiss-all.png
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
| `docs/evidence/clock-restyle/board-panel-100-home.png` | 318107 | DATA | `10397318a531c607f6291ba17ea983bc7b0d32f27ad5e07d964dc269d236b505` |
| `docs/evidence/clock-restyle/board-panel-160-home.png` | 316731 | DATA | `34b645eed7ca5d4eda9062d1f56db2c689ed07b3e084097a28ecaf39e376fd05` |
| `docs/evidence/clock-restyle/board-panel-200-home.png` | 317949 | DATA | `1922e250fcd30619bd99cd9c3a3aaa55ca4e4b66f011a335268d1fcf277d47e9` |
| `docs/evidence/clock-restyle/host-100-before-after.png` | 177156 | DATA | `4fa62684019d7645bdd6a432367b0e24ad791e113db75fd3da0ebd1b70639c1c` |
| `docs/evidence/clock-restyle/host-130-before-after.png` | 199104 | DATA | `ee2ee568349d2934b8b8c6950b9278d9b0f41203f6b71ced033796e4bcbc8974` |
| `docs/evidence/clock-restyle/host-160-before-after.png` | 196462 | DATA | `a030cb1e75d983468dc23384351c0c4c411dac03ff5db25022e8f62bf3cf37c2` |
| `docs/evidence/clock-restyle/host-200-before-after.png` | 217616 | DATA | `e590ff3c14c7c08eeba6acc7ec745eb5f63e4e0b0ad46a88ecdad3d0903069ad` |
| `docs/evidence/clock-restyle/host-200-high-before-after.png` | 214678 | DATA | `9e258d5a07a483381d428302c67f39a9d8a799d94461e51d1ea4a86604f27f22` |
| `docs/evidence/clock-restyle/host-latte.png` | 362466 | DATA | `928965287512f34e9111f2428f00d97aed21ba3668557aed880f1d87cf336439` |
| `docs/evidence/clock-restyle/host-portrait-steps.png` | 262562 | DATA | `8e3fc56d90f9fb9b02d709dec1384e37a0b07dc2c6574334f2f3bcb80f0b5db8` |
| `docs/evidence/clock-restyle/host-retro82-wallpaper.png` | 698591 | DATA | `c8862c1934628c68c99651f932dc05a6078b6a9e1504ef8d2b5df9de63e1e177` |
| `docs/evidence/clock-restyle/board-theme-change-catppuccin.png` | 110054 | DATA | `65816b008ae9ef83de1cf0554ce401b813e1652890a3c62f80fafdff3488f154` |
| `docs/evidence/clock-restyle/board-theme-change-retro-back.png` | 329015 | DATA | `d57e58fa7477047188e3b5ae243dd40830ceaf2ab0baf2ada6a9c81d09567041` |
| `docs/evidence/clock-restyle/board-theme-change-retro.png` | 326474 | DATA | `1f89ef9f8642bb3962d9ebc4324e5c4585e3504a8f82388112d8bb88efdcbbe5` |
| `docs/evidence/coherent-shell/accessibility-scale/board/01-settings.png` | 53914 | DATA | `eb97830d3b2c407b8a1a9559f4547c5faf30a528c36085c065ede0d2971e5eb6` |
| `docs/evidence/coherent-shell/accessibility-scale/board/02-vision-default.png` | 18953 | DATA | `067bdb088d7d3b137a2586058819ab40830bef98aab4bf2daca440413794e7a6` |
| `docs/evidence/coherent-shell/accessibility-scale/board/03-large.png` | 26944 | DATA | `1052f94fa56517b0116ce10500455c31e71e37504080bdea57fe91a6eff8d4f1` |
| `docs/evidence/coherent-shell/accessibility-scale/board/04-both.png` | 24154 | DATA | `cff3cb07a0352355135064f7bf06cab6bce6205543e5a887a463009c5d256634` |
| `docs/evidence/coherent-shell/accessibility-scale/board/05-both-settings.png` | 59433 | DATA | `8561484aa92a536a8f8e77b2af098c6e7652ce0d208ab757b0e4e3636825435b` |
| `docs/evidence/coherent-shell/accessibility-scale/board/06-reboot-shade.png` | 101199 | DATA | `cc1ff616181a6d33ad9c18698d485ef00d7cdd4eed46753110efcb254866ee76` |
| `docs/evidence/coherent-shell/accessibility-scale/board/07-reboot-vision.png` | 20059 | DATA | `8f4271009116c7434853a184bd2abed64268f5c1f906004a1d49a56a1237876e` |
| `docs/evidence/coherent-shell/accessibility-scale/board/08-restored.png` | 22641 | DATA | `a78135472bc20453af4e66d04d2f763213c9af1957e9d77cf8537cba28d5d2e9` |
| `docs/evidence/coherent-shell/accessibility-scale/board/09-panel-home-ring-overflow.png` | 324165 | DATA | `de500f127e58fc24ef83bd2edfe1900261d6a860bb783220edebebe3f5d44b78` |
| `docs/evidence/coherent-shell/accessibility-scale/board/10-panel-shade.png` | 28458 | DATA | `aa00afa77299964895e68c6109bc7a25e917f0ef1b570620adbe0b36710bc9dc` |
| `docs/evidence/coherent-shell/accessibility-scale/board/11-panel-drawer.png` | 110542 | DATA | `ad27f354a55b2b54eded7af38c6789f81a1a4f63e875f01ee94346e610070ed1` |
| `docs/evidence/coherent-shell/accessibility-scale/board/12-panel-home-ring-fitted.png` | 322335 | DATA | `791fcff532c7c076224578d631b6587bbe1450ef8be4c3a129863d27fcedd180` |
| `docs/evidence/coherent-shell/accessibility-scale/board/13-panel-200-home-before-widget-fix.png` | 324847 | DATA | `1c57ab07f2058492b26073f4e2834ec15378cf9fb3e1438e93d7d4cf5858c0de` |
| `docs/evidence/coherent-shell/accessibility-scale/board/14-panel-200-home.png` | 315250 | DATA | `59d901943da9ae4b13f66046e22040ad3468464a95cce481ed3023fca6fd5cc5` |
| `docs/evidence/coherent-shell/accessibility-scale/board/15-panel-200-drawer.png` | 51395 | DATA | `e5e9fead973ff511aa531fff97dc634d474ab1146e195a40a52bc27f68549112` |
| `docs/evidence/coherent-shell/accessibility-scale/board/16-panel-200-shade.png` | 35545 | DATA | `dabdc3a817ab2e5cf7f92f0a20af8d014e2e9b3a785a74f98ccc8d58acd7db04` |
| `docs/evidence/coherent-shell/accessibility-scale/board/17-panel-200-settings.png` | 54967 | DATA | `9dc943b483576575d6c0246858994d4538c2f00c300b62f284d07f09821bccd7` |
| `docs/evidence/coherent-shell/accessibility-scale/board/18-panel-200-vision.png` | 36936 | DATA | `081748268574b23d1a2c566e0b1e90adc7795179eb7d7241d982307f718a1683` |
| `docs/evidence/coherent-shell/accessibility-scale/board/19-panel-160-home.png` | 313297 | DATA | `0e296b6de50c1d1f35094a9ee3065c3aa00719aa2e4d5592ea6bc7d90589cd60` |
| `docs/evidence/coherent-shell/accessibility-scale/board/20-panel-160-drawer.png` | 64156 | DATA | `304ff44b7577876d4cb7027fca17dd8a55830c257d9cee75c803effcc004e3f7` |
| `docs/evidence/coherent-shell/accessibility-scale/board/21-panel-160-shade.png` | 31804 | DATA | `32ef2f1a1a209da25bc7d0cdc760dfd0832e4b852158442e439a88b689bbda75` |
| `docs/evidence/coherent-shell/accessibility-scale/board/22-panel-160-settings.png` | 49083 | DATA | `8b2170d72776931c93e7962d6c74775fff6a75b13f9441bf979eed5c1cb32e39` |
| `docs/evidence/coherent-shell/accessibility-scale/board/23-panel-160-vision.png` | 27067 | DATA | `df892e6f7500c072368526e0ce3803f1763064bc6e01d680dbdcfab5bf7c0502` |
| `docs/evidence/coherent-shell/accessibility-scale/host/default-drawer-568x1232.png` | 19931 | DATA | `bb12d1dff29516d0ccdda0d6dc101d4c1ea689c16e8bff8196a17601d71c63dc` |
| `docs/evidence/coherent-shell/accessibility-scale/host/default-settings-1280x800.png` | 39569 | DATA | `9ff798c8d1dbd81ec456a4e4dc7b2a60b868068372520fbd17b7c17c677a6099` |
| `docs/evidence/coherent-shell/accessibility-scale/host/default-shade-568x1232.png` | 41866 | DATA | `aec4b6cd890a30a32fdb64d8198b5ea0ba768ca332e2409855c72ffaefbe0219` |
| `docs/evidence/coherent-shell/accessibility-scale/host/default-vision-1280x800.png` | 22104 | DATA | `eb0966f9e06fb2fd729e399a95be0dc88b3bbde15b3c64ae3c9a6e9ef3aa6216` |
| `docs/evidence/coherent-shell/accessibility-scale/host/high-drawer-568x1232.png` | 19599 | DATA | `1c9722b94ae0ceb7794a06261355753f47fcf5af839c9ff50eb7cc03fb366747` |
| `docs/evidence/coherent-shell/accessibility-scale/host/high-settings-1280x800.png` | 36483 | DATA | `d59baab1b86d73dc76ee757b6b2e1a736192b30dc712cee7a69708199ad08b4e` |
| `docs/evidence/coherent-shell/accessibility-scale/host/high-shade-568x1232.png` | 38484 | DATA | `f7d7e549d62de45b1b966f6dfb6e37018eafc19f3a2beca5aab06ac99daa4b59` |
| `docs/evidence/coherent-shell/accessibility-scale/host/high-vision-1280x800.png` | 19398 | DATA | `20799378b0b226aa7d6e7c4b86b017b4bddbfb2bfec6fee8a77d439df21b2f85` |
| `docs/evidence/coherent-shell/accessibility-scale/host/large-drawer-568x1232.png` | 21713 | DATA | `cecaba3362fcf98c497ba5003e6d9b06567300c382f392588f64c48b5c44eb2f` |
| `docs/evidence/coherent-shell/accessibility-scale/host/large-settings-1280x800.png` | 46948 | DATA | `8c12a940d3d9f450e6242a11b351c7f67b4562851035d6f97781a3f85be17854` |
| `docs/evidence/coherent-shell/accessibility-scale/host/large-shade-568x1232.png` | 50762 | DATA | `7a80080d9cc38fa489186c9cf36c783b260053bfae53d386608db32ca76b67b2` |
| `docs/evidence/coherent-shell/accessibility-scale/host/large-vision-1280x800.png` | 26679 | DATA | `f9aa254f793aea91f9d252f9b7eca5ac74e55b2398b7dfb500d22c598f536f27` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/drawer-landscape.png` | 154897 | DATA | `b57527ed8b935caa251d4a3c3d03415d2e2d3cb93ebbce4a5b1d2c428eb47080` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/drawer-portrait.png` | 158362 | DATA | `41d8d67c9106929727b05681ef330e9714424d6c889e29265416ad7745521f57` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/settings-landscape.png` | 200757 | DATA | `ec16c90d82f9148aa3149b9a9a3373763ef6ad2d2e88dcf2a6d90654add5e027` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/settings-portrait.png` | 216646 | DATA | `074a5e48c842ac24a4451bbc8dc593bd55bd1618c239c5388913dd8259d6c3d8` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/shade-landscape.png` | 253785 | DATA | `fc002a81567f1145d64fd114b4a4ea51688f9a5aaacbf2985c8e31985953a29a` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/shade-portrait.png` | 232360 | DATA | `552fd356cd0127033d99cf14d0c39ed47193592aaae4881a836059a5189b46db` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/vision-landscape.png` | 142581 | DATA | `cdfa8107560a13eef7f41cf821f258cd14ba4e7a5e3eab3f8b8ac8a66e97caef` |
| `docs/evidence/coherent-shell/accessibility-scale/steps/vision-portrait.png` | 145361 | DATA | `f389d7bff4f2709452e977f790ab05dd75ca34d4687ddb0e7abbcf4e0408c508` |
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

These nine PNGs are unedited headless QEMU DATA captures of public synthetic
blue/purple Wayland clients. The adjacent README records exact binaries,
measured pixel displacement, and the open physical-touch gate. The three
`regression-*` files are the fix/two-axis-entry-regression before/after pair
for task 4.8's reopened vertical-shrink bug (`regression-before-fix-up.png`:
buggy `05ff1810`..`88ccca15`-line compositor, top edge clipped to the output's
top; `regression-after-fix-up.png`: same gesture step against the fixed
compositor, top edge visibly below the origin; `regression-origin.png`: the
shared pre-touch frame both are compared against).

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/shade-quick-toggles/board/1-shade-open-1280x800.png` | 101182 | DATA | `ab692d4cf10500b1f737e07eedaa293c4019a690f6eaefddd3403187c81e9efd` |
| `docs/evidence/coherent-shell/shade-quick-toggles/board/2-kbd-on-1280x800.png` | 43732 | DATA | `607b5d2fa0da79866348880d213226bfa14bc8a7fb67167ef70a585a5aa1e77d` |
| `docs/evidence/coherent-shell/shade-quick-toggles/board/3-kbd-off-1280x800.png` | 101750 | DATA | `00a780185adb986b07179cadca333d913ae74e17bac542dc3afffa174cdd4a1c` |
| `docs/evidence/coherent-shell/shade-quick-toggles/board/4-kbd-unavail-1280x800.png` | 97515 | DATA | `5dfd00e95b0a2caa969b26e0c9122d43078ec45a17aff770330c0e00531c6920` |
| `docs/evidence/coherent-shell/shade-quick-toggles/board/5-kbd-unavail-tapped-1280x800.png` | 100829 | DATA | `dbd0c23161743e4fa646959d59e735417504bf8467e50aae56038ed595847ba6` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-0-keyboard-available-568x1232.png` | 31940 | DATA | `f09c700423f41faa8ad3ad498bc8eca54ae42c5b44f8f0e45fa8c33e9bfcfaf1` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-0-keyboard-unavailable-1232x568.png` | 26850 | DATA | `d7b177631a6cd72159e9f2496f5ba15cb1dc96a4dbd00cd87c185fce22c811c0` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-1232x568.png` | 59874 | DATA | `077089feb942b867b69e5b70f6701b0bee46ddbee07005d27fad8df49c32ccad` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-1280x800.png` | 68528 | DATA | `f6ed9b1cabf3b12a43d6be2f834e7b3706cc25f9bc11f1608fe231dbca6da57e` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-available-568x1232.png` | 54900 | DATA | `0795a42e09634432b9b5ce3b612f0a705a69283a45c9c81a3493ce5d07e9dfc3` |
| `docs/evidence/coherent-shell/shade-quick-toggles/host/shade-4-keyboard-unavailable-568x1232.png` | 53575 | DATA | `2b7f1d9461d73fe5bef505bba781a69a26b01d933188282340df0fceae44b06a` |
| `docs/evidence/coherent-shell/side-edge-back/1-shade-open-1280x720.png` | 53761 | DATA | `a923f91bc32054b92985b36ac490cc876a587938193b3ee31664d8e98fa0fdb5` |
| `docs/evidence/coherent-shell/side-edge-back/10-panel-drawer-open-1232x568.png` | 64156 | DATA | `304ff44b7577876d4cb7027fca17dd8a55830c257d9cee75c803effcc004e3f7` |
| `docs/evidence/coherent-shell/side-edge-back/11-panel-long-press-menu-1232x568.png` | 185893 | DATA | `d54b1413153069e85bf3a66260c3b506cf0ce484d2f9bf1ba079d8b31909a13c` |
| `docs/evidence/coherent-shell/side-edge-back/12-panel-side-back-closes-menu-drawer-stays-1232x568.png` | 65504 | DATA | `316eaadd642c70f771db6fac8f98fe386daf63dd7fe1307fe0dc2a858abd15f2` |
| `docs/evidence/coherent-shell/side-edge-back/13-panel-side-back-closes-drawer-1232x568.png` | 318993 | DATA | `bccb1b73882504d6f50ff58326dee2ff26bd0d5138180e721a0a4325609d43c0` |
| `docs/evidence/coherent-shell/side-edge-back/2-after-left-side-back-1280x720.png` | 707535 | DATA | `2d181a2927d4edbdf3a2ea92c87f049fb307940b4d5ebeb4c76a26d53e62869d` |
| `docs/evidence/coherent-shell/side-edge-back/3-keyboard-shown-swipe-not-claimed-1280x720.png` | 32476 | DATA | `82d010631988c5b7e6ddf21c414f01bfed772d95b7cb30dfc8b79be32ca06f17` |
| `docs/evidence/coherent-shell/side-edge-back/4-panel-keyboard-shown-1232x568.png` | 156587 | DATA | `90159f4d0e109d3bcea7e43475192eb2a70d5c5f3f97ab000210753c9b23ef6f` |
| `docs/evidence/coherent-shell/side-edge-back/5-panel-keyboard-top-pull-opens-shade-1232x568.png` | 28281 | DATA | `3f1c2a9d463503c376fa0b6745719017f5c33883a2f950dbdebef61a686cb2c6` |
| `docs/evidence/coherent-shell/side-edge-back/6-panel-side-back-closes-shade-keyboard-stays-1232x568.png` | 156587 | DATA | `90159f4d0e109d3bcea7e43475192eb2a70d5c5f3f97ab000210753c9b23ef6f` |
| `docs/evidence/coherent-shell/side-edge-back/7-panel-side-back-dismisses-keyboard-1232x568.png` | 322069 | DATA | `94c9f0e9c72180df1285874d58e1e8a078b52db25d77a4fb69e2d813621265b8` |
| `docs/evidence/coherent-shell/side-edge-back/8-panel-settings-1232x568.png` | 50169 | DATA | `05c42a66e1b7e442162994f261e40d0a19cb8f0ba2ba48b149680869c7bdb903` |
| `docs/evidence/coherent-shell/side-edge-back/9-panel-settings-side-back-1232x568.png` | 321109 | DATA | `5c8a10703c36ec7fe5be5eeb103f943ab5c778e38b2149179124e24baa652609` |
| `docs/evidence/coherent-shell/two-axis-qemu/regression-after-fix-up.png` | 5478 | DATA | `4eb5fe1db653b5681ffa848471dedfe8b53e543ec317ab1a6eb27d57f6eb187b` |
| `docs/evidence/coherent-shell/two-axis-qemu/regression-before-fix-up.png` | 5492 | DATA | `42310d94fd4f97d91f585c923824b9271e7a64bdab086d0e90361e9c987b5bce` |
| `docs/evidence/coherent-shell/two-axis-qemu/regression-origin.png` | 4877 | DATA | `8d4260d119614cceb872d1f6636340cdaf770fa0a640eceb57aa226684e70cd3` |
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
### Wi-Fi Settings paired headless QEMU captures, 2026-09-24

These nine DATA frames use invented network names and synthetic dark/light palettes. The adjacent evidence README records the exact Sway/Rust inputs and QEMU-only limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/wifi-settings/paired-qemu/wifi-auth-error-dark.png` | 56457 | DATA | `574ea4b392e0e8bdc4ee5b4f46d82b800d39c43b53e343dabe85adcaa23b945c` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-forget-confirm-dark.png` | 23775 | DATA | `05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-keyboard-gesture-disabled-dark.png` | 37014 | DATA | `6a93416bc16cd60e96bf196c42afe36d52b028a02efacdb204c6ced6fcfaf6f4` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-list-dark.png` | 37765 | DATA | `ce8dd44606ab1bbe450fa502853249e656e8aeadc50718dfc075a006c076d317` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-list-light.png` | 37243 | DATA | `10f0f24d1816e6ce1df6efa2f48a11acb0d9d1fd44f926fb6fabe7f4581fcda5` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-masked-dark.png` | 52870 | DATA | `2e0916e57186db62ee52ce18959612f7acab2a5620a61c8388d5742cf756ba8e` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-saved-entry.png` | 36381 | DATA | `dd3782ac477ddfce563d062bdecdef87a5939ce815e2849a30d75c7e8a41b675` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-settings-dark.png` | 40394 | DATA | `e8be5551a201b2278569864505f6602965511f222c838d349c99ebd1829641c4` |
| `docs/evidence/wifi-settings/paired-qemu/wifi-settings-light.png` | 39815 | DATA | `13b92f1aa8f676c535318a8b0143658763f43da0ac68dad91d4ca440b7ed277b` |

### Notification motion paired headless QEMU captures

These DATA screenshots and short video clips contain invented notifications in the paired Sway/Rust QEMU session. The adjacent README records exact binaries, injected touch commands, sampling limits and no physical claim.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/dismiss-after.png` | 56017 | DATA | `856747c4afd9f1a223a444dd1b76f1d6dc02e1ddfc9f45991cd00b175743d827` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/initial.png` | 56150 | DATA | `d791cade02dfde4cc02756193e080d52ac007b7e141a54aa531b1173e63dc289` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-coasting-next.png` | 58488 | DATA | `3a8d023504d8dc638c76a900081512cf36ddbaa2d7d334a6b7040e9cc61cb65e` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-coasting.png` | 56869 | DATA | `75052edc63e86795286dd26d45b195e3f75785da13ff10676bc405c6f2a6fe51` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-stable.png` | 57229 | DATA | `5332e5896c24821965190c7d69974fab359ecd627674c5c4522a0b884d974da6` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/scroll-stop.mp4` | 41753 | DATA | `c4d221cc28a7cfa31da38e818561449cc7cef2564c7ea7cc86ffa094f35164bc` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-held.png` | 56527 | DATA | `cb4d0b8a85f2511b3525bb5ff724eb65fcf6dc2bd31a73eca0f22c56a4965600` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-return-early.png` | 56192 | DATA | `0170c00341405479c590e2ded085f246f50e2090f77eb42fb5d79327675c07e2` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-return.mp4` | 33115 | DATA | `01252e5ea0c1c839cb8ec8143badb480636aa6e90b78ad8f17841e0022324672` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-vertical-cancel.png` | 56150 | DATA | `d791cade02dfde4cc02756193e080d52ac007b7e141a54aa531b1173e63dc289` |
| `docs/evidence/coherent-shell/notification-history-motion-qemu/swipe-vertical-held.png` | 57079 | DATA | `125bc691f5c0c8f7e426a80b5989fb4b4b45d21d44d4e476e4e6a13c62ba6462` |

### webOS polish review fix captures

These DATA screenshots are host-rendered and paired headless-QEMU captures of invented fixture content (no real networks, notifications or user data). The adjacent READMEs record commands and limits; no physical claim.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/webos-polish-host/dark/drawer.png` | 49067 | DATA | `7c0236199807eef7cb68e884233eb6e1f1560389e75685b01508f1d645c4cdbc` |
| `docs/evidence/coherent-shell/webos-polish-host/dark/preview.png` | 53939 | DATA | `d0ae67a92ccfd2f06d3ff5c9a05f0ddb36378a99c2cb4d501745cbd4d3588d98` |
| `docs/evidence/coherent-shell/webos-polish-host/dark/settings.png` | 43989 | DATA | `d6c24fdd4179650139fa605737d1e29644954662dd7dd1767e59771f2cbf95c9` |
| `docs/evidence/coherent-shell/webos-polish-host/dark/shade.png` | 31755 | DATA | `3dff33df910839c6557f58453fd75dcf0b7e348ddcd872d5611b155ce3d131fd` |
| `docs/evidence/coherent-shell/webos-polish-host/dark/themes.png` | 26332 | DATA | `ecd12bb4fa419db0c186dff401f8dcd0664a6adc71b1ac01537291a5bf5516d3` |
| `docs/evidence/coherent-shell/webos-polish-host/latte/drawer.png` | 48309 | DATA | `2ab25d61035dc47d48e37745bb4f767936f2aae35752fed285caad02a6a75756` |
| `docs/evidence/coherent-shell/webos-polish-host/latte/preview.png` | 55385 | DATA | `04064a159eebdce9c757511c53e3f5ec2ea4d063e5acfa0406d71b6234d2dc84` |
| `docs/evidence/coherent-shell/webos-polish-host/latte/settings.png` | 42505 | DATA | `1012e2c71c16d01e2af568de7bc4ba903eaa8ab47893cbeb0d3fe77c1cfe8b60` |
| `docs/evidence/coherent-shell/webos-polish-host/latte/shade.png` | 30494 | DATA | `7920b116374b6c36684c32205a882aecd21171f86c40ec314598261430fc2ab7` |
| `docs/evidence/coherent-shell/webos-polish-host/latte/themes.png` | 25666 | DATA | `7c9d27d5a13b8f9e0547c8e8fa3a66c3d2f666e32a3b425108265f674bc0791b` |
| `docs/evidence/coherent-shell/webos-polish-qemu/deck-home.png` | 13892 | DATA | `04bf07fc0c9b60b28662303751331092b5638d66ba48c70a26a0736c280bc0d6` |
| `docs/evidence/wifi-settings/webos-polish-qemu/wifi-auth-error-dark.png` | 56852 | DATA | `83f065a0dd69f605b51dadf1da77d48c628579d009ea4cd54087b229ada62a40` |
| `docs/evidence/wifi-settings/webos-polish-qemu/wifi-forget-confirm-dark.png` | 23775 | DATA | `05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d` |
| `docs/evidence/wifi-settings/webos-polish-qemu/wifi-list-dark.png` | 37770 | DATA | `de1da296526f5f6feb4d44972fc3ccd88ce495be38265a788e0463031faae405` |
| `docs/evidence/wifi-settings/webos-polish-qemu/wifi-masked-dark.png` | 52048 | DATA | `e683d14906b728e6a457af6ad47cb8821ab0d8af2f803234305bcd557a030de8` |
| `docs/evidence/wifi-settings/webos-polish-qemu/wifi-settings-dark.png` | 40215 | DATA | `95e428aaa17f01fc274d0b31ca17d057ae318904d54c58b0f4553bb4377db18a` |

### Wi-Fi Settings password field takes the system keyboard: paired headless QEMU captures

These twelve DATA frames use invented network names and synthetic dark/light palettes and prove the password field now takes real `wl_keyboard` input (typed through a `zwp_virtual_keyboard_v1` connection standing in for `wvkbd`) instead of the removed in-app keypad. The adjacent evidence README records the exact Sway/Rust inputs and QEMU-only limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-auth-error-dark.png` | 31461 | DATA | `ffe9f46b8af0617145cc5d61e1df064f82275791fe1ebf7a4765473ad5b434eb` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-forget-confirm-dark.png` | 23775 | DATA | `05ddd61c03d755945223c96e618001122c788bab01fe94c58e06ffcf5941059d` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-forgotten-dark.png` | 55018 | DATA | `0fc088b091ad33e55ebeee9a9eedb735eb02a16614fd782befafa765833e4ded` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-keyboard-dark.png` | 30206 | DATA | `178d4f30df386e01d30e6c4ac29f59462999b28a2b4baa32bfbf8061070767b7` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-keyboard-gesture-disabled-dark.png` | 56505 | DATA | `7216d43e5b904f28f587193a69aca9710c5ed0df45b96db6a6a286e4b1798add` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-list-dark.png` | 55015 | DATA | `0e169a208a7c78e4cd5fb5926fa1edc8150ba711a7b15dfc7dad300820665395` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-list-light.png` | 54053 | DATA | `e8955993f0bac62bfdab2337ccedf16d5cf3575da8d3ef134e896d82316bfda2` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-loading-dark.png` | 46904 | DATA | `9bce2b1fe7e1dc3d8508b8ef17be44345d1fff70c819642055d22bf370683866` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-masked-dark.png` | 26616 | DATA | `2e474fb8b208685dfd1aee5a7ab2e50d02fb5e633ad8ae2f8297c2e962b3dfba` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-saved-entry.png` | 36381 | DATA | `dd3782ac477ddfce563d062bdecdef87a5939ce815e2849a30d75c7e8a41b675` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-settings-dark.png` | 60071 | DATA | `9ec5bd480721d3fcba238e5229e9f8c06d92612249612b570215651f9f651ec5` |
| `docs/evidence/wifi-settings/keyboard-focus-qemu/wifi-settings-light.png` | 58571 | DATA | `c33fb0e35b6668a9ed563f128666aa2571554beffcede4a40801697ce5cb8be7` |

### Theme activation after the commit fix: native board captures

These DATA screenshots are native `grim` captures of the installed board compositor showing the app drawer under two themes. Fixture-free, no personal data. The adjacent README records system, commands and limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/commit-fix-board/drawer-catppuccin.png` | 38880 | DATA | `a61bde5110afc2a8affad06c7cfdd78190e9b2759563646d71a80f8105a3fc13` |
| `docs/evidence/omarchy-themes/commit-fix-board/drawer-community.png` | 40915 | DATA | `bc925fa4c5725f3fc35f682feb9f64869a300a786df0548b62329bcef4a9a75d` |

### Overview hides the Home layer: headless QEMU captures

These DATA screenshots are headless-QEMU captures of synthetic fixture clients showing the Home layer bleeding through the overview before the fix and hidden after it. The adjacent README records commands and limits; no physical claim.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-jobs/board-panel-settings.png` | 25482 | DATA | `a6246c66a56d7fa3c3fcc17a6c5d1038b243f76a95cbfbe2a4188bd1c14a8888` |
| `docs/evidence/card-jobs/board-panel-shade.png` | 28087 | DATA | `b5f5de398afffe85b8aabc759cc1192a4731b42217250459900b354c2d6af517` |
| `docs/evidence/card-jobs/board-panel-themes.png` | 83205 | DATA | `3ab9fff686da3c51ada7f76c07891e971f2ee0cd1f8507fa8bf8a92c95f9a078` |
| `docs/evidence/card-jobs/board-panel-vision.png` | 27186 | DATA | `d2318655f0617eb8a3eeaa7cd60c40a716cb0dd3e5b0d4cbca8aeb27ddd17834` |
| `docs/evidence/card-jobs/host-dark-default-landscape.png` | 146655 | DATA | `a5e85404002a301c945fdd3a80eeb878f9b0a37c9f60f07e7ded8c4c552d7d6a` |
| `docs/evidence/card-jobs/host-dark-default-portrait.png` | 175666 | DATA | `d198ed2f8ade0d14f595826bac42e2f943eab14ef73fc5fc638afc144c0dcc3c` |
| `docs/evidence/card-jobs/host-dark-largest-landscape.png` | 218874 | DATA | `1b2b279fa5c0735303795b0bdbaf6fa8bee94dbfc16acc22eb09d2c026912aab` |
| `docs/evidence/card-jobs/host-dark-largest-portrait.png` | 223608 | DATA | `f714891ec8d8502c12b70bb22c4773e839a474ff1dbd1fabde9174cbecc0434a` |
| `docs/evidence/card-jobs/host-latte-default-landscape.png` | 138593 | DATA | `ff3e1c3856ce9e963f05304f90ad0ac218dc834023cf0d9ddb91edd8578da391` |
| `docs/evidence/card-jobs/host-latte-default-portrait.png` | 170469 | DATA | `929a9cf9e33d008f9040e0be57c68ea4ac2b3afab0cb9403657548f1037f2714` |
| `docs/evidence/card-jobs/host-latte-largest-landscape.png` | 207003 | DATA | `35d6a5e23c99b9dc771c1b2a722ade827cdb365fe7997384b093a853a685ffd2` |
| `docs/evidence/card-jobs/host-latte-largest-portrait.png` | 215313 | DATA | `b398a501fe669fa51f7ff2593a046f8a7a41f2f0665ae1d4e6b328e3aff3874e` |
| `docs/evidence/card-shell/overview-home-bleed-through/after-overview-home-hidden.png` | 24294 | DATA | `2d4f8420c1db9d1f40c9217ee3d4ba646270226f2525ea4eeb8918a3e3cb50a0` |
| `docs/evidence/card-shell/overview-home-bleed-through/before-app-focused.png` | 7292 | DATA | `a4d56bc27c4eba894cb36931c3030a018f1d0945414129a800295786787dd217` |
| `docs/evidence/card-shell/overview-home-bleed-through/before-overview-home-bleeds-through.png` | 24358 | DATA | `a1a9df92965e1208b1f2bc1d3f1b20a7f1bc26d4f9d4322db2ec18ff47e618de` |
| `docs/evidence/card-shell/overview-home-bleed-through/entry-00-origin.png` | 4887 | DATA | `bfc76c3bdd2e5a8db51e19243912529761bf0c382c314e09b20573bc5800eb08` |
| `docs/evidence/card-shell/overview-home-bleed-through/entry-01-touch-down.png` | 4896 | DATA | `6586a5ab19bf085c36f82d397939157b112e08380e2d16367b746c9b8d7b659d` |
| `docs/evidence/card-shell/overview-home-bleed-through/entry-02-mid-drag.png` | 4959 | DATA | `857caa9d6ea4de5d6ae24a55b67f5a71368ff178d7cce9f84f72f284e988109e` |
| `docs/evidence/card-shell/overview-home-bleed-through/entry-03-home-idle-reveal.png` | 4706 | DATA | `5824d7199bb74acd571aa8a0e7bbaa986f664e10fdbdcec5e9e91570f9db3a98` |

### App-switch neighbour full-output clip: headless QEMU captures

These DATA screenshots are headless-QEMU captures of synthetic ordinary-maximized clients during a held injected bottom-edge drag, before and after the neighbour clip fix. The adjacent README records commands and limits; no physical claim.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-shell/app-switch-neighbour-render/after-full-neighbour.png` | 4925 | DATA | `e25dd43c6c9aca1f1dc57ace48a2de2a682760c5d35c095cd2536603e4e6761d` |
| `docs/evidence/card-shell/app-switch-neighbour-render/after-held-1.png` | 4915 | DATA | `099a47af0e5726fe78af086c0dc9cbbad1b6f4a9c88b30bbdcba5e22f780c980` |
| `docs/evidence/card-shell/app-switch-neighbour-render/after-held-2.png` | 4932 | DATA | `55e6ebda0e06d3ccd1ac7b61a94a59912d993b69a30ac1ab97e7685b203d69b1` |
| `docs/evidence/card-shell/app-switch-neighbour-render/before-cropped-neighbour.png` | 4904 | DATA | `f338397d2cf535385ce1e57c85756685d8bdb4c62a0856d170be35aec0da312c` |
| `docs/evidence/card-shell/app-switch-neighbour-render/before-held-1.png` | 4905 | DATA | `07e481cec9ea72eb520c2ecc09c154e216d835381d54ac71b883c5f8e1364328` |
| `docs/evidence/card-shell/app-switch-neighbour-render/before-held-2.png` | 4924 | DATA | `1a517e2d67ae74efbc67de841187982617f3bff88b7202ee3a4dad08c14c3692` |
| `docs/evidence/card-shell/webos-fan-switcher/dark-01-overview.png` | 15375 | DATA | `e23a93dd46e8e71e426fe69a64ff62f5b25b6f21d6775569aaaf70d8416eb14b` |
| `docs/evidence/card-shell/webos-fan-switcher/dark-02-scrolling.png` | 12269 | DATA | `e9341f94a3051baf344738aa799a3efa0bd57d05a9e2c561ba281a291534ad47` |
| `docs/evidence/card-shell/webos-fan-switcher/dark-03-scrolled-settled.png` | 12274 | DATA | `6a367dc02f42de09ea0cf165fc85dc4f703b69c5c065097aef95671656d1451d` |
| `docs/evidence/card-shell/webos-fan-switcher/dark-04-after-close.png` | 15145 | DATA | `1352d062a802eddc0a63e4ef98b8be97d13bcf7d9900cf3c379ec361bdd46b2c` |
| `docs/evidence/card-shell/webos-fan-switcher/dark-05-opened.png` | 4889 | DATA | `ae096fe35939059f99ba5e8d4823874f05a0c3747b7f1e998e90e37c69c8d5bb` |
| `docs/evidence/card-shell/webos-fan-switcher/light-01-overview.png` | 15552 | DATA | `fa623975a65f8159a5af65638e0b946be46fbd74e881a358e5b7fbf5c93d270d` |
| `docs/evidence/card-shell/webos-fan-switcher/light-02-scrolling.png` | 12524 | DATA | `49fa7cae06dd6527a3b3d93520cd9dec7f237d19ae3d915a6846c89fa0ad5507` |
| `docs/evidence/card-shell/webos-fan-switcher/light-03-scrolled-settled.png` | 12587 | DATA | `b2093a6bba3df6b87f48da012dec01aaf350fafe2046489d41cc781b7f3663ec` |
| `docs/evidence/card-shell/webos-fan-switcher/light-04-after-close.png` | 15270 | DATA | `05afe2e3c70959c1c95ed4ce05b827f21ddd6a09290ad50a5aa2bdd4354a8118` |
| `docs/evidence/card-shell/webos-fan-switcher/light-05-opened.png` | 4913 | DATA | `c62d2f6b3a7fd1c4f6439955443fb0517524fb1c28617325865e24c5a0242c1c` |

### Tap-to-apply theme chooser: host fixture renders

These DATA screenshots are host-rendered fixtures of the one-page tap-to-apply chooser under staged Catppuccin and Latte generations. The adjacent README records commands and limits; no physical claim.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/instant-theme-swap/tap-to-apply-host/themes-dark.png` | 38562 | DATA | `a078dc50d948af4d6f87fb575a1f7ebefa25edfc39725ad8888b0a3311b810b1` |
| `docs/evidence/omarchy-themes/instant-theme-swap/tap-to-apply-host/themes-latte.png` | 38356 | DATA | `e1ceaff1e53e62ee75362838ed2cc644f76c452583e02b1f07053c69d134b92c` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/chooser-heading-tap-fit-1280x720.png` | 487886 | DATA | `09218a4f2d904716a63418e0ebc38cfc2d055350ffab11032bd0d65bb81531ad` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/chooser-status-overlap-before-fix-1280x800.png` | 525913 | DATA | `f5905b8474ee17347b47c5c10095b943e9c57a47bf9dd292ea306c99105cd4d1` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-center-1280x720.png` | 669944 | DATA | `ac3676b1a60096e88123ab3277054e999692f03b8697648009f4e984c9af5343` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-crop-1280x720.png` | 704983 | DATA | `58b186e46e68486485a3d4ad80bc5a662a2a28aa201c6d49f12d4db44cf31663` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fill-1280x720.png` | 695134 | DATA | `cfe77480071057630b90959f93fb44c86604770c00b147d9c7a1487a6dd84e24` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fit-1280x720.png` | 624876 | DATA | `0ece7fa2d055ee2280e571296feda685718121e5bdbd59c68e305fd40ae794ba` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-fit-after-restart-1280x800.png` | 745120 | DATA | `5381a73cd0ce1546f95ab5cd6ef593d9a7e7a241cdaeeb003636bc61903a89cd` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/dark-retro-82-solid-1280x720.png` | 80953 | DATA | `38b60ddf4765ade9f10446893749aa659a246e89b3175a4b61c5587f8fdabb9c` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-center-1280x800.png` | 168270 | DATA | `76e95966c4019a03ccc3cc96696469840f4105108d5ebf65413d0df68d7a05e4` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-crop-1280x800.png` | 195001 | DATA | `39e8fbfb80737619e0bfb4bf936f15110130caaf06ce880f3173936778230647` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-fill-1280x800.png` | 202004 | DATA | `573350f46079dcc3a805887d3aea0d690f22169dbf42b192216098921cb815cf` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-fit-1280x800.png` | 202560 | DATA | `3c5a18862d13d995e8a516eee806faa4e3507dff4961e57d9faea618037872be` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/light-catppuccin-latte-solid-1280x800.png` | 70398 | DATA | `19b3bf9816093b2c87c747b14c75fb9368a13b9cebf2f99e9c7608f262fca03f` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/overlay-chooser-1280x800.png` | 519960 | DATA | `ef9ef4431135292a7384a81178ec6f230ad203e5b90394d4139e706ce7681d23` |
| `docs/evidence/omarchy-themes/background-fit-modes-board/overlay-home-after-restart-1280x800.png` | 210287 | DATA | `45bd142c99c8c0f702dedcb97e98aa4c4ad78ded4bba9067f18dd535b69853fe` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-center-284x616.png` | 74738 | DATA | `c161b1bffe2cda61a86d35158caebf2d88e7791a16f1dc4394113a8d91650ac8` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-crop-284x616.png` | 82230 | DATA | `9d1f40b0512e74d6f37a55875c3a68588f1105305c66299cf31dd2939c458c46` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-fill-284x616.png` | 145945 | DATA | `485ff1a1ffcf84207e1a74173303c78bbd277bb77aa7dbfc02ea3e2f726ca2fd` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-fit-284x616.png` | 39927 | DATA | `a6335ab79253de2ac2a040d3be03c69745f86011cafbe3f27fae9cce4edfe666` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/dark-catppuccin-solid-284x616.png` | 5126 | DATA | `66f0984c785b5403a61c76e2fdaf796a25e7bbf8f0cf14126f0301edd41c8213` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-center-284x616.png` | 19970 | DATA | `23635218049dbdca1b4d493bec892daf44a027540c88519c545bfb4c57948cc0` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-crop-284x616.png` | 43731 | DATA | `6e3de80a94cf9196d2e6c5a5abcb03ba873062bb8e6ecb21afca95a6a6e1c3e2` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-fill-284x616.png` | 71298 | DATA | `9a87d376703dd3ff65675744ec5ee9d6e290cfb56651c8fcf5992b4cf52938a8` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-fit-284x616.png` | 43352 | DATA | `a614fd07d14cc7cc2b971491063a1b67e236cc88123168f15c253560f19d9e1c` |
| `docs/evidence/omarchy-themes/background-fit-modes-host/light-catppuccin-latte-solid-284x616.png` | 5125 | DATA | `e93c88cc87a33a2f8ca7fff624fcd9457f4c8746800f645d10aa9d7d2080e92b` |

### Bottom-band flicker before/after max_render_time: webcam frame sheets

These DATA images tile 16 consecutive full-resolution webcam frames of the physical panel's bottom end before and after `max_render_time 8`. The adjacent README records context and limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-shell/bottom-band-flicker/after-max-render-time.png` | 1760722 | DATA | `656e18b2eeb9bc304411d42cc656d366bd2e8947e7692536d3f1a36b2f8c7903` |
| `docs/evidence/card-shell/bottom-band-flicker/before-max-render-time.png` | 1552620 | DATA | `839c1f58897058e97e289553d97b636d8529743161aed19ef0f95326b1beea7a` |
| `docs/evidence/card-shell/bottom-band-flicker/hdmi-dock-band-phone-frames.png` | 927234 | DATA | `aaf18fc59dd1a5084642fbe5b699e3e8a0ed27aebbb95f138745fa90c81b7908` |
| `docs/evidence/card-shell/shade-backdrop-fade/injected-mid-drag.png` | 475810 | DATA | `f953614e47ffe4c6f174386ef1b3a5b2dc2a0aa2a9c793a1ff133b2c475ea5a2` |
| `docs/evidence/card-shell/shade-backdrop-fade/injected-slow-drag-2fps.png` | 2893980 | DATA | `9cad0390d86d67ce59d06acc430b99ee3aceee7f3592b5e31b814fe9ef664544` |
| `docs/evidence/card-shell/shade-drag-to-close/injected-close-sequence-2fps.png` | 1541990 | DATA | `c73761499696bd030d92b58e72a4640b749de53c6a187259879397a4b78ae8bb` |
| `docs/evidence/card-shell/bottom-band-flicker/without-kernel-patch-injected-gestures.png` | 1873557 | DATA | `cbc8370a74746d24a2467c4fe7dd31bf1fc9a14a28de4cfc169bc3ced7d18b9a` |

### Video card trap: webcam contact sheet (open / overview / closed)

This DATA image tiles 3 webcam frames of the physical panel: the video
trapped full-screen (the incident), the overview open with the video as a
real card (the fix), and the deck after closing it (video gone). The
adjacent README (`docs/evidence/card-shell/video-card-gestures/README.md`)
records commands, log lines and limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-shell/video-card-gestures/contact-sheet.png` | 1431358 | DATA | `94ad4dec646c0d8c58da8733b829f16576adc8a34912061a7bf71ba7861f4fb9` |
| `docs/evidence/card-shell/video-card-gestures/contact-sheet-overview-freeze.png` | 1429489 | DATA | `536397015eaaaadb79759c5abefe19f7d7c1ecbda9eeba2eecf1cf1d84f1e57c` |

### No video special-casing; generic live-card cost: webcam contact sheet

This DATA image tiles 4 webcam frames of the physical panel: video playing
full-screen, the overview open with the video's live thumbnail, a busy
non-video app (btop) shown live in the overview, and the overview after
closing it. The adjacent README (`docs/evidence/card-shell/
live-card-cost/README.md`) records commands, log excerpts and limits.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-shell/live-card-cost/contact-sheet.png` | 1089443 | DATA | `76883f6aba9647b6ba1a955827e81ff32958b1098926284f53584f3b6c0b63ed` |

### Panel power recovery camera evidence

Reviewed, cropped camera comparisons; commands and limits in
`docs/evidence/backlight/runtime-recovery/README.md`.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/backlight/runtime-recovery/cycled-26-128-255.jpg` | 19833 | DATA | `fd28b3884a4b4c93e4720a931c286dbcbc7e7339c1fa070fdfad6d8b547458fe` |
| `docs/evidence/backlight/runtime-recovery/live-26-128-255.jpg` | 23388 | DATA | `d2f33d7a70abbaaa6bc8f6e16e309536bbba828c6e51b3c8b63f269deaec3c92` |
| `docs/evidence/backlight/runtime-recovery/off-on-128.jpg` | 14111 | DATA | `53d41ebcc10164feb3cd70821119b7c6a83ce62b70c339548fe3b98764928d61` |

### Live HS brightness camera proof

Reviewed camera crops of the physical panel, with locked exposure; commands,
source and measurement limits: `docs/evidence/backlight/live-hs/README.md`.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/backlight/live-hs/live-26-128-255.jpg` | 21807 | DATA | `6b0475c77dce11a3802cbdb7a2c52ce91f803059f2160a02aaca08c6891889d8` |
| `docs/evidence/backlight/live-hs/off-on-128.jpg` | 15677 | DATA | `d05da3773efa0683dbebc6b3f176a8043af7b29cd08288fe823b4ce8f4fca196` |
| `docs/evidence/backlight/live-hs/settings-10-50-100.jpg` | 21907 | DATA | `2a6b3795cafc5e7ed9e70a957498807891e6b0a9585ea2637d80c38d388d4208` |

### Theme picker working-set board observation

Native screenshot and sampled native video. These show the preserved-theme
lookup defect, not accepted smoothness; see `docs/evidence/theme-picker/working-set/README.md`.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/theme-picker/working-set/browsing.mp4` | 376512 | DATA | `9edf97b5508b80673db74e264d50b99746f2b7774295b30aa2454c4017668539` |
| `docs/evidence/theme-picker/working-set/loading-backgrounds.png` | 117501 | DATA | `65c0660b3a9b4347fe64926128dbae7400bae6701df9a55df713ebc157cf773a` |

### Combined candidate brightness proof

Physical camera crops and an injected Settings screenshot; source, commands
and limitations: `docs/evidence/backlight/combined-candidate/README.md`.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/backlight/combined-candidate/live-and-settings.jpg` | 39326 | DATA | `1756635c6a3f7aea4e80caf0a8bf909d1211a0164c6c13e7499e5c594a985bab` |
| `docs/evidence/backlight/combined-candidate/off-on.jpg` | 15732 | DATA | `19e84e2647c7f0b7344e561002e5de9e600ba015f0ae2e4f36b622efb4f2a801` |
| `docs/evidence/backlight/combined-candidate/settings-ui.png` | 36724 | DATA | `0f55de68c97eff8199d8e2a8a789b87c391589085e90605531cfc556ba5d1a4c` |

### Saved bundled theme after store relocation

Reviewed native screenshot, injected Settings tap, candidate one-time boot.
See `docs/evidence/theme-picker/store-relocation/README.md` for limits.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/theme-picker/store-relocation/current-theme.png` | 301875 | DATA | `cca5e3950a6d3a739925272dc0e039f048f5364cc640c19b6ed6039d03224e6b` |

### Installed rounded-card evidence

Native screenshot on the normally installed physical system; static geometry
proof, not physical-finger motion acceptance. See
`docs/evidence/card-shell/transparent-corners/installed-system/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/card-shell/transparent-corners/installed-system/rounded.png` | 250980 | DATA | `5bb123a3d8c76bbdda5b2e0a88c9848c9d20cd4814fb8090e9fd2e389ea2572e` |

### Installed theme background browsing

Native injected-input board screenshot; saved selection stays unchanged.
See `docs/evidence/theme-picker/store-relocation/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/theme-picker/store-relocation/background-browsed.png` | 287514 | DATA | `ebc175d2acd4816f5ae26f54fcca81158565c499c88146b4b1d8e693931c8582` |

### Theme picker finger tracking trial

Native captures before and during a held 20-pixel injected drag. These show
geometry, not panel latency or real-finger acceptance. See
`docs/evidence/theme-picker/finger-tracking/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/theme-picker/finger-tracking/new-before.png` | 301875 | DATA | `cca5e3950a6d3a739925272dc0e039f048f5364cc640c19b6ed6039d03224e6b` |
| `docs/evidence/theme-picker/finger-tracking/new-held.png` | 300498 | DATA | `515448a93291c7f39ac2d96bd252dbded4fe3945d49f620122945c9ea0908d2d` |
| `docs/evidence/theme-picker/finger-tracking/old-before.png` | 298177 | DATA | `cfbdccacc6b3b43f12afd191b3823f8fc05f90f589f426fe3a53a2dc6f1d589f` |
| `docs/evidence/theme-picker/finger-tracking/old-held.png` | 276236 | DATA | `6b7f5e9626d4c26a47e31103209876acdc73d7d36865c5dae92610464d9ea168` |

## Background selection native captures, 2026-09-27

Reviewed physical-board `grim` captures with injected touch: Home before/after,
picker confirmation for both backgrounds, and selection after service restart.
See `docs/evidence/theme-picker/background-selection/README.md`. These are
image data, not executable firmware or real-finger acceptance.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/theme-picker/background-selection/home-after.png` | 785970 | DATA | `b822b4b32c6ce0ba6f90b203e1a61ed9736948a5fa614eefc6c5b7cf00c674fb` |
| `docs/evidence/theme-picker/background-selection/home-before.png` | 44478 | DATA | `b06525298d1317b37f8cec145127b13af5907a0f3837812dab0b848afc6f974f` |
| `docs/evidence/theme-picker/background-selection/picker-after-restart.png` | 313536 | DATA | `a1606e29a77f892d0500fcdbf35495136a1c1d8b625e0c0c0031ba1956664788` |
| `docs/evidence/theme-picker/background-selection/picker-alternate-applied.png` | 186967 | DATA | `4536c21f2c96e81b0b143238d2f067f4b60077765a8926a402b98f678480a20e` |
| `docs/evidence/theme-picker/background-selection/picker-applied.png` | 317404 | DATA | `9f6a4608fca4fcc74c14049acaf2adab50eca8878692835d07703f7553aba6e5` |

## Home navigation captures, 2026-09-27

Reviewed native board captures made with verified injected touch. See
`docs/evidence/home-screen/navigation/README.md`. These are image data;
real-finger acceptance remains open.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-screen/navigation/drawer.png` | 75729 | DATA | `72c95b4f6bb012234a29c2443e4d566e19189271230f5185caa8e17bc606f89a` |
| `docs/evidence/home-screen/navigation/home.png` | 26108 | DATA | `5b54afe2fa2681fe89d0c3486bf9704bd621bd4d5da156aa36b5ba9bff274b20` |
| `docs/evidence/home-screen/navigation/overview.png` | 16283 | DATA | `a02ac5e799c080f640123979e7c31e853ab3328870edb803c9bd2c1b659538d4` |
| `docs/evidence/home-screen/navigation/restored-terminal.png` | 8833 | DATA | `d52107ed6f51f9434beea6012fbbd0248f366fceea6d9bf38c71f7c46481c50c` |
| `docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1232x568.png` | 41194 | DATA | `955d4295d8e6dcf08c9f64aaa7b04fcc07731db5741c6c02897e88f9f4052fb0` |
| `docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1280x800.png` | 57802 | DATA | `555d78d07462a33db598cc5b87c97ebf3215997c7bfc38dd1243fd16fb691b1d` |
| `docs/evidence/home-screen/widget-picker-fit/host/widget-picker-1920x1080.png` | 69905 | DATA | `ff0b9adbacf9a19192e1941f9e4b5311b93f4259e3976c40d6c24639d50e87ab` |
| `docs/evidence/home-screen/widget-picker-fit/host/widget-picker-568x1232.png` | 61959 | DATA | `9962b8045bfecbea7ff7f5bd93fa6ee49eaae7a43f55352359dc6c1f0dab0090` |
| `docs/evidence/home-screen/widget-picker-fit/board/before-widget-rows-past-the-card-1280x800-grim.png` | 147834 | DATA | `ae87503b0e4edd6675c49e979b1d28d1eb44e964591546b0e23729bdd1a6b29e` |
| `docs/evidence/home-screen/widget-picker-fit/board/after-weather-row-click-1280x800-grim.png` | 807377 | DATA | `e037e9aa99953431e37c96db60382a1550c2363e9e0989976cdca1073d75a2e3` |
| `docs/evidence/home-screen/widget-picker-fit/board/after-widgets-page-1280x800-grim.png` | 237930 | DATA | `b8986ee027cb26e13b15cec247018664869958698bd6c6f2ca300adfdcaf9360` |
| `docs/evidence/home-screen/widget-hit-area/long-press-in-clock-gap-1280x800-grim.png` | 810838 | DATA | `1a3859a823e401a64123eb793af2c764025fbcbbfecc7f4784a8dd6c64a18430` |
| `docs/evidence/home-screen/widget-right-click/right-click-clock-rearrange-1280x800-grim.png` | 806296 | DATA | `97b7d126f407e0b8ac292b935fc6e65ec4ab7c41bd17159c31a83a9d1dc91068` |
| `docs/evidence/home-screen/page-settle/page2-right-click-1280x800-grim.png` | 818636 | DATA | `ef0a2f4190a3912f9fe60b5e8255be09ce09be200a4c204cf47b86eec1bedcc8` |
| `docs/evidence/home-screen/page-settle/before-fix-blank-vanished-page-1280x800-grim.png` | 762170 | DATA | `144823739da80239aa5460a0f0168345a2a3106d6596b9429ee1c8421816b254` |
| `docs/evidence/home-screen/page-settle/after-removing-last-page-widget-1280x800-grim.png` | 778835 | DATA | `6a8a491c6605b7539979ffebb43c8968eeaadf73e0b1455598685dcbfcf453bd` |

### Omawrite host and physical-board runtime — 2026-09-27

Omawrite is compiled from pinned MIT source; embedded fonts carry SIL OFL 1.1.
Both notices ship with the package. Host captures use headless Sway and a private
scratch HOME. Board captures use the physical panel output with injected input;
they are not real-finger acceptance. See `docs/evidence/omawrite/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/omawrite/board/home.png` | 25463 | DATA | `0fbb9697614b2e271a7982f02c3296fa4febf4333363d8b656e601f2f6f3ca18` |
| `docs/evidence/omawrite/board/keyboard.png` | 29886 | DATA | `afe1289aee3bde0c258340918783f0d77f1b437f6dd0be135bc722ec5daaf03b` |
| `docs/evidence/omawrite/board/open-dialog.png` | 22913 | DATA | `c96077d2ab5b3a018023c40470092f0a7b776477a44b10df80bc72e0efd0ec67` |
| `docs/evidence/omawrite/board/overview.png` | 22699 | DATA | `c50fc4d406ed540a96bbab5419505d128f47d40c85c2ccf595fd054ed809d52f` |
| `docs/evidence/omawrite/board/reopened.png` | 16873 | DATA | `315f096b76467534d380c55ce3138cb7b608f56d7a8cccfa461a8e0d0d820ee4` |
| `docs/evidence/omawrite/board/save-dialog.png` | 23574 | DATA | `b4b928946c4e72e92df8342fcaf91a65f8ea7f65bfb3297ebfffae7c0aa20c23` |
| `docs/evidence/omawrite/board/writing.png` | 16506 | DATA | `9059fe3be800fedfa5ca0c7abfcd79dabc0f94fdfbdf62ea21f3556455390423` |
| `docs/evidence/omawrite/host/keyboard-size.png` | 13089 | DATA | `8d1fc969c90546f9bb92e15906d0b37ccc79b301e3151c6021645f51fdf018fa` |
| `docs/evidence/omawrite/host/open-dialog.png` | 27261 | DATA | `4add3162608c3aee30e5e8b4913afdc57c5a3d733463ebd75d5529a6c8e0efca` |
| `docs/evidence/omawrite/host/overwrite-confirmation.png` | 35732 | DATA | `3ba194865ba72f16bbbb014d5c83b3b08ad80ca673215452649bbe0396a68fb4` |
| `docs/evidence/omawrite/host/reopened.png` | 20937 | DATA | `187ea627a844f0032897fb3d936021d08d6ab781088b535f9d95146f8ef49ad0` |
| `docs/evidence/omawrite/host/save-dialog.png` | 27883 | DATA | `d51a147161151986efe98d11536e0a7b773525bcda9dfec2726931bf55fdc214` |
| `docs/evidence/omawrite/host/theme-changed.png` | 14075 | DATA | `a0bde0d87901a0a6a0fa8abe1843d4535b8cdf65450cb8da18abeafe442dc86e` |
| `docs/evidence/omawrite/host/theme-dialog.png` | 30242 | DATA | `7b5409158b489163e5d453f0c80364e103792da3c126d0e04fe604622b9ddc70` |
| `docs/evidence/omawrite/host/writing.png` | 18244 | DATA | `fc9db149225963e8d76393b3de5bfdde0dfa89e2b8afd3ac98b6a92d70ded8af` |

### Brightness slider on the headless compositor

Host QEMU capture: injected touch drags across the Settings and Shade
brightness sliders, both routed through a real cross-built Rust client and
patched Sway under `qemu-riscv64-static`. Synthetic settings fixture, no
board. See `docs/evidence/brightness-slider/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/brightness-slider/settings-mid-drag-54pct.png` | 64405 | DATA | `2e2c4a9fcc2110d03fabac3f926171a656259026fa9d03dae8ab88e298e9af3c` |
| `docs/evidence/brightness-slider/settings-after-drag-90pct.png` | 64617 | DATA | `2349e999dcaf4284a54910bcff8809b7e6aefe51dfad6bae95d0f1fe4f0896ec` |
| `docs/evidence/brightness-slider/shade-synced-45pct.png` | 59251 | DATA | `e9fe967ebc8e42204ee39fd5f7fa1feec9048f78ae632de014097a066cb62157` |
| `docs/evidence/brightness-slider/shade-after-drag-90pct-still-open.png` | 59095 | DATA | `76383912cbc1241d553b2c6a122f71e1228fd54e0ba3b448f2dd49bc4cfa7d1c` |

### Power-key host fixture

The power menu screenshot is a host-rendered fixture, not physical-board
evidence. See `docs/evidence/power-key/host/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/power-key/host/power-sheet-host.png` | 32234 | DATA | `862c1e59404b041f72425d885943e82ac0d4942f204b2a98566894b8822a66be` |
| `docs/evidence/power-key/sheet/after-cancel-grim.png` | 15555 | DATA | `b0dbc0c909cb821e30f098c298649a599e5883800e54ee9d5f556b785551f7be` |
| `docs/evidence/power-key/sheet/restart-confirmation-grim.png` | 22180 | DATA | `35fc6ab0fcc71b3e5ea8bcb973a2b673eb7170f05218f1fe26b0e1e00eb88960` |
| `docs/evidence/power-key/sheet/sheet-open-grim.png` | 14636 | DATA | `2ec7df41782948f46baf959c568e4a64fb8e658c8e66e47cc3abb8ab9b7858dc` |
| `docs/evidence/power-key/sheet/revised-restart-confirmation-grim.png` | 20890 | DATA | `d498a3f28e3b2ddf552e261f73ec823fc24eb33b0bae68e0a02a42c0174623cf` |

### Volume slider and HUD on the headless compositor

Host QEMU capture (same harness family as the brightness slider's own,
`tests/volume_hud_qemu.py`): a synthetic `pw-dump`/`pw-cli` fixture pair
standing in for a real PipeWire session (`K230_PW_DUMP`/`K230_PW_CLI`,
the same environment-variable substitution `K230_SETTINGS` already uses),
a real cross-built Rust client and patched Sway under
`qemu-riscv64-static`. No board, no real PipeWire daemon. See
`docs/evidence/volume/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/visual-language-panel/board-panel-100-drawer.png` | 106498 | DATA | `d470fae779b6106d7c6cd59cb250d928f28c0e97f7f0192be618863933a1d4ee` |
| `docs/evidence/visual-language-panel/board-panel-100-drawer-roles.png` | 67654 | DATA | `976484f682c9a36422d53f52c6f967d0a6b910701e5c58df16b7ab1bfa8d3004` |
| `docs/evidence/visual-language-panel/board-panel-200-drawer-roles.png` | 33594 | DATA | `6cdb9a7768d00c85c01e951a6db5bd4af13cc7eeb767867020b63c23d5d744ae` |
| `docs/evidence/visual-language-panel/board-panel-100-home.png` | 325585 | DATA | `57c5b786d39209e28d67addb5c557f0d93e875a78483d7d7d403021acc9d7a71` |
| `docs/evidence/visual-language-panel/board-panel-100-settings.png` | 27635 | DATA | `ac5aa88ae6dadc73672c322a57ce91dbfd4216b4b64678f188c1c691243f6270` |
| `docs/evidence/visual-language-panel/board-panel-100-shade.png` | 13125 | DATA | `a51cada8f2a82729c14c2f1264cfb951e93776c00de0c1f4132575c3fbce22f8` |
| `docs/evidence/visual-language-panel/board-panel-100-vision.png` | 27186 | DATA | `d2318655f0617eb8a3eeaa7cd60c40a716cb0dd3e5b0d4cbca8aeb27ddd17834` |
| `docs/evidence/visual-language-panel/board-panel-200-drawer.png` | 51340 | DATA | `482d8a04f510b691584287b3225da562874dd15f8184ddf12e7a4415de17154d` |
| `docs/evidence/visual-language-panel/board-panel-200-home.png` | 332532 | DATA | `67306afb8745e6fe7f2eff6e0c2d3d324b3531d1c435e3f9a638db9fb5d86b11` |
| `docs/evidence/visual-language-panel/board-panel-200-settings.png` | 29304 | DATA | `a4ece9287f51c2d7583781013563932f9c92c04c7f686e7fe3b7ed82e7304435` |
| `docs/evidence/visual-language-panel/board-panel-200-shade.png` | 17744 | DATA | `6b8e7a461293f2ff62576ab4a5d0bda53835fb50c0f8c49cdc574183ec1f7beb` |
| `docs/evidence/visual-language-panel/board-panel-200-vision.png` | 41753 | DATA | `7b87bebba551c421c6a521324e524da735f8d333cc6449c179c4ab1894f098ae` |
| `docs/evidence/visual-language-panel/host-drawer-steps-1232x568.png` | 165256 | DATA | `e1b06b77e8d7b8072e5cd8b09aedabe4c094c5c719d8bcd5c1b90399b15a4bda` |
| `docs/evidence/visual-language-panel/host-drawer-steps-568x1232.png` | 187020 | DATA | `0074e6a96aaef045a1a3e41760cd2ba9ce75423028e3553cbb125e15ff902356` |
| `docs/evidence/volume/shade-both-sliders.png` | 60471 | DATA | `9d1ffe6cd11029eec3dc103a72a93d1c661362ed45127db426e94fe78a428b9d` |
| `docs/evidence/volume/hud-collapsed.png` | 60444 | DATA | `6afe4816bc6a66f409c5d70bff41ed94eb33d1034ebb93f05db303923632826a` |
| `docs/evidence/volume/hud-expanded.png` | 64958 | DATA | `1db2d849128d5574ea833cad147a4f75bcf3868ed3132fb7ed6b0a5b21a65401` |

## Widget visual redesign host captures, 2026-09-28 (revised twice: board
review round 2 dropped every widget's card background and rebuilt the
clock styles after design research; the filenames/hashes below are that
final round)

Host-rendered, not board or QEMU evidence: `cargo run --example
render_widget_evidence` (`nix/rust-shell-client/examples/
render_widget_evidence.rs`) calls the real, unmodified `render::paint_home`
offscreen against two synthetic `AppearanceSnapshot` themes (a Catppuccin
Mocha-derived dark palette and a Catppuccin Latte-derived light one, built
directly from `appearance.rs`'s own public fields, not a live Omarchy IPC
session this host has no compositor to run), composited over a genuine
Omarchy theme background image (`catppuccin`'s `2-waves.webp` / `catppuccin-
latte`'s `1-color-fade.webp`, decoded through the same `BackgroundCache`
the production wallpaper layer uses) rather than a flat color. The two
drag-mechanic captures (`dark-drag-edge-indicator.png`, `dark-drag-no-
room.png`) drive `HomeScreen` through its real public `down`/`motion`/
`tick`/`external_drag_motion` API, not faked state -- see
`docs/evidence/home-widget-design/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-widget-design/dark-clock-bubble.png` | 202589 | DATA | `2a827346e51964ed56484b701bd720287f3db5f10f773845bac25c0939faa5a8` |
| `docs/evidence/home-widget-design/dark-clock-thin.png` | 207521 | DATA | `924a309fa318f37dd57d80beec57c09b4bb30568370c47b08fecf5adc97551c2` |
| `docs/evidence/home-widget-design/dark-clock-analog.png` | 191612 | DATA | `1398af67e82fddbb1237622ceec17a1fad39e78ecee7594446d2cd9b05d0d152` |
| `docs/evidence/home-widget-design/dark-clock-dotmatrix.png` | 210538 | DATA | `7b9aac0da67ffd94d4341c930ed26032fa882cb3be44065f0229bc8bc5d4c125` |
| `docs/evidence/home-widget-design/dark-battery-present.png` | 199925 | DATA | `be4bb9f3177e475782a1570d1978cbe59e5f9bc6ea68a6d7689eb78c130d4dd3` |
| `docs/evidence/home-widget-design/dark-battery-absent.png` | 191743 | DATA | `693b0de82051da47e505b2cd987b16ee551265bc6171fb55a73e0826812e377f` |
| `docs/evidence/home-widget-design/dark-weather.png` | 204140 | DATA | `1e98894b8b078dcb74b6bbde47e0065c8389faf52f8be6e1a93ffe25e82773f3` |
| `docs/evidence/home-widget-design/dark-overview.png` | 225058 | DATA | `e23ba26c6ea31d98907fa9777862d538630b69072a6c22dc7ce93c1f65d891fd` |
| `docs/evidence/home-widget-design/dark-widget-picker.png` | 128368 | DATA | `2d64b6efc8a868f958df8ef7adab930ecb5f6a6c8cf2bc4423985021b3ffa172` |
| `docs/evidence/home-widget-design/dark-drag-edge-indicator.png` | 187800 | DATA | `4981926068b22c68ee61c61b11e13be7589c243086b5c83b3830e0d05840d574` |
| `docs/evidence/home-widget-design/dark-drag-no-room.png` | 207810 | DATA | `b3b4a5cb991f4aeb1175625c52b7acff6df77c39a81a1d080baa33b1029910b3` |
| `docs/evidence/home-widget-design/light-clock-bubble.png` | 83918 | DATA | `2f7f323fd3a809fe0db577b2d831d9a5d2c1099a8c743970967d880384f8fdb3` |
| `docs/evidence/home-widget-design/light-clock-thin.png` | 89672 | DATA | `44315e00614738c83c9854879a5177ce8625e94f2aed87bf43e19a7e6f223679` |
| `docs/evidence/home-widget-design/light-clock-analog.png` | 72964 | DATA | `03c49c1b67ab215b4ea175ff600c7598a52bda59f0b004a81e3d3c13d0cf909c` |
| `docs/evidence/home-widget-design/light-clock-dotmatrix.png` | 96003 | DATA | `8eb5077bd38fe42a124a5f498a6a23ef689e4f5918f2148b851c046479ef4e30` |
| `docs/evidence/home-widget-design/light-battery-present.png` | 81211 | DATA | `c315804f242a56ba94b303010fffdba6ad44b27140d008725aad444414ed2107` |
| `docs/evidence/home-widget-design/light-battery-absent.png` | 74123 | DATA | `400f8cbcca06a5a2224205a5d071fbaa2d4c47277c6e838a34d84e910d84b008` |
| `docs/evidence/home-widget-design/light-weather.png` | 86388 | DATA | `78843e3a5835a341a2fb9801fc3c367b9e74ff8ff56be3b10c6757950a44f847` |
| `docs/evidence/home-widget-design/light-overview.png` | 118568 | DATA | `7480e53a2d166f6046ba735d5a47ee9fbbe9bf274054de367df87a8fd3abc747` |
| `docs/evidence/home-widget-design/light-widget-picker.png` | 86518 | DATA | `9b6f45195710d80e950dc8659a43e879cfe0b1ace4b0d579e0f5cb14a38caf03` |
### Files app candidates: dark/light theming, host-native

Host-native capture (NOT the riscv64 cross build, NOT QEMU, NOT the board):
the real, unmodified `pkgs.portfolio-filemanager`/`pkgs.nautilus` for
x86_64-linux, substituted from cache.nixos.org, run under Xvfb with
`GSK_RENDERER=cairo` and `GSETTINGS_BACKEND=keyfile`, reading a keyfile
produced by `tools/theme_gtk.py`. See `docs/evidence/files-app/README.md`
for the exact harness and the schema-path bug this run caught and fixed
(`nix/shell.nix`'s `filesAppSchemaDirs`).

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/files-app/host/portfolio-dark.png` | 20512 | DATA | `1edb7ac0fc9bd85bb2853bfb4013bf082e7a52ed29c47fae473972971a7445ff` |
| `docs/evidence/files-app/host/portfolio-light.png` | 20130 | DATA | `373198612a7a7ae65d933697b400d952c5982415e4fce232c827a57bff3cae8f` |
| `docs/evidence/files-app/host/nautilus-dark.png` | 21129 | DATA | `6219142f5fed441b5021980b3c0f8383228f1417010bf8f9922ea936572a9b68` |
| `docs/evidence/files-app/host/nautilus-light.png` | 20000 | DATA | `b5c553f6b0d419371460c005b7aaaff96ffce504794591f336e113fb3f688b5e` |

### Portrait HDMI software-rotation scene: headless QEMU

Native changing-client captures under the real RISC-V Sway/Pixman scene.
These are test fixtures, not physical HDMI or touch photographs.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/hdmi-plug-cma/board-hdmi-plug-3h41m-black-bg.png` | 62064 | DATA | `3c2cf9367ad3ef90e23ac0e5c33deca77a5f848e789f3b98196567bec0e6afb6` |
| `docs/evidence/hdmi-plug-cma/board-hdmi-replug-after-fix.png` | 808987 | DATA | `028ac6897682a822685435215e03ad39bcb24bc2355e41c948fafc186be7485b` |
| `docs/evidence/hdmi-plug-cma/board-hdmi-swaybg-stopped.png` | 809063 | DATA | `dc1e82ff86948651d0d532605ed6598cbbcbc04c3e68af2310c803060c84e52c` |
| `docs/evidence/hdmi-shell-performance/scene/turn180-sampler-fallback/ordinary-a.png` | 8782 | DATA | `c84f70ac6b2178a285fcc3629a9345310784a4b79ea20098941bf3c7d7b4ef02` |
| `docs/evidence/hdmi-shell-performance/scene/turn180-sampler-fallback/ordinary-b.png` | 8790 | DATA | `b37fda708291fac1c44a0559dcafc37fee0505b2f6bacad9f82d88e03a5d4b5d` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/ordinary-a.png` | 10537 | DATA | `8c10dd5611d5b97754603642c6c3728fa3fa4bac939c51b8e75cbe093a046111` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/ordinary-b.png` | 10545 | DATA | `ccb7b0f8f15cadc823028d2f79f36c62a6481fa2c36009d0a6f3ae98b7950c9b` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/overview-a.png` | 20692 | DATA | `1f6a9dfc97ae02e42c44c6f4a4948155786cd4356d436493cf7cc474fb43c48b` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-quarter-turn/overview-b.png` | 20717 | DATA | `52067082bbf8cdd97ae1e8ca47fc85743a2cb43832de91770794472e3978a26c` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-sampler/ordinary-a.png` | 10546 | DATA | `254f10b379df10bc966aeab93e5e307f67c8030d0024cfe041bfaaf687ed27dd` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-sampler/ordinary-b.png` | 10554 | DATA | `e48de1f101b121ada8008b5cd592d01e71d2bad46d7e8cba930543b3fc0f76c2` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-sampler/overview-a.png` | 20714 | DATA | `fcb7183acd5da12e3be0d60d0d02a22f14406135f2657aad652e509785d7aed9` |
| `docs/evidence/hdmi-shell-performance/scene/turn90-sampler/overview-b.png` | 20672 | DATA | `5c3fe4dce16a82b17356398f7b070ec26c5dd17cb305ddd21ede874aa6058715` |

### Fahrenheit weather display evidence

Board-native capture cropped to temperature content; not executable code. Source and crop provenance are in `docs/evidence/fahrenheit-weather/capture.json`.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/fahrenheit-weather/weather-fahrenheit.png` | 70227 | DATA | `570d15376898cb6e6af36ff5cb3e54d9f434759ee2fde467efc198810ab40233` |

### Board pointer launcher evidence

Native HDMI screenshots from an injected Wayland mouse click; source, commands and limits are in `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/pointer-launch.json`. These are non-executable image data.

### Drawer search keyboard evidence

Native board captures, camera photograph and headless QEMU screenshots; commands, runtime identities and limits are recorded in their sibling README files. Non-executable image data.

| File | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/app-drawer/system-keyboard-qemu/app-focus-restored.png` | 5816 | DATA | `a7968af7e10d550affd1bddf59ec069c069caf2516af16a7003b224b37b279a3` |
| `docs/evidence/app-drawer/system-keyboard-qemu/search-corrected.png` | 25961 | DATA | `511b39b65e5210df3036f6f98c2e472acf293d0b75ced63150d2548ecba4ed0a` |
| `docs/evidence/app-drawer/system-keyboard-qemu/search-focused.png` | 46026 | DATA | `1d76f9906d40788df8f1d39ec9d731212e21b8d0883ed6ef9b04cf7583294152` |
| `docs/evidence/app-drawer/system-keyboard-qemu/search-keyboard-dismissed.png` | 9175 | DATA | `a42873650f6c21bc6d5febccd76fcee671c52d9bb08acbe13cc9adc97ff4c592` |
| `docs/evidence/app-drawer/system-keyboard-qemu/search-typed.png` | 27259 | DATA | `dc0bb35cd2db00175a49625c4cbfc35db455bd13029ea743254f52cba22b43cf` |
| `docs/evidence/app-drawer/system-keyboard-qemu/search-unfocused.png` | 48468 | DATA | `7898de9b3679b7c30a6411dcbe389493c787ab87dd9b785d6c376358eaffb497` |
| `docs/evidence/app-drawer/system-keyboard-board/corrected.jpg` | 80196 | DATA | `2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7` |
| `docs/evidence/app-drawer/system-keyboard-board/dismissed.jpg` | 60014 | DATA | `59882fcd6820777010fc0e6fb7d553d5fc85a9f1a2bf266af0a10b9774f33096` |
| `docs/evidence/app-drawer/system-keyboard-board/focused.jpg` | 80196 | DATA | `2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7` |
| `docs/evidence/app-drawer/system-keyboard-board/panel.jpg` | 42479 | DATA | `bf9fe2f637ce3ef69b37bbdb7fe37195e996d428cb028c88f67c7cab5579ac23` |
| `docs/evidence/app-drawer/system-keyboard-board/reopened.jpg` | 80196 | DATA | `2e2994f2ff284e86f704a3c77f32aeeaa12adc1a85d30882cf13b155cf2845a7` |
| `docs/evidence/app-drawer/system-keyboard-board/typed-q.jpg` | 45611 | DATA | `913ee16cc135ef498930ae55d25938f9920ef4f6265b2188ea3f3549258e672e` |
| `docs/evidence/app-drawer/system-keyboard-board/unfocused.jpg` | 60014 | DATA | `59882fcd6820777010fc0e6fb7d553d5fc85a9f1a2bf266af0a10b9774f33096` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-created.png` | 187098 | DATA | `9a91fa9debf2b38dd276966040b7c9a318de20f8044ab8e28a9eaae775dd0f98` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-open.png` | 90138 | DATA | `5df90eb3a83cd4f47427e690b64f742b7795daef9fde3269ae3f7c661721b400` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-rename.png` | 90156 | DATA | `828040b58ad7ad46924fc18d4bf5afad2ddf703037b7323a2ebf0d4a5bea7c22` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-renamed.png` | 89199 | DATA | `c32798981358a1dab29599d3437dd7d9ef0643a55d13f2fb28f65d327c9186d4` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-folder-member-extracted.png` | 191964 | DATA | `c0f16c81ef09b464beb034f86286782a6480032e5531906c87a81a60c03372a9` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-dock-folder.png` | 188701 | DATA | `741a8d2a5c2983fe01a883e480993b334179134a9a926fa350fe30b698ccaf59` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-picker-widgets.png` | 102839 | DATA | `1f13d06090c24cc8eec0535f2ba2930e33f2e03263599eb589160e022c0982b2` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-clock-widget-placed.png` | 183960 | DATA | `3fb3ce1e8b330e3fd455a2caf53aea7b67b07baed43260c4f31626948110172a` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-dark-after-restart.png` | 182811 | DATA | `bbe2a1db5210ff7da9a821583e2232e4e27f884adaa0ab550def78f4598b88f6` |
| `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/home-light-page2.png` | 70711 | DATA | `032f6ab6426c97cdb08ecdb95a32b2c27ed32b848c50d0a747ffa83a91190a4a` |
| `docs/evidence/home-widgets/clock-date/board-panel-100-home.png` | 316740 | DATA | `7cade2185d5426edfd571520dbab37cb60a04256140b2fc45efd3495b0832a6a` |
| `docs/evidence/home-widgets/clock-date/board-panel-160-home.png` | 314023 | DATA | `9fdc354f6d9436cd342992b59d836c458b78d7c6faf2cf0e728349cc60184de6` |
| `docs/evidence/home-widgets/clock-date/board-panel-200-home.png` | 314414 | DATA | `02ce7b1cdb66b9d684be9c9f951cd611420c7da18f141edb7dadf6856689498d` |
| `docs/evidence/home-widgets/clock-date/host-landscape-steps.png` | 113976 | DATA | `cbd3efe5b9aca037e04fec956d8cfe4ede3dfaeef71538588201185891bceec8` |
| `docs/evidence/home-widgets/clock-date/host-portrait-steps.png` | 81672 | DATA | `ab1ccf5557d0dd75dcce28795ba670ea2c855a75b471ddb544bb7dbe98b34c79` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-analog-dot-matrix-weather.png` | 233227 | DATA | `0ca9d2b169c3e0612a920c08333a610112cd480324c26fc7a30769d6402841eb` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-clock-bubble.png` | 191856 | DATA | `ba630cbadc8406ed9cc8aed992b3bee046be68bbb48a3a6d0b5a4411d831b79f` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-clock-thin-fling.png` | 206714 | DATA | `ef30699ebb39259b995f81a6b3a266b0b7410965975d81b39143428a665d702a` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-edge-indicator.png` | 197139 | DATA | `4a2e198e3085b10d99599fb9e4949441b2f13b668baf2cdfd5c4591b76f7ea6a` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-last-edge-new-page.png` | 193391 | DATA | `09f2c39d77fa5ef7146bc3c750bca8df3c2235ab035f4d517ba50f7b3dcabe21` |
| `docs/evidence/home-widget-design/closeout-2026-10-01/qemu/home-fluid-new-page-drop.png` | 192621 | DATA | `5007dedc8ec8342188b82d2b4f5c779113f2e4183915ba43f7c12411c9210860` |
| `docs/evidence/mainline-full-shell-2026-10-06/console-after-ddrcp2-fix.jpg` | 18462 | DATA | `c227b66f47d51885f41bb7a13b1da3cafb57355cd1fefa448399e775086f6491` |
| `docs/evidence/mainline-full-shell-2026-10-06/full-shell-mainline-top-vs-normal-bottom.jpg` | 47032 | DATA | `7887bc93e8d1ea584a164af871391bb5236306453972a3c324315cd148b3c02b` |
| `docs/evidence/mainline-full-shell-2026-10-06/panel-purple-background.jpg` | 22447 | DATA | `dcc114f12b60c087ac0663b8cf1109c2b21bd025bb333b872b596447baa1f7c0` |
| `docs/evidence/mainline-full-shell-2026-10-06/touch-finger.jpg` | 24638 | DATA | `ee179c2bd5acb9061a3af48f53535a44026d5e9b9771628b0a77218b13b91e23` |
| `docs/evidence/mainline-shell-parity-2026-10-06/after-touch-camera.jpg` | 19030 | DATA | `d2af9c82e952991b11d9a3259ceabb0bca7491f948053d7096a8e1e6ef4ef73c` |
| `docs/evidence/mainline-shell-parity-2026-10-06/power-sheet-camera.jpg` | 7005 | DATA | `f211031020afcea2fe58537b82bc16635ee2773c34af41df4cde6f8c3d895d8f` |
| `docs/evidence/mainline-default-boot/installed-home.png` | 101927 | DATA | `dc7f1191e55daba719f8f0898c13a89f748de8d1880b4edfb395f93e469aecf9` |
| `docs/evidence/mainline-init-exec-transition/camera-repeat-2026-10-05/panel-dark-candidate-120s.jpg` | 21563 | DATA | `5405de961a963cd1446cb7f42382329048367cdbc9866a248c4445666c6a6bbd` |
| `docs/evidence/mainline-init-exec-transition/camera-repeat-2026-10-05/panel-normal-shutdown-text-21s.jpg` | 31121 | DATA | `31c010bb635bc85bdd6980d8fe602098d4f83ac52a9d36a1c011b50f90fd1b68` |
| `docs/evidence/mainline-restart/physical-minimal-2026-10-02/home-panel.jpg` | 134465 | DATA | `c2d7bd67952385a6729cb1ade6fae9ef1169f585461deea15def08c26f8b4698` |

### Ordinary mainline trial and normal recovery camera evidence

Non-executable photographs of the physical device. Capture commands and
limits are in `docs/evidence/mainline-system-trial/physical-2026-10-03/README.md`.
The ordinary-trial photo does not establish a new mainline frame or touch;
the normal-return photo follows separately verified protected normal identity.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-system-trial/physical-2026-10-03/normal-return-home.jpg` | 74117 | DATA | `b7616d6dfc744893c4f52af15cdea1b4fe81f909fe251ea54ac1ced9563484c8` |
| `docs/evidence/mainline-system-trial/physical-2026-10-03/ordinary-boot-panel.jpg` | 91919 | DATA | `e633d697f387c1d6d4fa7fb827be6bc5665ea54ab3e9e6f1b536724c94d01f10` |
| `docs/evidence/launcher-curation/drawer-native-2026-10-08.png` | 68670 | DATA | `ab2199317d89f02e711c934b7a453373089c084e12b413e9d636c16bf68f7b38` |
| `docs/evidence/mainline-sd-image/fresh-home.png` | 56268 | DATA | `bbf09476cc92fa4efd0002fdf3efd415c4b2722deb0ed091d7096892f06f000f` |

### Mainline HDMI native captures, 2026-10-09

Non-executable captures from the physical board's compositor, with source
identities and commands in `docs/evidence/hdmi-mainline/README.md`. These are
native screenshots, not monitor photographs or physical touch acceptance.
The old-trial pointer position and fresh-trial Home selection used injected
compositor commands, as the evidence records.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/hdmi-mainline/fixed-native-home.png` | 354298 | DATA | `6c8632fb3cc8f1871cdf90d06ee54b6841535bd7500fdb94b05869b1610187b1` |
| `docs/evidence/hdmi-mainline/fixed-native-terminal.png` | 9681 | DATA | `cc2d10af36ae21000abaa1911dcbad1e225dda5d3c603cbde016f0cae4577fed` |
| `docs/evidence/hdmi-mainline/live-mainline-hdmi.png` | 30025 | DATA | `1193184ac0aba5f9e6b8bdc1aa270fc4db3f640ffe77a50a763bff560af2c868` |
| `docs/evidence/hdmi-mainline/live-pointer-native.png` | 28836 | DATA | `c30fbdbc85783130e8a4606df061767724d2199c07426fabf151349f713c0908` |

### Manual HDMI switch host paints (2026-10-09)

Production Settings paint with synthetic controls; no board or monitor photograph.
See `docs/evidence/hdmi-hotplug/manual-switch/host-render.json`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/hdmi-hotplug/manual-switch/host-confirm-1920x1080.png` | 55567 | DATA | `f2f4c25452eaf4d89d9039890238f59faa7398a9fcd13aaafb526243c77fb1f3` |
| `docs/evidence/hdmi-hotplug/manual-switch/host-confirm-568x1232.png` | 51765 | DATA | `7dbe61332db45d9205343d03de556efb9a8a6498d6e40acb978bc34bdc900320` |
| `docs/evidence/hdmi-hotplug/manual-switch/host-confirm-800x1280.png` | 58349 | DATA | `19ba27a947777a66004ad7eac0900d0abb4c8e90325c35dacb4e6716fad585e6` |
| `docs/evidence/hdmi-hotplug/manual-switch/host-settings-1920x1080.png` | 52805 | DATA | `5490312c11c4c5fdbb92a0f9745a83dce0c316c148cc78379ada559f180e09bf` |
| `docs/evidence/hdmi-hotplug/manual-switch/host-settings-568x1232.png` | 46776 | DATA | `ce417f85b6a8de46d73fb7b4955524e3463106b90b7e0f09185618ec926aa98e` |
| `docs/evidence/hdmi-hotplug/manual-switch/host-settings-800x1280.png` | 52509 | DATA | `7139fd4be7aecff236b5df281a2c0a8b62aaad8b8df96bd03a174572183bf3b6` |
| `docs/evidence/hdmi-hotplug/landscape/hdmi-plugged-grim.png` | 9570 | DATA | `ccbde505048655fa68d53a8719b9fc0081c36bc65175053d6c4f9773dee3a448` |
| `docs/evidence/hdmi-hotplug/landscape/panel-after-unplug-grim.png` | 6428 | DATA | `8c53f15f85acc02f9ec7a5746e0edb40e0e24f76e0116cbff55f5f64787e2d7d` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/drawer-1280x800.png` | 95606 | DATA | `8751565df5b1e63c87b9ea5a219306acdb6b6a8b3e9ccc75e185dd2cac5c313c` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/drawer-1920x1080.png` | 72295 | DATA | `0a74244d895e2fec50725501a172a7bf480e6ab66413fa5f78600d818d7056a5` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/folder-9-1280x800.png` | 22684 | DATA | `343ac491a42bbd1c908ba3c18709052ba877216ebee89fa7b3bd2efb0b5d60ae` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/folder-9-1920x1080.png` | 26963 | DATA | `be707130ee63e5f173d4f0773eb69cbda52902ab9797ff70c01abc5e2b5bf805` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/help-1280x800.png` | 67309 | DATA | `e2ba3efb1c87ee88676ff749e8c4dfbcff5ddcddd98c86ce081a0399e21b3f20` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/help-1920x1080.png` | 106752 | DATA | `7045157b5371d1b8cdf736f431e306b0496faee2ebe476aae761766d2e9c3ad0` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/home-1280x800.png` | 32407 | DATA | `f45596248a932840e6078564d77d588bb61c2746c3c4557af81d8e51cc681e01` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/home-1920x1080.png` | 47407 | DATA | `0ca331a217bdac0a5661b18d31c65cdfc60e4bf841b070fc63a3503c9af8d489` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/power-1280x800.png` | 20611 | DATA | `5f05afaa389d467e4da022aa89b0e28954f5c5781560e0266f4033069aeccd35` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/power-1920x1080.png` | 24938 | DATA | `809be86682262ef7aa5a9a10ad16b738c2cc2cba3a177b73705c3ee50967ff24` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/settings-with-base-1280x800.png` | 45816 | DATA | `467f4bc7cecc80febbcbb90ade203ea1fd0f147fe7ce76429449dfdb1551a489` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/settings-with-base-1920x1080.png` | 50360 | DATA | `1daa524fb299d72e539fe30e89a885e9ba1560b591a81d06d6477628b726a121` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/shade-4-notifications-1280x800.png` | 63018 | DATA | `14cab0c1cdb7a05d3e53c9102458283e95bebfd93f8c04f257e1e695476b1101` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/shade-4-notifications-1920x1080.png` | 71163 | DATA | `efd77f7f6efd13ca4611cad029513ab067e438808422d59e918fb8027adc0bd8` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/theme-chooser-1280x800.png` | 37784 | DATA | `e40919972c198c05d6ca6be10bdc15655cb9d0caab1154c34736f13f7d0fd63d` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/theme-chooser-1920x1080.png` | 42631 | DATA | `50711fa4810c7df0137c97eeaa1f63e03e98bedbf15fb4bd280b0c3d58121e3e` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-entry-password-1280x800.png` | 29753 | DATA | `3f35ec0b8fb115a14e45a9ef968592c2f14d0d5c79a6126909aece1537ab892b` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-entry-password-1920x1080.png` | 33731 | DATA | `cd5c5d4814aaca240e997b7cdda4dc5ae30ebb2651a2addcea4aee309068ada2` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-list-1280x800.png` | 47394 | DATA | `cfb96550e14595c1cc6ff249cfb25620d789ad0a02e10947c30adad0f6f9139b` |
| `docs/evidence/hdmi-hotplug/landscape/host-renders/wifi-list-1920x1080.png` | 52063 | DATA | `e66227f34bdb80eb23e88dc0a624591af9b738fc038f9b12a6d26fd389332dcc` |
| `docs/evidence/hdmi-hotplug/landscape/board/home-hdmi-grim.png` | 35829 | DATA | `4f9b1ccace0647bd8c3f0ba72a72734b937b1b29b474976bb74ebffc26dcfcca` |
| `docs/evidence/hdmi-hotplug/landscape/board/settings-hdmi-grim.png` | 52202 | DATA | `7372b8293e14bfffa47d05c68097ad2ad9a38d520296f7d520566f157b5deac7` |
| `docs/evidence/hdmi-hotplug/landscape/wide-dock/board-six-slots-1280x800-grim.png` | 813564 | DATA | `23ebae22bc1c15024d46c406068ce4ee9fb70d308aaf630424a71b44765f87e8` |
| `docs/evidence/hdmi-hotplug/landscape/wide-dock/board-video-dropped-in-slot-6-1280x800-grim.png` | 816016 | DATA | `af2a55cad5fe45f24c3b09bdc59b833472ef7f95fd1555375aa9a4bd420fe43a` |
| `docs/evidence/hdmi-hotplug/landscape/wide-dock/board-video-in-slot-6-1280x800-grim.png` | 815078 | DATA | `ee3b2919d25c128292035f7c8f81734bf5196df86b3d1f2f2bb5e8db88a4cf4e` |
| `docs/evidence/hdmi-hotplug/landscape/wide-dock/home-1232x568.png` | 21485 | DATA | `0c2812db3da2b2039cfd41bff317c05d4af90ef45012b944bfa8af19e1cabbc8` |
| `docs/evidence/hdmi-hotplug/landscape/wide-dock/home-1280x800.png` | 31903 | DATA | `7b7cec0fa311bf9096cbc49cfa82581640fc7591cb81a0704b474ddca61c96d3` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1232x568.png` | 36434 | DATA | `9159a4f4c5d3100624614443d41fd5b093b0ef163f3d20e30b07daa0ee05001a` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1280x800.png` | 40866 | DATA | `84b6d97127f8ceb1e70f4c3b85cf1994b3fe4637f8372f88afa93364713fbffe` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/theme-chooser-1920x1080.png` | 48014 | DATA | `3b6245127cef76666a1bb2f9a087aaf775b080e1f7f1a473b69bf18888a5112e` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-password-1280x800.png` | 29678 | DATA | `dbcf4e69ccb55819790044eee32ab81094b6773f9f2b7987e667c7ba80642216` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-password-1920x1080.png` | 35630 | DATA | `72af6843161ef7f354866d72a281a46e8497397f64b44d1cd69a4750b43c14e9` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-entry-saved-1280x800.png` | 35623 | DATA | `6ed36c0bee95582a91d5c228597ab54138c7b2b0d24004d59e98ec408708b3a2` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-forget-1920x1080.png` | 26445 | DATA | `32f507d9192f4fd49b870800b1cb0ab4faf5fc9228f65745538e8d9740127ac8` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1232x568.png` | 45437 | DATA | `8b0f1bfa6b50fd0ae6fd1db609decbc22e800a8ceac84f746e01bae6f4e46f61` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1280x800.png` | 54184 | DATA | `f08588cb20f272da51d3e69f941e5130a1d040e13b5b7f8b0d36e74cd58585c2` |
| `docs/evidence/hdmi-hotplug/landscape/wide-reflow/wifi-list-1920x1080.png` | 60658 | DATA | `95178d12ade837cc1fda9a03e7a58bbed213230e845e0a64eb79e4185fe1c65b` |

### Responsive HDMI acceptance (2026-10-09)

Native Home capture from the accepted normal hotplug runtime; physical target
acceptance is recorded separately in its evidence directory.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/shell-responsive/board/acceptance-2026-10-09/home.png` | 359917 | DATA | `0938edbc429fe58e4ccc4f16e4f25e163b8a8c3664f8a298bed8b8c19bfc7f1d` |

### Coherent-shell integration gate captures (2026-10-10)

Non-executable headless Pixman captures of the selected RISC-V compositor
under QEMU user emulation with native Wayland clients and injected touch.
All content is synthetic fixture artwork. Commands, source revision, capture
provenance and limits are in
`docs/evidence/coherent-shell/integration-gate-2026-10-10/README.md`.
These captures establish task 4.1 runtime behavior; physical panel and touch
gates remain open.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/close-recovered.png` | 16217 | DATA | `93d6c07d5adbc1c7c857add6bcdfe992679c6510255f0fcc63b5c7abd8ff0a13` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/live-held.png` | 14254 | DATA | `71222c20cc4cf43e2e19ba9f127d476943de54fdb361aac4f2f89ad35bb5d4b8` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/private-one.png` | 13898 | DATA | `d2e7e5d51bd74b33c29558581a0a216f1a1d240b40a5216d8e0cf8ba01d686da` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/private-two.png` | 13898 | DATA | `d2e7e5d51bd74b33c29558581a0a216f1a1d240b40a5216d8e0cf8ba01d686da` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/public-one.png` | 13959 | DATA | `f864663e2718f63ede79240898af5aea1fb26a1ed90febebd73f0e4c70d1f23d` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/public-two.png` | 14394 | DATA | `2a13ea91fa102b75dee1b75bb8d6b9c068a68b8221c814373deedddec80af296` |
| `docs/evidence/coherent-shell/integration-gate-2026-10-10/unavailable.png` | 15058 | DATA | `1596eb39f0075c6e2dfa20f75c3e31513a3d937a2360a67be2dfebc6f34169ae` |

### Coordinated shell scene captures (2026-10-10)

Non-executable headless Pixman captures from actual RISC-V Sway/Rust under
QEMU user emulation, native Wayland clients and injected input. All content
is synthetic. The old-compositor capture records the failing drawer regression
control. Commands, source revisions, hashes and evidence limits are in
`docs/evidence/coherent-shell/coordinated-scene-2026-10-10/README.md`.
These establish task 4.2 runtime behavior; board deployment and physical
panel/touch gates remain open.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-100.png` | 9271 | DATA | `ec84e64f2f63096b88fc1c03ddb63ca360ba93d72401a6764fe053d66e6d5bd0` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-300.png` | 10187 | DATA | `fea0f40dabd3aa4fd5bbadd4a7e95205d66c93a937bf9085477e1815f6cd45cf` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/drawer-open.png` | 10187 | DATA | `4780410f54c3f47a02258d3bab73dc18acdfb993c40ae5ca1a348f1562759537` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/expand-01.png` | 5487 | DATA | `2ea7344df624378e1acea8a50a07e65463a88cf32d538a79542eb0c926f7ad46` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/expand-restored.png` | 5776 | DATA | `91e8033dd6d79142ec66fb0f3e8d4612d13c5942967d94c0ed06a4b20884d66e` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/focus-app-restored.png` | 5793 | DATA | `98733d800ee9bed45d9010b5b4ec4615fa165f6fb7f806566863a95628753d63` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/focus-search-typed.png` | 12216 | DATA | `8fa91114e4b65754f27d216a1b80b96c79a7ccb6e21ab7b6684efeb5ac98d42f` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/home-held.png` | 9495 | DATA | `39468de49f9d3bf7349a8c1b05292f915908c934749ee8e0f55b0ae32f18494b` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/old-drawer-100.png` | 9273 | DATA | `1c663bebb1df5efc2adb36c1f804b5a9ac60650154ea95046a0f2a7241c68ba3` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-100.png` | 5784 | DATA | `c8c53864d6dd325f0ff5d4151ae3d79e849f9b206dd5bb17c79a0c4bccb3a9ae` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-300.png` | 5637 | DATA | `6b7296b7e4613fca5c18bc66099dce27a24ea2ec4faad3b64bcb81bb082ffda6` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-open.png` | 25305 | DATA | `fa6e0aad5a3f7a927ab57b3ddb14fb5501c85685cf1090d4e55776f8381827d8` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-restored.png` | 5792 | DATA | `5885fdf7a509f577e21b5a318592c1ac3327778c4afa004d3e5824becdec50a0` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shade-settings.png` | 42780 | DATA | `60aea246794323007d2d149bdbdd07df6f18fd897c362b87df6904ed5fa7410c` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shrink-held.png` | 5697 | DATA | `b384d1c88c5b1ee3f33eb863b238d32db660baf70dc09cacdc6c121db1f4ab88` |
| `docs/evidence/coherent-shell/coordinated-scene-2026-10-10/shrink-overview.png` | 13841 | DATA | `23048b7408a4d2855520da2efaffca1496620dd4929a13c4c56ff1f1bba1fe7f` |


## Coherent shell live interruption evidence — 2026-10-10

These synthetic headless captures record task 4.3 reversal, retarget, actual
client exit, refused close and privacy during transitions. Provenance, commands
and sampling limits are committed in `docs/evidence/coherent-shell/interruption-gate-2026-10-10/README.md`.
Board installation and separate physical gates remain open.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-entry-held.png` | 5913 | DATA | `e5c034b1ca848a75afc32f7f37e88d49df6079986e20dc23fa744c3726a0af30` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-entry-reverse.png` | 5931 | DATA | `83d4d2abb9f8dd0a3857365b7f748742d165edcb331220b175de3b9103d77375` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-expand-middle.png` | 5541 | DATA | `5cc5752bd9f8c643f7fe9e07b1a77064a5526d25e01bcefb9266f4ff72dcccde` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/back-expand-reverse.png` | 5524 | DATA | `af1e532589fb73a6a499dcdce1055460dc60f5b644383a1b3603c9a0d9d9633b` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/entry-held.png` | 5843 | DATA | `298b3d4a631e79af2a7781e07346e8f994d965da6c578d5619a53a3a55905945` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/expansion-unmap-middle.png` | 6031 | DATA | `09d0b1beeb684359bc181bb597351a48164bae9b3c3d86bfd9efeda5dd2742c4` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/expansion-unmap-recovered.png` | 5782 | DATA | `5deb1e9485c678175369348ebef3d953cb58403ba35a726621523e07edb3b8ec` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/finger-reverse.png` | 5084 | DATA | `19a2b3247c4d649369d209ef8db7221e0a7b1ce8e0b71ef9cedca9397bb39764` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/new-contact-middle.png` | 5525 | DATA | `0dd90de10d007f694e62dad536a4a727a418759a440fed8ac3c4a03f868301cf` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/new-contact-reverse.png` | 5571 | DATA | `7b0e552f4353e45388f53087dc13c4112a62f43afa1d65d9351499f9005c0e02` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-placeholder.png` | 14376 | DATA | `ef21f6b9ec3318a183a23afa3684831db45af1db9fa8a6cc49b828812ef2d8d7` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-public-control.png` | 5976 | DATA | `1deb07b5d46be0a31537402f5361ee5c502f8eacda9e18b1f1f00ac1998c5638` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/privacy-transition.png` | 5957 | DATA | `b2a1f9fd9d44da437eb3d8259818399947b26932ec27e417b964cb311940b14e` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/refusal-pending.png` | 16336 | DATA | `388e599604519b8cb1c2460eca20a263b9dd2bf242a39a07b0e82efe74906a0a` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/refusal-timeout.png` | 16316 | DATA | `b3e22611d1edb2af5ffd758c2a8611ff8a26e2904bac8ff8bb4fed15ffed0878` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/second-contact-reverse.png` | 5483 | DATA | `8a86045ce2e93f57e1e03dca703b9eb9cc623d77b2d5bb792eaef2f8f6825c8e` |
| `docs/evidence/coherent-shell/interruption-gate-2026-10-10/source-unmap-recovered.png` | 5783 | DATA | `d1bae5b45118c28913e28e0e12c5fa66e82203366920f5b378b14c65be52bb87` |


## Help and navigation aid host evidence — 2026-10-10

Generated Cairo/Pango host renders for coherent-shell task 1.5 use pinned dark
and light appearances and nonsecret synthetic app names. These are DATA images,
not board, camera or real-finger observations. Source, commands, input identities,
reviewed drawer-reference change and limits are recorded in
`docs/evidence/coherent-shell/navigation-aid-2026-10-10/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-buttons-hdmi.png` | 48798 | DATA | `b39cf837f2429aeac1c57e9a3da431f636d3d8cfcd1dad5d1bfef112d62666e9` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-buttons.png` | 40160 | DATA | `732d489086b9e9b71addf83951602b1df519057fa668717eb6b7124b676d7509` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-drawer.png` | 46441 | DATA | `9a39433788953784ec03217f05c1db3b3aa11a370f014108aebfe1f7def99c15` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/dark-help.png` | 54543 | DATA | `dc51a79c53b67e1ead64c32b1ce4be9fb2908b8cdb6f632846b314b77cf4d190` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/drawer-568x1232.png` | 44240 | DATA | `be876d1bc6515c1e346450c8f8c0f0d5b477fcbbe7a51515c95e284ac753f244` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-buttons-hdmi.png` | 47361 | DATA | `55423d4699800eb9b55e3353e111039a6535fb040b81afd04637c0a2fb4bc4c0` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-buttons.png` | 38894 | DATA | `923cfcc3bb698118306399317dd241a8dfa51435629007fff38903358d934791` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-drawer.png` | 44721 | DATA | `5e698163701ee1c86962c53a459b9e7aff68dc2d11fc8fa961887dadae099087` |
| `docs/evidence/coherent-shell/navigation-aid-2026-10-10/light-help.png` | 53454 | DATA | `193bda0b9be35ad0a5f637c9324db54ae582299e86ead4660f63cec881debb26` |

The combined candidate’s native Help image was captured with `grim` after a
programmatic route request on the reserved physical board, using the committed
Rust renderer and bundled Catppuccin appearance. It is not a camera capture
or a real-finger test; exact boot/artifact identity and capture command are in
`docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/help-native.png` | 69836 | DATA | `3fb102a889e56bb760935320dec9e14e546d1b79743cef05ba91a35a97a4e57f` |

The ordinary-boot Help image is native `grim` output after a programmatic Help
request on the reserved physical panel. It was reviewed for readable labels
and private information, then the script returned Home. It is not a camera
or real-finger capture; the exact installed bundle, fresh boot ID and command
are recorded in the same combined-candidate evidence directory.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/combined-board-candidate-2026-10-10/ordinary-help.png` | 46665 | DATA | `2f81e737d0511f644884883876d82572fb67d86ccde475a54fe3bddeff3ad164` |

The touch-hold app menu image is a headless QEMU screenshot from
`tests/rust_home_screen_qemu.py --actions-only` with injected touches. It is
not a board, camera or real-finger capture; the command and artifact
identities are in `docs/evidence/recovery-routes/touch-app-menu-qemu-2026-10-11/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/recovery-routes/touch-app-menu-qemu-2026-10-11/drawer-actions-touch-hold-menu.png` | 76088 | DATA | `4bc927d031126339723be556a533c0b2e7e37435d15bf55a5273771469712ae7` |

The recovery-routes touch capture holds trimmed, downscaled bench-camera
clips (real-finger input; serial/SSH-triggered setup) and one native `grim`
screenshot of the Settings denial. Raw clips stay private on the host; their
hashes and the exact triggers are in `docs/evidence/recovery-routes/touch-capture-2026-10-11/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/window-list.mp4` | 512512 | DATA | `a3ae45784cee598cd059ad936fe21e25e74b8410ddfbe506674a2c2a0206ad97` |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/brightness-denied.mp4` | 113533 | DATA | `e4cb7a888f92d37b8145d5751d516dd4bbdd2d98fe4fe21a0f90937d225b6da7` |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/video-cancelled.mp4` | 234786 | DATA | `eaf032fdc191224528a5c91d2fbcf3377d730a752047f4bf1c44738e1e273f02` |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/video-stopped.mp4` | 115156 | DATA | `f0a3a6dd1be3da1aac8cd966bbbffb84a6284567d5de684cb5ccf837f1f61a7e` |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/settings-denied-native.png` | 36652 | DATA | `b5506ce563292b714551bb6a35de3e378b088ed60651fa05a6265281b1d7675f` |
| `docs/evidence/theme-picker/combined-install-2026-10-12/home-after-install-native.png` | 5322 | DATA | `f078407d50b5b949a6ee29f6f41e649f0ad74a0c3b1cc263c099073f9ca98181` |
| `docs/evidence/theme-picker/default-backgrounds-2026-10-12/themes-without-saved-choice-native.png` | 93172 | DATA | `d5e9e45aaffb221acc1a7a56d9951d8176a4d8e37e5b4c2340c096959c473efc` |
| `docs/evidence/theme-picker/row-sprites-2026-10-12/sprite-build-picker-native.png` | 177384 | DATA | `03df501db91377f9ba381c07dccf9b0000a1d358a717696e4d3de953f05a8e77` |
| `docs/evidence/theme-picker/board-session-2026-10-12b/18.3/position-curves.png` | 134564 | DATA | `a74cd1ddb6b77674c23ef6255a09cd09a90bdc471fda3ae8ef6d5cf495bb2ba3` |
| `docs/evidence/theme-picker/board-session-2026-10-12b/18.3/velocity-curves.png` | 143987 | DATA | `ca4d7726de8bd0b39760a5b4a10858f0fa12e9ad0b80d360ff397f413385015d` |
| `docs/evidence/theme-picker/board-session-2026-10-12b/install/installed-picker-native.png` | 93629 | DATA | `f299986e3fcee4497bc64680d1e0d8ef8f1ccff26efc18a3af8976a22a4cd0a9` |
| `docs/evidence/theme-picker/board-session-2026-10-12b/install-2/installed-home-after-apply-native.png` | 78798 | DATA | `99b2ce3c66e9f30ba473638d6cf0e33c0e2e33cd1035f48782c536e7959af99b` |
| `docs/evidence/theme-picker/board-session-2026-10-12/10.7-6.6/panel-bottom-full-resolution.png` | 21535 | DATA | `57ac5ab689645e6836f75f06c27b01c3aaf261909ccd5e2d8652b4c2fea84c2b` |
| `docs/evidence/theme-picker/board-session-2026-10-12/10.7-6.6/picker-dark-light-dark.png` | 219129 | DATA | `7e131b309e4159af7095a885c20504b1f96f6eb3eb3acba0d2517a40e44e8d8e` |
| `docs/evidence/theme-picker/board-session-2026-10-12/13.4/browse-base.mp4` | 84386 | DATA | `dc35b46841c36e893c0e2486b323f09af3c68d33c293da7eb8be802d716a8afc` |
| `docs/evidence/theme-picker/board-session-2026-10-12/13.4/browse-cand.mp4` | 73352 | DATA | `95e2e17c3924071e0c90b13d2a9dab4451b7c0743a081bd9f6693a05b0526fa0` |
| `docs/evidence/theme-picker/board-session-2026-10-12/13.4/vis/baseline-open-theme-background.png` | 163330 | DATA | `5deada975fa50bf93d7a953937843fc4deca474fba7efd4d37163460a1705013` |
| `docs/evidence/theme-picker/board-session-2026-10-12/13.4/vis/candidate-open-theme-background.png` | 154304 | DATA | `e55929ec58bc52e2f8d959894ff55174b1596eec86f76d9175179b3e1ad53619` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/gesture-release-to-rest.png` | 28764 | DATA | `d29948d090aa47dbe99fd62e54b7ec2dc089c5197548eba3a37079060b838d54` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/gesture-timelines.png` | 95125 | DATA | `7e44fb5c7a4443aefcd3be11549af1d26815501a5f98f0248dd4af75d91eefe6` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-ca-bg.png` | 41832 | DATA | `2b5b76d5e25b4fe5f35398c06fc339b2863468a1376245f5846418783d30c115` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-ca-theme.png` | 63945 | DATA | `7997913ea7ddfc13ba865c7614052838da147851b0e3fe9f4623c66923d006a9` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-mo-bg.png` | 37737 | DATA | `7884f1bbaf1cab44ef5a91856f97c98ada66d5db3eea8d2632725083d6c28924` |
| `docs/evidence/theme-picker/board-session-2026-10-12/18.3/labels-mo-theme.png` | 65152 | DATA | `854cacdba026a85315abcc61b565ddebc3293fc50009c7c5b2640ab17c069726` |
| `docs/evidence/type-roles/board-hdmi-100.png` | 138064 | DATA | `602664b30c1ad73b92262f18eeb04dfbe8a4feb722f4e5ff616f75ebe1ea3349` |
| `docs/evidence/type-roles/board-hdmi-160.png` | 172358 | DATA | `8ef18c9fab70530c8a3a2f70229a2bfe0ed2327668fb29d94f5b50643ca4c3a9` |
| `docs/evidence/type-roles/board-hdmi-200.png` | 172360 | DATA | `240e7ed0d3c042b68eb33b4eacf9eb2116dbb664fc98b66825177c3903c193ac` |
| `docs/evidence/type-roles/host-settings-landscape-steps.png` | 197358 | DATA | `1afbe66898b6e3e1d236a3d4d9aa10021e3c40ffeb4ebcc11dda7e540e7c3e1e` |
| `docs/evidence/type-roles/host-settings-portrait-steps.png` | 217467 | DATA | `fee1891f2f96bd4e4291c8e32d675cfb5ff1e61591679489d61188d537be3800` |
| `docs/evidence/type-roles/host-shade-landscape-steps.png` | 245430 | DATA | `6537a53dbe93d30db9eb3f196c4b0402a823de793f9495703e3a006ecd090193` |
| `docs/evidence/type-roles/host-shade-portrait-steps.png` | 190180 | DATA | `91219b4a683ef259842b3a97054c3f5fea5d1f038ba8b0afc3c349c42abc93f6` |
| `docs/evidence/type-roles/host-vision-landscape-steps.png` | 160939 | DATA | `ae5a5b24de9f4ac3fa96d6ad528df09ad30eb4975e70abb87fa5c744423c6020` |
| `docs/evidence/type-roles/host-vision-portrait-steps.png` | 156417 | DATA | `b9d91f77f6185d650801e5f003338c68ccebdca3d481f88a80e734bcb527d8b8` |
| `docs/evidence/recovery-routes/touch-capture-2026-10-11/stale-splash-camera-zoom.jpg` | 15353 | DATA | `379ebd25d4a0f224c33d2651d7aaeb134fa7258b625503b12e1e4a2d3e2f5cc5` |

### Mainline boot splash board trial camera stills, 2026-10-12

Non-executable frames from the bench webcam films of warm reboots. Capture
commands, timings and limits are in
`docs/evidence/mainline-boot-splash/board/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-boot-splash/board/aruco-target-at-uboot-prompt.jpg` | 126512 | DATA | `d848b4231cde223d49f29d2392cc9e5aa0f53a696604921b1038f5ed1f8dea1e` |
| `docs/evidence/mainline-boot-splash/board/fb-poke-after.jpg` | 125609 | DATA | `1d9e4f9fb666eb675f387c8c20790548f8a3f35bafbd429a27ac051975c2ead1` |
| `docs/evidence/mainline-boot-splash/board/fb-poke-before.jpg` | 125833 | DATA | `498f1bc8d346615497735748e413f8981f1798384ad741a281a3f5e22f4e2d75` |
| `docs/evidence/mainline-boot-splash/board/handoff-film1-strip.jpg` | 67892 | DATA | `4dd87701a7449f6e5e2bc62c4a20b313c2501a8c060ca167f7fc96ceeb971c97` |
| `docs/evidence/mainline-boot-splash/board/handoff-film7-strip.jpg` | 66991 | DATA | `40fbecd977357ed567f28d5253c5d502454fb0422a05c3be7cc4f02891123a6d` |
| `docs/evidence/mainline-boot-splash/board/splash-at-idle-kernel-prompt.jpg` | 119995 | DATA | `2c11206efc4b2a5bb0ec471f0ca738e1e3c8fb52e2d8d899d3b4b37c9765ef33` |
| `docs/evidence/mainline-boot-splash/board/splash-at-uboot-before-kernel.jpg` | 119671 | DATA | `b7e0c5fa9b1f9cb9e327d310bbeef5c05df6ea15c4103c3e6708a09b125cc463` |
| `docs/evidence/mainline-boot-splash/board/unreserved-kernel-tear-film2-strip.jpg` | 68373 | DATA | `dc38dac11ae7f6129c9433fe43db56dbfdc01fd2e0d3c7fdc101e14fa129e43b` |

### CPU0 Linux-start board session capture, 2026-10-12

Non-executable `grim` capture of the compositor output taken while CPU0 ran
the echo payload under Linux (coprocessor task 5.1). Command and limits are
in `docs/evidence/second-core/linux-start-2026-10-12/README.md`.

| File | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/second-core/linux-start-2026-10-12/cpu0-start.png` | 7734 | DATA | `a6a8591d874042351b5785b57b87277c1af63eeb007045ebb220960a896a03e8` |
| `docs/evidence/stroked-icons/board-panel-settings-scrolled.png` | 50843 | DATA | `c98b920c65045ce8343e8bd247fcc1fd7ad7cd15c671477017475c10f2b063f2` |
| `docs/evidence/stroked-icons/board-panel-settings.png` | 27104 | DATA | `b0d3c684830cd403884f4f61c7ec7b72661a5fb9a4167c305723c8ff9dcc492d` |
| `docs/evidence/stroked-icons/board-panel-shade.png` | 13125 | DATA | `a51cada8f2a82729c14c2f1264cfb951e93776c00de0c1f4132575c3fbce22f8` |
| `docs/evidence/stroked-icons/host-dark-landscape.png` | 212819 | DATA | `ef106ae06c7ac7ddc52a993cfab2f130bfba6cfa013ed85c996008b4ab9a1a5d` |
| `docs/evidence/stroked-icons/host-dark-portrait.png` | 222347 | DATA | `5339bfa0b2b08d8ea00a063436fbf49a7ae5ae372029cfaab4b926c81208ac9c` |
| `docs/evidence/stroked-icons/host-glyph-sheet.png` | 57618 | DATA | `6c3d4ea48118e0b022af08ee0e73e3ca62ccc59f453a780c4620f6254e5a6f66` |
| `docs/evidence/stroked-icons/host-latte-landscape.png` | 201595 | DATA | `4b8a9e1e62f86d1b73e363abecbf30a86e95e54f0a892374519834ee8343d933` |
| `docs/evidence/stroked-icons/host-latte-portrait.png` | 210178 | DATA | `04dc1e1199800310f48125df1fe9764373cd9eaea5be0834fcb68852391b112c` |

## Keyboard base shell host renders

Host renders (Cairo, no compositor, no board) of the shade's battery line and
Settings' Key backlight row, with and without a fake `power_supply`/LED tree.
Command and limits: `docs/evidence/keyboard-base/shell/host-renders/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/keyboard-base/backlight/settings-slider-board-grim.png` | 41683 | DATA | `289e8fdf6ef299338eef4531648a680f111e86022a96e7320bd720b00eb3dfac` |
| `docs/evidence/keyboard-base/shell/host-renders/settings-with-base-1232x568.png` | 43848 | DATA | `e618055416a78cf92d162d4ab6fcdcc24da5d0349e19af82886d7d9e48e45cd9` |
| `docs/evidence/keyboard-base/shell/host-renders/settings-with-base-568x1232.png` | 51515 | DATA | `104cc64446e119ada93a262fb8cd42c4edfbb71351fe1240e23af9608bc4dfef` |
| `docs/evidence/keyboard-base/shell/host-renders/settings-without-base-1232x568.png` | 38040 | DATA | `297e1020fe8fee839a7cc438ad0188e9854570ed3f6dd0972e099624b62db857` |
| `docs/evidence/keyboard-base/shell/host-renders/settings-without-base-568x1232.png` | 44523 | DATA | `8bf60ecef682bbd3096389c6fd385dd5bae0442ec0e8ff4ace14ac32a94abd9d` |
| `docs/evidence/keyboard-base/shell/host-renders/shade-with-base-1232x568.png` | 24852 | DATA | `2b291140f4b245f798056e3464f81c7e7b2842f366b312e53052326aba43e79a` |
| `docs/evidence/keyboard-base/shell/host-renders/shade-with-base-568x1232.png` | 25853 | DATA | `f5b353a2e56808b422a389db46e05ba66942f180dfeac519812dc334d2e58711` |
| `docs/evidence/keyboard-base/shell/host-renders/shade-without-base-1232x568.png` | 22596 | DATA | `6200cdc038df4f5cfcf74422c60f13be70a32444e9221637f93e4af3157df22d` |
| `docs/evidence/keyboard-base/shell/host-renders/shade-without-base-568x1232.png` | 23670 | DATA | `f3689f64b1d76d8cddaa38b41448d23af3191c499a3b84cbeee3ac123e5a4dc5` |
| `docs/evidence/keyboard-base/shell/board/settings-landscape-drag-injected.png` | 22145 | DATA | `6c17a39b1e712ed00ad8bfd58a1b25898683ea60b202dadd98a0445fb4c28ac8` |
| `docs/evidence/keyboard-base/shell/board/settings-landscape-grim.png` | 22145 | DATA | `6c17a39b1e712ed00ad8bfd58a1b25898683ea60b202dadd98a0445fb4c28ac8` |
| `docs/evidence/keyboard-base/shell/board/shade-landscape-grim.png` | 18440 | DATA | `b41da29af5be0df5d36eba405099ca982ca77038b201c19221cb770800f13f0b` |
| `docs/evidence/keyboard-base/shell/board/settings-key-backlight-off-injected.png` | 41533 | DATA | `58829059cff1e99ef81e09d252af7c7203d0957336c79c764d56f90eda1dd9a5` |
| `docs/evidence/keyboard-base/shell/board/settings-three-column-grim.png` | 41476 | DATA | `6e52317412dd88c019d15fa08558b59ce63bf68c5b7656d206ba1179c7f48a91` |
| `docs/evidence/keyboard-base/battery-policy/shade-countdown-grim.png` | 23403 | DATA | `0b84ded661718cd1b9306ef2327c4a4218f6e4e85143c244526130f1bf5457d3` |
| `docs/evidence/keyboard-base/shell/board/home-battery-widget.png` | 309123 | DATA | `35392bb82d2662916a720b29ebeb5594de6d1490e040f07686ad69b8aab7a726` |
| `docs/evidence/coherent-shell/notification-preview/banner-trusted-1232x568.png` | 27362 | DATA | `1858054405c18a6f9236793779eec16d900195d2ca0846814d8fb0a218037eb5` |
| `docs/evidence/coherent-shell/notification-preview/banner-trusted-568x1232.png` | 44988 | DATA | `d30df0ee7fb7c7ae12264847173b10afbd83e0d6d41b7611c4cfa6f71f325980` |
| `docs/evidence/coherent-shell/notification-preview/banner-unknown-1232x568.png` | 27324 | DATA | `b86059e9249f9018bbff16dba9557df0e59eba09b741fda9b61218d31d967ca2` |
| `docs/evidence/coherent-shell/notification-preview/banner-unknown-568x1232.png` | 44957 | DATA | `89ec298b9ce93940f7d923f2f60b606477c39f7c2385c85beb4f7669bbb4d648` |
| `docs/evidence/coherent-shell/notification-preview/board-banner-over-terminal-grim.png` | 11121 | DATA | `658ff706daf01c54667144e023b8a4568e3079736668d1a210e726104fadb887` |
| `docs/evidence/coherent-shell/notification-preview/shade-open-tag-replacement-grim.png` | 22668 | DATA | `a114b385868a612bec62da7f9db8a6fe9fa6b438e63683078f4cec6b0764c738` |

## Battery - Details widget host renders, 2026-10-15

Host renders of the Home Battery - Details widget from fixture `uevent` text.
Command and limits: `docs/evidence/battery-details-widget/host/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/battery-details-type/board-hdmi-home-160.png` | 830572 | DATA | `418b3422b4a9b0f79b1ccc46ddf97740956762fc12e727182eb17f88eb332009` |
| `docs/evidence/battery-details-type/host-landscape-steps.png` | 148715 | DATA | `85c42274fdbbd7132eef19e3fdf26e867c4f0d50821e3f2f11ded1d3123ae178` |
| `docs/evidence/battery-details-type/host-portrait-steps.png` | 143099 | DATA | `64642d60967ca79da8135460fd7b381a24d16e77e1fc212424b14bfde449fb81` |
| `docs/evidence/battery-details-widget/host/charging-1232x568.png` | 69909 | DATA | `89fb5e30e2319141d86165b5d2cf341a200cd28cfb524d01ea14343e3bfcb2de` |
| `docs/evidence/battery-details-widget/host/charging-1280x800.png` | 81385 | DATA | `3e592c07b4052e7ba5337ee314ab7455402b0216f810f85b707a9e6cbde9f03c` |
| `docs/evidence/battery-details-widget/host/charging-1920x1080.png` | 88296 | DATA | `7da2af5ea9c40498b74d8308fcead6242a76bf8fb2bcbcfea1fb069da8d9de4c` |
| `docs/evidence/battery-details-widget/host/charging-568x1232.png` | 70990 | DATA | `60b7996a8c7278f843b10265c1ddf9f51ee7faa7c7beda7590a2d38037a85b03` |
| `docs/evidence/battery-details-widget/host/discharging-1232x568.png` | 61318 | DATA | `0fae56c2b143e1e698f0faa6c8be231f1a91fb266a32784845cf2ab563bdbb23` |
| `docs/evidence/battery-details-widget/host/discharging-1280x800.png` | 72381 | DATA | `8199e0d4c040ba068b2977ffde96598caee1b1c8de8018b49a1e9464c81eaf75` |
| `docs/evidence/battery-details-widget/host/discharging-1920x1080.png` | 77541 | DATA | `28dfa0fa0b1f92082a6f28fae3750cb413706b0d130f5896da6a008c090402e0` |
| `docs/evidence/battery-details-widget/host/discharging-568x1232.png` | 62705 | DATA | `dbc9d9af23a4a61f023d824faf62c130267d06db5bb4edee2ae2e82b7ca9978f` |
| `docs/evidence/battery-details-widget/host/no-battery-1232x568.png` | 19941 | DATA | `b3f33ed0528e88aa17841a8557006bce65b2e96394e05ad11b33ca3961945ec3` |
| `docs/evidence/battery-details-widget/host/no-battery-1280x800.png` | 24960 | DATA | `1168261a0da7bdf63f4159a1f88c4ba69e19ae14d03861000fdd7b7172b52ea1` |
| `docs/evidence/battery-details-widget/host/no-battery-1920x1080.png` | 29678 | DATA | `020462acd02e38f9e85e5145a19da89f1084a6003eaf6cc4494a5357ed0110e9` |
| `docs/evidence/battery-details-widget/host/no-battery-568x1232.png` | 23043 | DATA | `a03c125e64c86fec1b327dba56c78254508ab60af71e55efeac3b43b16cb96ca` |
| `docs/evidence/battery-details-widget/host/picker-568x1232.png` | 74351 | DATA | `e954fab750d4099ee4d7120197cda001f7692b4c1add50c2a35e465360a721d8` |
| `docs/evidence/battery-details-widget/board/home-page2-battery-details-1280x800-grim.png` | 806885 | DATA | `7734298d1350e5de05032c5196b9bd43beddb97fd92002b8fbe4176d69438416` |
| `docs/evidence/battery-details-widget/board/picker-widgets-page-1280x800-grim.png` | 234139 | DATA | `e359c679fef4cd256b634ba0f50b538a0d9137699b92535b7a9bfb42cbd4d21a` |
| `docs/evidence/battery-details-widget/history/day-1232x568.png` | 57830 | DATA | `95cdbd8c9bef73f125dddfe09bede8f788f1449279e051a6cd3fafd5e895415b` |
| `docs/evidence/battery-details-widget/history/day-1280x800.png` | 74761 | DATA | `aa7fda60f081d96aced6385caa21ceba5f76313a442b446c99221bfb96acbb28` |
| `docs/evidence/battery-details-widget/history/day-1920x1080.png` | 79873 | DATA | `3dd5441b85f70a7ce9e71fe1a5c673445ed42d6f706b81a949315dc8a9040ad7` |
| `docs/evidence/battery-details-widget/history/day-568x1232.png` | 63200 | DATA | `73b75361db4c657da09396de2d83f70e33ed2fea73121fa2dc2eeabba7b41f64` |
| `docs/evidence/battery-details-widget/history/fresh-1232x568.png` | 56020 | DATA | `d4af3b4854df0ae0d7cd904c4546bd9673d518f163d696a6adef5aa5ac7ecc30` |
| `docs/evidence/battery-details-widget/history/fresh-1280x800.png` | 72851 | DATA | `ecadad5cc7bb0f213f2b8a491582a27c91c5a56ca00ccb4e1097e98e644cfae5` |
| `docs/evidence/battery-details-widget/history/fresh-1920x1080.png` | 77618 | DATA | `1a658f6118544201ef42abcd7b8343d4a6e1b69fac925a218f44823e7e252220` |
| `docs/evidence/battery-details-widget/history/fresh-568x1232.png` | 61673 | DATA | `672fe3c7ee2c05b7cc1b009f379e510f2e8426600b2a681c190fdf3bed0c22b7` |
| `docs/evidence/battery-details-widget/history/board/page2-graph-1280x800-grim.png` | 808698 | DATA | `fb49616a25f887cd0f983c825729929cce2b99775c691bea78c1e37aa7dc6447` |
| `docs/evidence/display-touch/trackpad-restart-and-long-press/first-swipe-after-sway-restart-page2-1280x800-grim.png` | 787020 | DATA | `15db802b2ecd6922ddea88a9241ef1ac2c1170f03239c04eada585e206ef5e0c` |
| `docs/evidence/display-touch/trackpad-restart-and-long-press/long-two-finger-press-clock-1280x800-grim.png` | 821210 | DATA | `72969291055b086c99065f7f595d78a04ecbe8c3609958c6aede900abf581e42` |
| `docs/evidence/display-touch/trackpad-restart-and-long-press/long-two-finger-press-page2-after-swipe-1280x800-grim.png` | 787548 | DATA | `1e858f92dd9f427097d33a4b98dac5b37511b5c19b33020fb63c3147ffdd1212` |
| `docs/evidence/rest-of-text/board-panel-100-home.png` | 327813 | DATA | `bc20c47de804c4f5527101e6f8398009d47de992c8434b397740d17b321094f6` |
| `docs/evidence/rest-of-text/board-panel-100-home-weather.png` | 303552 | DATA | `25e9fbda189c1349dd464f2e741065fab1baa77ed140369c4790bfdc9559b704` |
| `docs/evidence/rest-of-text/host-banner-1232x568.png` | 9685 | DATA | `6e222d41121d2e15b3e0a882577b0254fde1067a2716aa50fdb044673eaf893a` |
| `docs/evidence/rest-of-text/host-banner-568x1232.png` | 8607 | DATA | `e7d43131d2a871cf09143d8e3b5f304338fc22c66522d8f01e3c753340b1090e` |
| `docs/evidence/rest-of-text/host-help-steps.png` | 326452 | DATA | `ca4afb3558abc30f43505beae2499dbc7410712f9cbb33abdb76731b942a1cd6` |
| `docs/evidence/rest-of-text/host-help-wide.png` | 448186 | DATA | `e0bf987dd554a51d571177549278875a59a03f7da38cdf863690d69f124ca427` |
| `docs/evidence/rest-of-text/host-themes-steps-568x1232.png` | 189412 | DATA | `40af3196323e16637a133d30834077dc82233204c4d55d17edac781342786b07` |
| `docs/evidence/rest-of-text/host-themes-1232x568.png` | 84153 | DATA | `536e64bc9f493912259970e5a137678db4da9c78505137dd8f136d71c02ea21e` |
| `docs/evidence/rest-of-text/host-menu-splash-568x1232.png` | 72239 | DATA | `7ed97151eb5301a3c567ce5e62f2e32fad72ee8e7296afb1db073b1fd08061b8` |
| `docs/evidence/rest-of-text/host-menu-splash-1232x568.png` | 71885 | DATA | `b537a8fb335420c5812d18d81b0ea6c9ee3880390a81b4db884594de703476d7` |
| `docs/evidence/rest-of-text/host-themes-1920x1080.png` | 44418 | DATA | `64c0fc8b9758247af7bdf85f2457d88ac1a695bae7fd387eb42a3dc6d543c3da` |
| `docs/evidence/rest-of-text/host-home-widgets-steps.png` | 169349 | DATA | `84944d451c4c5266e381fbac4b859350e3c50e7b36d9f583f3b2de2ea22c5dea` |
| `docs/evidence/rest-of-text/host-wifi-200-568x1232.png` | 264969 | DATA | `9a6dbcaf060694446bf9c1aacc827cf46e47c118f638cf8a0462a91ccdab845a` |
| `docs/evidence/rest-of-text/host-wifi-200-1232x568.png` | 263691 | DATA | `de6d2d21d69ae2665761c63868da86a650829570fc4c84d77b4ae88f9e6e2de7` |
| `docs/evidence/rest-of-text/host-wifi-100-568x1232.png` | 145256 | DATA | `81ff11de0912324f6ac0f0a6de8605474c80b9c331be793a442c5fbed05c702b` |
| `docs/evidence/rest-of-text/host-wifi-100-1232x568.png` | 148099 | DATA | `1416ea0b21de344e7d619a22ffb3a88636fe5aa51be06c10be1558a6f540e5a1` |
| `docs/evidence/rest-of-text/board-panel-100.png` | 1130629 | DATA | `9a9b114124f744820f581a8eb43f8ff6f9db4aec88de5205269f60d8a99390e7` |
| `docs/evidence/rest-of-text/board-panel-200.png` | 1176167 | DATA | `b5415580d0ea62acb239e220ebd320fab3b35145a245e79da39e433632fa46fd` |

## Overview backdrop tap board captures, 2026-10-19

Native landscape panel captures after injected absolute-pointer input;
commands and limits: `docs/evidence/overview-backdrop-tap/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/overview-backdrop-tap/backdrop-drag-overview.png` | 36020 | DATA | `cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88` |
| `docs/evidence/overview-backdrop-tap/body-tap-home.png` | 104198 | DATA | `58692858d53cf304c793082fa706d60fa48c8f75d9f5da9bd08dbeae46142ff1` |
| `docs/evidence/overview-backdrop-tap/card-tap-terminal.png` | 6233 | DATA | `7a2f2289f6cb1dcf31e4d017265769563b9eb27d065cc0e9f351453f21a7315e` |
| `docs/evidence/overview-backdrop-tap/overview-before.png` | 35966 | DATA | `aaae7b98bbc9c44b2a7842080798db969d4b456ddbc6e8309113b6399ac52d0d` |
| `docs/evidence/overview-backdrop-tap/overview-retained.png` | 36020 | DATA | `cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88` |
| `docs/evidence/overview-backdrop-tap/shade-pull.png` | 29017 | DATA | `8eea0fd6d76f9aa12a0551f52024b56987f7f64f12794160a00dc8bf322546bf` |
| `docs/evidence/overview-backdrop-tap/side-back.png` | 36020 | DATA | `cd41143071204ffd096a6e9aa0fdccd6a71531c4d1a94205b17bcd886db24c88` |
| `docs/evidence/overview-backdrop-tap/side-tap-home.png` | 102251 | DATA | `880f1bc6d3bb49be989aa9c9903b7849ee377f7b2dd78add53f0335f51600de1` |
| `docs/evidence/overview-backdrop-tap/title-tap-home.png` | 102317 | DATA | `358adfa74c2011904c9062a9ac94e429cc7feab3f743282428d31dc57a126075` |

## Shell motion trace board captures, 2026-10-19

Native `grim` captures after injected uinput; full commands, failed budgets
and camera limits: `docs/evidence/coherent-shell/motion-2026-10-19/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/motion-2026-10-19/diagnostic-probe/held.png` | 28140 | DATA | `022cccd66d73e4dfd2f1d48c4a5e3e32abb901296e8a876d7c94a5359d814d08` |
| `docs/evidence/coherent-shell/motion-2026-10-19/full-after.png` | 30342 | DATA | `0fd107c75e8a68b2a3bf8cae56fadf5aa9814b108a179ecc1891d6b1cd8478eb` |
| `docs/evidence/coherent-shell/motion-2026-10-19/full-before.png` | 30342 | DATA | `0fd107c75e8a68b2a3bf8cae56fadf5aa9814b108a179ecc1891d6b1cd8478eb` |
| `docs/evidence/coherent-shell/motion-2026-10-19/reduced-after.png` | 31646 | DATA | `8aedb44255dd121e869fcc78c2845ae9dfbc52131d1ef9aa3c038ac41283e9b0` |
| `docs/evidence/coherent-shell/motion-2026-10-19/reduced-before.png` | 31646 | DATA | `8aedb44255dd121e869fcc78c2845ae9dfbc52131d1ef9aa3c038ac41283e9b0` |

## Shell motion camera correlation, 2026-10-19

Concurrent injected-input recordings and derived review contact sheets.
See `docs/evidence/coherent-shell/motion-2026-10-19/camera/README.md` for
clock alignment, observed movement and camera sampling limits.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/coherent-shell/motion-2026-10-19/camera/full-contact.jpg` | 244202 | DATA | `8f41ffe0be47661ffb7b4f75ea8a847eca8eb466c6457ef5af9ffebd4ca6d9e0` |
| `docs/evidence/coherent-shell/motion-2026-10-19/camera/full.mp4` | 1423087 | DATA | `e38a564b4f0a002e510a319eb9c94ca4aed51172d53c9cbeaeb5f57a76d6d695` |
| `docs/evidence/coherent-shell/motion-2026-10-19/camera/reduced-contact.jpg` | 245114 | DATA | `5a42db1dae662497c74822f66e22f7e3abfeb4ba158efe4859be2603b61ee82a` |
| `docs/evidence/coherent-shell/motion-2026-10-19/camera/reduced.mp4` | 1570474 | DATA | `62c08db87ee6b7110d7855ae14805c009c1c47be10804f3d528da4edbed2e9a2` |

## Retained-output live-client software captures, 2026-10-20 UTC

Board compositor PNGs and callback/release logs are described in
`docs/evidence/panel-paint/candidate-retained-output/README.md`.
No camera or real-glass interaction is claimed.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/panel-paint/candidate-retained-output/live/before.png` | 31333 | DATA | `cac6396187d3f193e964b389f5da86a80852635d2b0a2b8ce311279387241557` |
| `docs/evidence/panel-paint/candidate-retained-output/live/after.png` | 31441 | DATA | `a036bc8d1ca10157be62ee4fc1fab2535b2591c999c05244bca42388052c1a41` |

## Opaque-interior live-client software captures, 2026-10-20 UTC

Compositor captures described in `docs/evidence/panel-paint/candidate-opaque-interior/README.md`; no camera/glass claim.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/panel-paint/candidate-opaque-interior/live/before.png` | 31427 | DATA | `ec0e34b5236fbc340ed3afca3cd657df3dfe7dbcbc9909d21500b0cfdc4216a1` |
| `docs/evidence/panel-paint/candidate-opaque-interior/live/after.png` | 31382 | DATA | `7e629704a01b4463024d513233f49c65495e458246bff6239a4e647471631eb7` |

## Label-ink board software captures, 2026-10-20 UTC

Static setup equality and changing clients are described in `docs/evidence/panel-paint/candidate-label-ink/README.md`; no camera/glass claim.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/panel-paint/candidate-label-ink/static-before.png` | 30290 | DATA | `4fbe0ded570c91331436bfc5b73b5c78b6769bed5bede911913ca0817c16c6db` |
| `docs/evidence/panel-paint/candidate-label-ink/live/before.png` | 31450 | DATA | `1c00680d9329156e8764348c3b06d638edd55488c9f19fd54ef2359e1ef7c71a` |
| `docs/evidence/panel-paint/candidate-label-ink/live/after.png` | 31456 | DATA | `c32dbb9ce42ffb0a06c5f5d185cbe95424e128964c75296c9a7ea8766dc0c3b1` |

## Coalesced-scene live software captures, 2026-10-20 UTC

Changing clients are described in `docs/evidence/panel-paint/candidate-scene-coalescing/README.md`; current camera/glass proof remains unverified.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/panel-paint/candidate-scene-coalescing/live/before.png` | 31404 | DATA | `eace8062bd0f7d19d5887aeb823b5184e28c82132539b1874ca17aac360f10d1` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/live/after.png` | 31465 | DATA | `e7980631e2786f14afe4b7ef4960e2ee6b45dc66a66add188b95cac5fc8067af` |

### Qualified panel-paint camera proof

Full/reduced injected motion and sampling limits: `docs/evidence/panel-paint/candidate-scene-coalescing/camera/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/full-contact-1.jpg` | 306264 | DATA | `8fe55879676a9662c4d0c7ed068f7437869a22a4abe18145ca9315e400b9a426` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/full-contact-2.jpg` | 304601 | DATA | `6fb32d8d67ec0e046c31eea5614eb7fed410fdd98f41b722594cb990579db9b8` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/full.mp4` | 1346668 | DATA | `563259b918556d4182fcc2620f17cd567fca6682abd015eca5361d6572f93530` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced-contact-1.jpg` | 312434 | DATA | `5a2b89b995f2bb8fcfd03bb52f1c8b4d6c265b00e4dd7df77eab24400319e4ba` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced-contact-2.jpg` | 311815 | DATA | `b4eb088fec63029b100b283af1b6c71c0f403256a2e8172d02fdf65ec0e4e5eb` |
| `docs/evidence/panel-paint/candidate-scene-coalescing/camera/reduced.mp4` | 1259697 | DATA | `386de08ceb29b10af5330130f6b21329f65dffd2effe9fb124a4c7d875b43ea5` |

### Current source221 portrait headless scene

Twelve native software captures and limits: `docs/evidence/hdmi-shell-performance/current-scene-221/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/ordinary-a.png` | 8777 | DATA | `154e3568645238a0f6bc21fb72a41ae3e1126f9d9812df1b48836b0c1c0412bc` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/ordinary-b.png` | 8778 | DATA | `6b99b5674b661119e865270d33eaaddb0e043ae2d4ab574911f2ec9d05f69821` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/overview-a.png` | 21460 | DATA | `ad86810b1c0735f4cd2cedc112331afc6a52cf2e2787f8c004c452b99377247c` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn180-sampler-fallback/overview-b.png` | 21529 | DATA | `ac9718bad50f8071df99e33cee2c72b113d5cb71fafa4e49a65de8e567dac24d` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/ordinary-a.png` | 10532 | DATA | `1cb688812240d80a41acd853c8dda854df3c7041d62e3465f8981baa3b3250e1` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/ordinary-b.png` | 10555 | DATA | `47abdb889f5ec3a3ac1ee1e2a752a71ea2d2b75e6f04e398f1b909438a5841a8` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/overview-a.png` | 23374 | DATA | `b92c26ae53513519988f8533871b5ef0da5ce3d816f54e501034bc4c8fcfbae0` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-quarter-turn/overview-b.png` | 23311 | DATA | `7d76c47ba299309671042a7b4336c6d0090d2dee1f0f20e815d181d4c2185e3c` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/ordinary-a.png` | 10531 | DATA | `0772c695ecea3a4d3402ba2b8dbc6e467239cf5a86269d14b5cec16720590427` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/ordinary-b.png` | 10531 | DATA | `e1215e04cf0d51f0be7555e0b663909c8fb614cfa779936e78925dac57a2e9f3` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/overview-a.png` | 23372 | DATA | `33a74cc4d484efea10356015da31969b0fb55b632a3cd5a81ffe8d5ec0713097` |
| `docs/evidence/hdmi-shell-performance/current-scene-221/turn90-sampler/overview-b.png` | 23295 | DATA | `271b7cd1f072d238fb891a25ff068c01b07f43513430a699019c9e8425262659` |

### Landscape HDMI numeric scheduler/I/O traces

Compressed allowlisted numeric records; raw buffers, pointers and process names are excluded.
Provenance and limits: `docs/evidence/landscape-hdmi-stall-trace/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/landscape-hdmi-stall-trace/board/trial-a/traced/events.jsonl.gz` | 1862260 | DATA | `af2b216b1e6e6be97c2d8ec3aa74b7c7e5790747dfe93989aa142705fcf0c5b0` |
| `docs/evidence/landscape-hdmi-stall-trace/board/trial-a/traced-retry/events.jsonl.gz` | 1868852 | DATA | `8123fd85b5c5afad79a32b226bcf2de6a8c147b3792c83f95bf8f4e36f27f891` |

### Landscape DRM wait stack evidence

Address-free numeric/symbol streams; capture/postprocessing recovery and limits:
`docs/evidence/landscape-drm-wait/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/landscape-drm-wait/board/trial-a/traced/events.jsonl.gz` | 1856362 | DATA | `25d1f864fbce06099ae0f0af2bb3476de54cf5ff3506b1a133711705e2a647c3` |
| `docs/evidence/landscape-drm-wait/board/trial-a/traced/stacks.jsonl.gz` | 63547 | DATA | `99bab6a7531c1c5e97bf4c5f00052eb6a4afaea573358e069bb739cdc4154641` |


## Landscape connector-poll trace evidence, 2026-10-20

Deterministic gzip of sanitized numeric and allowlisted function/caller records.
Private raw traces are not committed. Provenance, commands, hashes and limits:
`docs/evidence/landscape-drm-holder/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/landscape-drm-holder/board/trial-a/traced/events.jsonl.gz` | 1857350 | DATA | `c17ccf67aa547ac359aee159ae2dc28452d8e68ff184cb2b6e92197690d2d1d6` |
| `docs/evidence/landscape-drm-holder/board/trial-a/traced/functions.jsonl.gz` | 23451 | DATA | `e60a160e2c036c989b8e3082cdf47e4d32d02060dd2a25982b63ed627bf5e858` |
| `docs/evidence/landscape-drm-holder/board/trial-a/traced-retry/events.jsonl.gz` | 1850954 | DATA | `9f7545361103f1308392285dc905b982f98a6d7b2c0696ac20167b6d5f1c5413` |
| `docs/evidence/landscape-drm-holder/board/trial-a/traced-retry/functions.jsonl.gz` | 23198 | DATA | `40ac701d2440a95cd9d4e2c0b95bb7024ef16fe51c28b4e111b984641e0d59ca` |


## Current splash baseline film, 2026-10-20

Diagnostic film, raw camera JPEG samples and deterministic gzip of numeric frame metadata.
Provenance and limitations: `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/README.md`.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/baseline.mp4` | 334583 | DATA | `3cb362a67335b160be5a16e7dca5a8be56e2efe52bbfcf025e4d9713781eb91d` |
| `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1426.jpg` | 37837 | DATA | `47c4afcb52a2d17c8adbf0db51c970f31f8013c2a4dac2e79ea48f6cd22a1fdd` |
| `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1431.jpg` | 37282 | DATA | `069973fa256f5b48a1cdd2463141fe9f887ec03a11d83b37fd8504da060cdfc5` |
| `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frame-1436.jpg` | 37689 | DATA | `3fd83b6c03c5b15f3980e793acca5072d97fb20a537a4e115aa10ea5fb3f1875` |
| `docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/frames.jsonl.gz` | 176478 | DATA | `6407b53f691f0fa16e814fbbc1eb0e6561b5427505442e58f1758446976716e7` |

### Splash DMA-request optical calibration (2026-10-20)

Proxies and original frame metadata for eight reversible panel-brightness transitions;
early boot alignment remains UNVERIFIED. See the trial README.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/camera-calibration.mp4` | 123494 | DATA | `1580c39907dbfa971f3d8bf8236689d734341ddda8a17e2fa3ce0b835176abd9` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/calibration-frames.jsonl.gz` | 18030 | DATA | `e9c1e3c374d9e6cdfdf3b2c62884dbdd45a8b06f3f398477d475ca9b8786ac26` |

### Splash DMA-request candidate warm boot (2026-10-20)

First120s viewing proxy, original7193-frame metadata, and untouched peak-score
frame/neighbor JPEGs; final clock qualification remains open.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-boot.mp4` | 432129 | DATA | `53d58204ec7eb7b6860d3d3564a40ff9421033c5df421253851d70264829717e` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frames.jsonl.gz` | 235060 | DATA | `d10957f38c4a58990b76473ae92bd5771e3f68dbed1606f6a2649802a4d9ed01` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1489.jpg` | 36989 | DATA | `750bc4fab6ce79dc1d5cbee5fb7e65b108c7959768ec9f843a1cf3f123c5a387` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1494.jpg` | 36987 | DATA | `095abfef584a31411c3428f197cdaf169f0071b6eb86bffbf4aa2dc06c22f318` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/candidate-frame-1499.jpg` | 36645 | DATA | `56583fb3d151f0134cfb9df79f30a5151d0cdc1b6bf76adc2300998dae7d424d` |

### Qualified splash DMA warm boot (2026-10-20)

Complete8993-frame viewing proxy, original clock/frame metadata and original
peak/calibration JPEGs. Empirical timing bound±75.244ms; see final proof README.

| File | Bytes | Kind | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/boot-and-calibration.mp4` | 1305901 | DATA | `db46cd51f93504cf2ad6e63473ba512c45af7b9be6286cd1fd056adee2ae0289` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0350.jpg` | 34946 | DATA | `530c7ed5bfdd2ebd7cb06f6d2bc855ced16d3b60a1fb7d3d847c5d93e6f489dc` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0355.jpg` | 37405 | DATA | `fe32471546f39087964a47bb032e688ebce9adb9350c4122018d63b5e640a8b6` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-0360.jpg` | 37575 | DATA | `df21ce7f4c3b35cd1bbde7573c0c70876294bafcc2df37deb80c12f049cc7a0f` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6922.jpg` | 36011 | DATA | `ad29534e4fdf62d2540480c8a88bae22cd939d18a49e976f7a8b24f1cdbc6483` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6952.jpg` | 59014 | DATA | `035b04a22e5de9fd5f5a2a41e9b5df0a30cdcefd3be0ce2402fb0b1cec6c35e0` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-6982.jpg` | 43511 | DATA | `978cbf2119bae4803fb9fef6edd6fd67947ff81388480f75f53711a84a8b842d` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7017.jpg` | 66278 | DATA | `877160f6475b5e1befb89d6d320d0555430238f2394a182835203bc146a5ec45` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7048.jpg` | 35617 | DATA | `d8cfe3266ef3aeb3c43f7ecfd32de6013d32bf637db58f840669db109c1698c9` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7079.jpg` | 64997 | DATA | `4ace712afa9bc03b4f7022be525e46aa8a35ba523ed3cef36a09b57f66ec63a2` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7109.jpg` | 42881 | DATA | `01b5c5ef63de3fed38058f55863d6cb1cab6e1996cb96af3c2f9f996ddc61ae6` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frame-7139.jpg` | 63498 | DATA | `ae75797fbec9a5fb7eb855595b7f2b2c7ec0562406d6c2bcdc0bf6ae06da86cf` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/frames.jsonl.gz` | 294304 | DATA | `95bdd638c97cfca7b5bf739a3e0f4ba4bdfbbbdf67033f91e2b8c9fee5080771` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/host-clock.jsonl.gz` | 121406 | DATA | `3fb586fb415d67425bb69b622de0a64818b2eddd43f0bf12a117ceec5aea34c6` |
| `docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/final/timing-analysis.json.gz` | 171304 | DATA | `09a52ca5c5b3b3732cec96e68ca4c5a7c3acffb6f42f00cc14540ffbce2cef61` |

## Background video board trial — 2026-10-21

Data only: native injected-board captures and a scaled camera excerpt.
See `docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`
for the failed gates and distinct evidence classes.

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-covered.png` | 5430 | DATA | `b0f531e19c7ea4a8d64c911e57c996a784374ffd7552ab6ff4ca57f258a28051` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-panel-video.mp4` | 382648 | DATA | `38d331f1606562c4cc6b359cfb4e7ef472a3be8f2c6b12f70b4aa7ae4f2c7899` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-static.png` | 121845 | DATA | `ac95204a3fbc83d8cbd0e7ee60359809c96b88be8c0ee923698a24d0aeb2fca9` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-video-second.png` | 123271 | DATA | `bad4d7951fccb5f1238a63703be1d701b6a62a9fd5545cbbaae6364e56abc421` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/baseline-video.png` | 137730 | DATA | `b6525a11d4555f88dfc7fc37e501b0baa1d2a88e0c052c464fc96b9be3593323` |

### Final coverage candidate media

| Path | Bytes | Class | SHA-256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/panel-pause-resume.mp4` | 900686 | DATA | `99a2c6b0191ee7147957f6d9dd6c0df9745b2d7150f64148c3b28a8069851461` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/postboot-home.png` | 106868 | DATA | `c751f7951fccb20f9f5b5048ce070d9c731516a9e5edfa625c38ac1b4993b44d` |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/candidate2/reduced-motion/paused.png` | 124538 | DATA | `dac16dda343c1c88ed8888357c78bd83d690f037d9580a0945eb45528c0bd54e` |

## Render-profile numeric trace, 2026-10-21

Compressed allowlisted numeric scheduler/syscall events; no raw trace or process names.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/omarchy-themes/background-video-board-2026-10-21/render-profile/traced/events.jsonl.gz` | 558197 | DATA | `10554387857e0f2befb3b3f7b5a95b50281d63d470345b6c01a328eb08603ae5` |

## App-drawer scroll captures, 2026-10-22

Native `grim` captures of the drawer before, during and after an injected scroll.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/interaction-jank/drawer-scroll/run4/after-close.png` | 6233 | DATA | `7a2f2289f6cb1dcf31e4d017265769563b9eb27d065cc0e9f351453f21a7315e` |
| `docs/evidence/interaction-jank/drawer-scroll/run4/drawer-open.png` | 68768 | DATA | `63af3f4281611d470feaf69ce22843d7f7b50bf88d7cdf22a3ee06497dcb821e` |
| `docs/evidence/interaction-jank/drawer-scroll/run4/mid-scroll.png` | 61738 | DATA | `4cc7d9bc7a234671639008ec5c969923657d4de75b318b2f63beb4203aab1fd1` |

## On-screen keyboard probe captures, 2026-10-22

Native `grim` captures of an owned trial window before, with and after the injected keyboard show.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/interaction-jank/keyboard/probe1/before.png` | 3398 | DATA | `55381f254639278c06843516fe461cf2666da9674cdf9beec4182426e3988743` |
| `docs/evidence/interaction-jank/keyboard/probe1/hidden.png` | 4148 | DATA | `4f6eef5de15b27915e181b8b10faaf1c0a71bc5bcafebe50094c973df652917b` |
| `docs/evidence/interaction-jank/keyboard/probe1/shown.png` | 14778 | DATA | `fc2b26d3cf54847501310ef5675d445d2f387a5d9a44d0ea1a875c136ea5889f` |

## Ordinary-card video probe captures, 2026-10-22

Native `grim` captures of the live Video card before entry, in the deck, after a drag and expanded.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/interaction-jank/ordinary-cards/probe-video/arm-focused.png` | 140435 | DATA | `5672cfb5929a3af54d211a76bac5ae34f791cf1f6721b996368ec7f1ae60cc4b` |
| `docs/evidence/interaction-jank/ordinary-cards/probe-video/deck-dragged.png` | 191991 | DATA | `b4b2feb54cbe12d3b0cb53336d80bfc8cfd91a4b815b9f33b7ab929db068b45e` |
| `docs/evidence/interaction-jank/ordinary-cards/probe-video/deck.png` | 148089 | DATA | `d96ea9a35c885e2007c8a5cac2c52fc80895e2a4f89d1a1361cb0c7eac699f29` |
| `docs/evidence/interaction-jank/ordinary-cards/probe-video/expanded.png` | 401871 | DATA | `0b0be5a757efced534c41d28eeafe9013f364edf9f1078cfcb2a9899f896a182` |

## Shell design review captures, 2026-10-26

Native `grim` captures of the fixed shell surfaces and drawer apps; see `docs/evidence/shell-design-review/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/shell-design-review/build-1r8zfd5s/r3-themes.png` | 88364 | DATA | `01b122e485f94d6198afbc0eb8502cc06391277edf382f895d8c63d3c5d53ff7` |
| `docs/evidence/shell-design-review/build-9kam3kq9/files-buttons-zoom.png` | 15262 | DATA | `1812d04b9e217008ff82a7834baa363d79189e00c6d9d7792411aa391517dbee` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-drawer.png` | 70350 | DATA | `69bfb72118c3256f4356b77a2710d5e61c171e45d2b0ea411028fa75cc625603` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-files.png` | 15079 | DATA | `7ea1fce0beb946d4a82aa40a4ea0b35f38ff35e76d76973c7d13588e5f67404e` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-home1.png` | 107965 | DATA | `4343c20dc5e30f0445ce030cf121b68044afe36bca884a3622a1f10837d716ca` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-ov1.png` | 32922 | DATA | `34e366cb0bb5b36e61057258a5819193ebb8a9dc15c7ba506a6d9268ee0e9247` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-ov2.png` | 33689 | DATA | `85e1c182777512c610f2629a7ce62be0ddd27c0301355fe2262a638b51a9b941` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-settings.png` | 64202 | DATA | `ed400d49773fcfa67bb1059062bfea76b6fe889b11234d598191e4417352d44e` |
| `docs/evidence/shell-design-review/build-9kam3kq9/r2-shade.png` | 26071 | DATA | `03337109f40e66e8d74ab77c42d007340a864cc34040254ebe375a22b70a6e1c` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/04-settings-scrolled.png` | 56419 | DATA | `91a7ab0408513305fcbde2180dcce8cabbf0a9a99f4400afd216dbbfe5937005` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-2048.png` | 11155 | DATA | `36cab3e01df021bb06a38d244df12c8f6ccf6890d30c77ad3fda0b706f658cfa` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-clock.png` | 7016 | DATA | `5dc1f1b00be815aff60431c57aca46db89de9ea4bf902583076caebd3735d832` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-fifteen.png` | 14696 | DATA | `3c0827cb2de58efe9e1306e20989620c2d158addbe1aaeb8ca97680b68e9b408` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-galculator.png` | 18725 | DATA | `69a8038a2d73680c6c00b41dfa78831b0547a987936db32a4952e52ba793bfcb` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-net.png` | 9951 | DATA | `f01245f4ac1379cb56c757e2de832b330bbfb3faa5d0b7c65c1b95b761fc289d` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-nethack.png` | 29011 | DATA | `ae0dd731fc9c405e6f0a1e70abc4048e1e203b6196457efbbe01548278d805dc` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-samegame.png` | 8065 | DATA | `c74e282b77e30a09409e1b1406f612768bb651ee035824b112914b586c137f32` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-sixteen.png` | 17330 | DATA | `32a96813757fe7feb0d533314aa1de7bb72c7d4094c72edb3588369731101fbf` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-timer.png` | 8204 | DATA | `2f99703c82316d3c4752faecfabbb59cd36a5e35ea04bc58357320ec21e8e3db` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-viewnior2.png` | 6581 | DATA | `4cea40933d790e29bd13cd92b5004b8b22388eb8bac1fc8945b4c8808218f035` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/app-zathura.png` | 4209 | DATA | `008f58267065c92f33871018f7d6f9e909d7326fea8efbc215224eab12bec22c` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/files-buttons-before-gtk4-ini.png` | 16460 | DATA | `ea4ec7c895a41d1650724e712607beb0c2ef0c6b9a18c104bbefb1ecffbf878c` |
| `docs/evidence/shell-design-review/build-9rbjw6vl/ov-2-after-side-tap.png` | 106020 | DATA | `9d3efc0ef39905ff634d3f3bd842cad02022d1ec894240c12760804639295ec2` |

## Design-review leftover captures, 2026-10-26

Native `grim` captures of the charger line, the framed chooser slices and the Timer controls; see `docs/evidence/design-review-leftovers/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/home.png` | 102638 | DATA | `921656fafa16535c04dcbe8cf22c52b94a72b596d0a1ec601e8dc12891225fa5` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/themes.png` | 93800 | DATA | `6af9d299f51851fa1f88dc0233920e6432cdc9b4421e53b550f8ca7f7c94403f` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t0.png` | 8204 | DATA | `2f99703c82316d3c4752faecfabbb59cd36a5e35ea04bc58357320ec21e8e3db` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t1-plus.png` | 8206 | DATA | `e6035e1ecd65eafc79b32e6c978bac2c44da61262f730e48811b52dfdc7cbe79` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t2-minus2.png` | 8197 | DATA | `643da8791a919160b1d0b84b58616025febcaf0674143ffaaf3b8f618e8c2712` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t3-start.png` | 8081 | DATA | `3963702782ed820274a077e7f8985bee545317fc43a8ae57193a1ac0e6c3f685` |
| `docs/evidence/design-review-leftovers/build-qh3i7b3f/timer-t4-reset.png` | 8197 | DATA | `643da8791a919160b1d0b84b58616025febcaf0674143ffaaf3b8f618e8c2712` |

## Modem shell UI host renders, 2026-10-26

Host renders of the Cellular and Location pages and the shade indicators from fake state files; see `docs/evidence/nrf9151/shell/host/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/nrf9151/shell/host/cellular-no-sim-1232x568.png` | 39393 | DATA | `c85f4021902b8189254f6683290c85abc90314592827aebf283cd09a0b0070a9` |
| `docs/evidence/nrf9151/shell/host/cellular-off-1232x568.png` | 38697 | DATA | `799a4c333cd811e18a245e8c78d4321641617b7ac7099311fd81c1f378efdd9b` |
| `docs/evidence/nrf9151/shell/host/cellular-pin-1232x568.png` | 49156 | DATA | `b5f780d2421ceab8f1b00a930d4c4815334759d82099d4f7e5a83c4df14deea2` |
| `docs/evidence/nrf9151/shell/host/cellular-registered-1232x568.png` | 44146 | DATA | `2219d75492bf0b6ea234d9394321c3c74eeb9444f59e0d31413eadfe6751ec22` |
| `docs/evidence/nrf9151/shell/host/location-fix-1232x568.png` | 18148 | DATA | `bd9ddb325b0de1968dfd44cbbfb1847186f9d340e3759a89211763db61051652` |
| `docs/evidence/nrf9151/shell/host/location-off-1232x568.png` | 17652 | DATA | `0e3a0380935ea6f252b3808669b10ea2ffc2395f6df929c9b0c2e13828fb41bb` |
| `docs/evidence/nrf9151/shell/host/location-searching-1232x568.png` | 20935 | DATA | `f2349ee140e8c47a067c17da59ada989de2b0b85623592568c8f56ecef1cdc64` |
| `docs/evidence/nrf9151/shell/host/settings-no-modem-1232x568.png` | 63650 | DATA | `b5da8264118b3ed15c47ebedac04580ab237b694965508532880607783a4fb3d` |
| `docs/evidence/nrf9151/shell/host/settings-with-modem-1232x568.png` | 72644 | DATA | `3008eebb06ab7418fcaee1d030f688c0997b2628f6fac6241ccf4a90c9261804` |
| `docs/evidence/nrf9151/shell/host/settings-with-modem-no-sim-1232x568.png` | 71564 | DATA | `c5addf45b783fa6bc7535490d240cf9b2ece6fa918f5c6e3d451a5c1cdcfe90e` |
| `docs/evidence/nrf9151/shell/host/shade-both-off-1232x568.png` | 60791 | DATA | `97ae17b3b6f5f9134bcac568a2b5da42fce12f1786bff574895fd80097d16e4f` |
| `docs/evidence/nrf9151/shell/host/shade-both-searching-1232x568.png` | 62196 | DATA | `03ca1b30d63eccd95480330ce8c1bbbde74d70db7d2d60e5ab9d47097a77dbb1` |
| `docs/evidence/nrf9151/shell/host/shade-both-searching-no-battery-1232x568.png` | 60154 | DATA | `387a0f55f3eefe14779b63c7b8d7d0ad19c51d82e4ea96c7806a57e55f045e15` |
| `docs/evidence/nrf9151/shell/host/shade-cellular-3-bars-1232x568.png` | 61061 | DATA | `b8a86e5bc1196becc6376911e78b5bae384f4d6fb70c6da5cafa62fde7ba857b` |
| `docs/evidence/nrf9151/shell/host/shade-fix-no-service-1232x568.png` | 62186 | DATA | `f7ba6d11898be9a13ebf17d8f043b056e88d56ae483c138b7e4d715f231e33ea` |
| `docs/evidence/nrf9151/shell/host/shade-no-modem-1232x568.png` | 60791 | DATA | `97ae17b3b6f5f9134bcac568a2b5da42fce12f1786bff574895fd80097d16e4f` |

## Modem shell UI board captures, 2026-10-27

Native `grim` captures of the Cellular and Location pages and the shade indicator; see `docs/evidence/nrf9151/shell/board/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/nrf9151/shell/board/cellular-off.png` | 29498 | DATA | `647017c9fd5c13394d9f802b8c33519a6b7cc1b755df662893b27b2710f3b0dc` |
| `docs/evidence/nrf9151/shell/board/location-off.png` | 14570 | DATA | `ffe2aedcb932831363b5fe0f47672478f1cd1c960dce341b1ddc30ad2bcc3a7a` |
| `docs/evidence/nrf9151/shell/board/location-on-searching.png` | 16971 | DATA | `b7b162ede1268ba8152699d63252d77debbb00d04ac51b75fad0256b6c4ca2f3` |
| `docs/evidence/nrf9151/shell/board/settings-rows.png` | 67976 | DATA | `7fbef27941c78089dd1dfa23197585dd9555a255b61bae29fbfa15fa24d82535` |
| `docs/evidence/nrf9151/shell/board/shade-location-searching.png` | 27990 | DATA | `4ffe1aee3d9c123f6a97264824126d2c830145dedafa22879e2155910f45224f` |

## Landscape shade host renders, 2026-10-27

Host renders of the wide shade's time header, status line, tiles and list heading; see `docs/evidence/shade-pass/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/shade-pass/host/shade-modem-location-off-4-1232x568.png` | 94826 | DATA | `555d3f164a39bf46442619ca1f809f2b799d8cc58325f3d22f70372c6f88229a` |
| `docs/evidence/shade-pass/host/shade-modem-location-on-4-1232x568.png` | 97254 | DATA | `b05ead37b6e068cfc444d518712c8e18c86f3d806ea760557a9c1ff76eb2453e` |
| `docs/evidence/shade-pass/host/shade-modem-location-on-4-568x1232.png` | 68430 | DATA | `de4e1a572029cd2dcba7aeab262ad9805beccc7bd304dcfa1abfde7596eed831` |
| `docs/evidence/shade-pass/host/shade-no-modem-2-1232x568.png` | 70156 | DATA | `ab62897f52ec497470d3d0f95fd012fb5341937b63e6ae7d6ad8cb251626e040` |
| `docs/evidence/shade-pass/host/shade-no-modem-empty-1232x568.png` | 42462 | DATA | `8c767bb158c66c366fc42370d088844df6a68c9dd53e8d66f50a431ddc74ffe9` |
| `docs/evidence/shade-pass/host/vision-100-shade-1232x568.png` | 63963 | DATA | `72f5b59602c2f755dfe7377fe6e361974799186b957e0d6152755cb7713f38cc` |
| `docs/evidence/shade-pass/host/vision-200-shade-1232x568.png` | 83052 | DATA | `4fb9f45a606c35906ae0088d5ccf40eb3a3e48631838343373a43c6754246e1a` |

## Landscape shade board captures, 2026-10-27

Native `grim` captures of the wide shade and its tiles under injected touch; see `docs/evidence/shade-pass/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/shade-pass/board/shade-open.png` | 41547 | DATA | `5a763fb2bd58bfaa97a1772cccadc9840a781494ef3afb05a3ad1cc55f611455` |
| `docs/evidence/shade-pass/board/tile-cellular.png` | 29498 | DATA | `647017c9fd5c13394d9f802b8c33519a6b7cc1b755df662893b27b2710f3b0dc` |
| `docs/evidence/shade-pass/board/tile-keyboard.png` | 37838 | DATA | `5932c81af1c19334cbd9743c6bb44b9a04ab07fda4afa2dfd6bcb106f430dba5` |
| `docs/evidence/shade-pass/board/tile-location-off.png` | 39183 | DATA | `87f59585fd05235620a5269a4bcf65d4a194d1bdab3e2015fe0a41137ab5792b` |
| `docs/evidence/shade-pass/board/tile-location-on.png` | 40677 | DATA | `3bc2788b3b27066248c37349f56d892822df1d24782e2b8a2bd62f60cbf4832f` |

## Base-key drawer and overview board captures, 2026-10-27

Native `grim` captures of the key-focused drawer search and the overview under injected keys; see `docs/evidence/base-keys/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/base-keys/board/keys-after-enter.png` | 8165 | DATA | `a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6` |
| `docs/evidence/base-keys/board/keys-drawer-open.png` | 70373 | DATA | `ee7513ae8fcfc031781673cfef7cab622fc831f615df553c9507c0bea46f6b12` |
| `docs/evidence/base-keys/board/keys-drawer-ti.png` | 10996 | DATA | `10f202da0963924b537d5a768e30ff7a30ae1309fb52204edbbbf8bec4c0ec0b` |
| `docs/evidence/base-keys/board/keys-overview.png` | 77558 | DATA | `97ca6176dfc6c5e8a5cdbe45e807840855e652b0ea29cad1c30245d3a4270b0c` |
## Help refresh host renders, 2026-10-27

Host renders of Help's Touch and Keys groups from `render_help_refresh`; see `docs/evidence/help-refresh/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/help-refresh/host/help-landscape-1232x568-end.png` | 90045 | DATA | `fac69f720ae8595aa5c6c9e8fe1c404cdc6bbff7da2014b551a3f57ec3055661` |
| `docs/evidence/help-refresh/host/help-landscape-1232x568-top.png` | 97118 | DATA | `4df953a8f63c648fb98e4d9b3f3384aa875ad7aeb4f9a0825ff1c264de0f3eb4` |
| `docs/evidence/help-refresh/host/help-portrait-568x1232-end.png` | 100905 | DATA | `b7b8131dadb638854b5f0d0cadb4cd8d4bf3588ea16c73134f3ff076cd5bce8e` |
| `docs/evidence/help-refresh/host/help-portrait-568x1232-top.png` | 110636 | DATA | `e852cf5374353cfd8f06fab09aa5553df316da619c36590bafd73458bda0934d` |

## Settings About and Date & time host renders, 2026-10-26

Host renders of Settings with its Date & time and About rows and both pages from `render_settings_about_evidence`, using fixture values; see `docs/evidence/settings-about/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/settings-about/host/about-100-1232x568.png` | 42819 | DATA | `cd13a6de926d5f23e04f9de840f731f55539da7a12a92cec4f9f2c49c0bc4f6c` |
| `docs/evidence/settings-about/host/about-100-568x1232.png` | 49853 | DATA | `f4a36975306e53dfbab3d21ad7b03fdaf557ce399d69f3d397e60ea0168b15e8` |
| `docs/evidence/settings-about/host/about-200-1232x568.png` | 59725 | DATA | `9466b3d658de0a0d4ec4c7d2b19ce60533b93f6794f4e6a9d2fad23528d14705` |
| `docs/evidence/settings-about/host/about-200-568x1232.png` | 77086 | DATA | `439715e345321a22b333f73d4a91ce5dffdf616e985eafec9909d2819e2cd5a5` |
| `docs/evidence/settings-about/host/date-time-100-1232x568.png` | 41792 | DATA | `8d3f07c82194d46c6cf1ec3e665d7800deabdcc4d3bebd032cf7070d0d51d293` |
| `docs/evidence/settings-about/host/date-time-100-568x1232.png` | 48268 | DATA | `3061985905c888bfdda28d9aa59fdc9354e0b682d58f03527a32df8a8dbaa73e` |
| `docs/evidence/settings-about/host/date-time-200-1232x568.png` | 61421 | DATA | `eba08d7e6fa17267dd36fc8f4947bd7353b7df4fd89a61b4678105ac9fe760f7` |
| `docs/evidence/settings-about/host/date-time-200-568x1232.png` | 72534 | DATA | `1496cfa8ed436effba327ec09a5d3f2dbfa7a72355d7d92d82aa651fea3a26cf` |
| `docs/evidence/settings-about/host/settings-100-1232x568.png` | 76764 | DATA | `35a944ae92b2c49f3f447a87e9cefe0500693680d15735ed3c156a87adcc07a5` |
| `docs/evidence/settings-about/host/settings-100-568x1232.png` | 71041 | DATA | `e44d2b81c60d348ba3e6c396d8cc13e16fd24bff9c9a8db6ae49ac5e9b0bd754` |
| `docs/evidence/settings-about/host/settings-200-1232x568.png` | 82442 | DATA | `2813bdad2345e8a71f89c134e528744bfb3fb681acbc70c8a138e18eaf3185cf` |
| `docs/evidence/settings-about/host/settings-200-568x1232.png` | 78407 | DATA | `86aa7eca83e2fd517d58f9d26e9ee2d0b76818569bd2f43d2ef55ed0fd13e416` |

## Do Not Disturb host renders, 2026-10-27

Host renders of the landscape shade (three tiles across, quiet mode off and on, with and without the modem) and Settings' Do Not Disturb row from `render_do_not_disturb_evidence`, at 100% and 200%, using fixture values; see `docs/evidence/do-not-disturb/host/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/do-not-disturb/host/settings-modem-dnd-off-100-1232x568.png` | 79237 | DATA | `15dec396047d94d1aedf26f1ceb70dac174711285627106def9c585a1d65a0a3` |
| `docs/evidence/do-not-disturb/host/settings-modem-dnd-off-200-1232x568.png` | 81674 | DATA | `2ad24f78fb2c4dc2f832491e6083f5b8fadbd0778bb35a00bbaab41d6b049da1` |
| `docs/evidence/do-not-disturb/host/settings-modem-dnd-on-100-1232x568.png` | 79166 | DATA | `4684ddab1dda35dfc3f687c2bc5f0f546d06b06cbad24a0523368d0badc4cab7` |
| `docs/evidence/do-not-disturb/host/settings-modem-dnd-on-200-1232x568.png` | 81674 | DATA | `2ad24f78fb2c4dc2f832491e6083f5b8fadbd0778bb35a00bbaab41d6b049da1` |
| `docs/evidence/do-not-disturb/host/settings-no-modem-dnd-off-100-1232x568.png` | 77994 | DATA | `bc448a0e7be03d738432bf3437ce21cfd3ed6f4e1242aa74aa02a1733a7b8e26` |
| `docs/evidence/do-not-disturb/host/settings-no-modem-dnd-off-200-1232x568.png` | 82904 | DATA | `fba3b014bcf4c6de0752258cfe8134fd2543c55f2b102e2bfa654327bd9fe513` |
| `docs/evidence/do-not-disturb/host/settings-no-modem-dnd-on-100-1232x568.png` | 77610 | DATA | `fee1336c96da1c6a42f26223a282bab45aecfef88432431f7ca94279154d8639` |
| `docs/evidence/do-not-disturb/host/settings-no-modem-dnd-on-200-1232x568.png` | 82872 | DATA | `c0fbd05aea4d7bb9e1f325f9c79d923d6562f35b76d397cbedd39d00dc9bc00a` |
| `docs/evidence/do-not-disturb/host/shade-modem-dnd-off-100-1232x568.png` | 76917 | DATA | `983767feab09655959f4b07df6ed880c8def0d67eb801762a79153e0f0f1e3db` |
| `docs/evidence/do-not-disturb/host/shade-modem-dnd-off-200-1232x568.png` | 89864 | DATA | `2ef0c71171fcdd5a83da761efa0b20d7d16813ca41c67840d305f76efa9904de` |
| `docs/evidence/do-not-disturb/host/shade-modem-dnd-on-100-1232x568.png` | 77412 | DATA | `606d263c15ff8f4308d023049ab462c7b0b08fd31ddc1e39b7c3c8343693e4d8` |
| `docs/evidence/do-not-disturb/host/shade-modem-dnd-on-200-1232x568.png` | 90414 | DATA | `93c471d5a0aaccf4f87d2c818022dc51130d75c4309ac8f69f345a43b8295187` |
| `docs/evidence/do-not-disturb/host/shade-no-modem-dnd-off-100-1232x568.png` | 69154 | DATA | `7155ae4fa8442848b6a58a7f126efc1a328101f6505ef1d5a46084283157ad7b` |
| `docs/evidence/do-not-disturb/host/shade-no-modem-dnd-off-200-1232x568.png` | 83675 | DATA | `d1e08c6a3cfeea0b9d727ebe3da13ccf7d011c617b51957ba52323f900990298` |
| `docs/evidence/do-not-disturb/host/shade-no-modem-dnd-on-100-1232x568.png` | 69491 | DATA | `e76b806b6e6ab1feb082b3d61a64d7a2150ae25507bda362886f6833272245f7` |
| `docs/evidence/do-not-disturb/host/shade-no-modem-dnd-on-200-1232x568.png` | 84252 | DATA | `55015f7afe14eb3039ac9c3748aede809a4763b8f5b08599506789fd7e21cdd5` |

## Idle-on-charger Settings host renders, 2026-10-27

Host renders of Settings' "Idle on charger" row (Clock and Sleep, with and without the modem, at 100% and 200%) from `render_charger_idle_evidence`, using fixture values; see `docs/evidence/clock-display/host/README.md`.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/clock-display/host/settings-modem-charger-clock-100-1232x568.png` | 61877 | DATA | `18503cd696af72eaf4e2bf09bccfc0a28d01d867046cde5a30dea50ca720014c` |
| `docs/evidence/clock-display/host/settings-modem-charger-clock-200-1232x568.png` | 58432 | DATA | `b24c9e82ebdec6312c53dc2b6383afbc00b23082d2f57c28d9c15a450a7ffcbb` |
| `docs/evidence/clock-display/host/settings-modem-charger-sleep-100-1232x568.png` | 61742 | DATA | `fedb89f7175f65e28d8094b09d1aec18920295313b5bbe0fc4772cb2db5a9d14` |
| `docs/evidence/clock-display/host/settings-modem-charger-sleep-200-1232x568.png` | 58008 | DATA | `a7b22b301f436bc8a9d9728bfac5665b0f769f4bb08d43177c6c60e32c23787d` |
| `docs/evidence/clock-display/host/settings-no-modem-charger-clock-100-1232x568.png` | 82571 | DATA | `ced3dbed070f2c6544af0e655650e279edb58bbcc8ee5d9f636b73935cf0bb78` |
| `docs/evidence/clock-display/host/settings-no-modem-charger-clock-200-1232x568.png` | 79319 | DATA | `7d64e3a4ba90c53b084eff25f7f3ecd5e7f19c4bae3df148fc05c17828d8d4aa` |
| `docs/evidence/clock-display/host/settings-no-modem-charger-sleep-100-1232x568.png` | 82439 | DATA | `0135b004c98b8e966e35873b5944db39f8f10cd5c6cdece1cb2d572fba5ee102` |
| `docs/evidence/clock-display/host/settings-no-modem-charger-sleep-200-1232x568.png` | 78838 | DATA | `802ee26b6d5412269cd2a136e10a96aed417a6c706fe7a0cbd478cbb646ebc8f` |

## Board evidence: Help, GTK touch floor, alerts, shade

Native grim captures from the board for the Help refresh, GTK touch floor, app alerts and shade Location tile changes.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/help-refresh/board/help-landscape-1.png` | 75356 | DATA | `92bd21cfb151dfd57daecc902631064f1fdf77b7fcfa0c6e01cf20c698e5343d` |
| `docs/evidence/help-refresh/board/help-landscape-2.png` | 87922 | DATA | `2d7b38beb80c40e57368e45d08aeae55f65adaa7df11b5a589ed82e749427ec3` |
| `docs/evidence/help-refresh/board/help-landscape-3.png` | 70890 | DATA | `b4da560e3ff60590e114fd9be71714ae1c4b9caa5d9568f7fbe089ef32f279c1` |
| `docs/evidence/help-refresh/board/help-landscape-4.png` | 70890 | DATA | `b4da560e3ff60590e114fd9be71714ae1c4b9caa5d9568f7fbe089ef32f279c1` |
| `docs/evidence/gtk-touch-floor/board/files-landscape.png` | 15254 | DATA | `7b020e6c5d2966120e47ab8060047cb63c7cfb4bb073ea0399385c2a994c4206` |
| `docs/evidence/gtk-touch-floor/board/net-landscape.png` | 10348 | DATA | `0972065dac53965f8d04136a7102a3a78654a41cde4cfd2e1c3cf3250a5e5f7e` |
| `docs/evidence/apps-alert/board/banner-critical.png` | 6699 | DATA | `9a8a1484c0bf835b8e1db51cba8fbd43db9304b806b09a87099ec158bafb59cd` |
| `docs/evidence/apps-alert/board/banner-shell-claim.png` | 6699 | DATA | `9a8a1484c0bf835b8e1db51cba8fbd43db9304b806b09a87099ec158bafb59cd` |
| `docs/evidence/shade-pass/board/tile-location-searching.png` | 47832 | DATA | `b5a84ae6de237ea79d49c7d1968230ba1449d60b4a46877fc14c4b589abed1ac` |

## Board evidence: overview All apps, idle, focus keyboard, About

Native grim captures from the board for the overview All apps entry, idle dim/off, focus-raised keyboard and the About and Date & time pages.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/overview-all-apps/board/after-tap-drawer.png` | 90266 | DATA | `aa49129286a0bc7a64317e140d8eff66a333d683ebb3057d9d1709765057f428` |
| `docs/evidence/overview-all-apps/board/overview-title-row.png` | 9846 | DATA | `228673f5089241367a5e42a2a220898d92b8b5d0ce09c25e7b48e64d3576798e` |
| `docs/evidence/idle-dim/board/after-wake-tap-on-video.png` | 203546 | DATA | `b2f023db4e9850349a87acdc556e3e592acde2a40cdfd574ac872ae6522476cd` |
| `docs/evidence/a-focused-text-field/board/overview-keyboard-lowered.png` | 94301 | DATA | `72e64e56d9eb7291647bf4b5ef1031b0bda88821c444f8b17ae93690c936f51e` |
| `docs/evidence/a-focused-text-field/board/terminal-focus-keyboard-up.png` | 13000 | DATA | `4e2e9d23596e3775f1a6d44ae4ad1d78cbdf77f920f7c4f5de3d1dc294cbe265` |
| `docs/evidence/settings-about/board/about-landscape.png` | 32208 | DATA | `9cb6b59a3a2c1f84a714320d30a57e93daea00191e1221d9fc0bdc08138f035e` |
| `docs/evidence/settings-about/board/date-time-landscape.png` | 33323 | DATA | `a806edf12f14f2e36e7fdb7b6b944b6385cb104dc0a421e67f770cc5120f07f1` |

## Home notification count host renders, 2026-10-27

Host renders of Home with the pending-notification count 0, 3 and 100 from `render_home_notification_count`, over a synthetic 30-app layout; see the change `home-shows-how-many-notifications-wait`, task 1.3a. Host render, not glass.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-notification-count/host/home-count0-100-1232x568.png` | 27974 | DATA | `80010bf1889149b71c6214cd678e44e3deb640f066137e1654a17ec58ac7f67b` |
| `docs/evidence/home-notification-count/host/home-count0-100-568x1232.png` | 51169 | DATA | `af9dad629c977316c22a67cb1b3b776ef7e6a2ec082d5134bcd39d400701f6d7` |
| `docs/evidence/home-notification-count/host/home-count0-200-1232x568.png` | 27974 | DATA | `80010bf1889149b71c6214cd678e44e3deb640f066137e1654a17ec58ac7f67b` |
| `docs/evidence/home-notification-count/host/home-count0-200-568x1232.png` | 58603 | DATA | `2460a23bcf6640f7f0597b517b123329aae0e7a70cb638259730ebf38e8f80f3` |
| `docs/evidence/home-notification-count/host/home-count100-100-1232x568.png` | 29704 | DATA | `13049fd83f80a62a1262ff3d5507525588fd63f3d0d2929c72678ad51700eeae` |
| `docs/evidence/home-notification-count/host/home-count100-100-568x1232.png` | 52790 | DATA | `512670ef6c0f2fe4ad35642e59c675be1e924348fa5525bb22c736eb6bf6483d` |
| `docs/evidence/home-notification-count/host/home-count100-200-1232x568.png` | 31024 | DATA | `ab81f67c8fe591dd21b99d6344c5fa9efe33fb48b42b45b3cde75ffabdbe85f3` |
| `docs/evidence/home-notification-count/host/home-count100-200-568x1232.png` | 61530 | DATA | `a53fbcf615bdc46a19122de89fcbf6ed30f5d64fcda44c316fa5d25d2676de7c` |
| `docs/evidence/home-notification-count/host/home-count3-100-1232x568.png` | 29486 | DATA | `ca476068973c1ab5d96817129fb129c8fa30c472e52fdd6be0441655d597b19b` |
| `docs/evidence/home-notification-count/host/home-count3-100-568x1232.png` | 52595 | DATA | `edd9ea707a12271eded1a961224418217323d0677fd7d4be9865799fe82f8426` |
| `docs/evidence/home-notification-count/host/home-count3-200-1232x568.png` | 30623 | DATA | `d0971b44ef6604cc9f0b5c11d07586a3a03636d66c36b57df382e3b61c84fa2c` |
| `docs/evidence/home-notification-count/host/home-count3-200-568x1232.png` | 61122 | DATA | `01097affc6893ea9e3278d8ec8676e04926ca5489d0d343d25bca12c083a72cf` |

## Board evidence: Timer alerts and focus keyboard

Native grim captures from the board of Timer expiry banners and the Timer with the on-screen keyboard kept down.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/apps-alert/board/banner-timer-card-open.png` | 5801 | DATA | `945cb4443ee71bdec39ad1e2fef64607872b73d6a018be0478a728e22cefa191` |
| `docs/evidence/apps-alert/board/banner-after-shade-closed.png` | 97815 | DATA | `f2ab317e35c30c7e9c7d88327eb66ced42332be2be79cc02132d11d2f21b7de6` |
| `docs/evidence/apps-alert/board/banner-after-shade-ordinary-boot.png` | 97815 | DATA | `f2ab317e35c30c7e9c7d88327eb66ced42332be2be79cc02132d11d2f21b7de6` |
| `docs/evidence/apps-alert/board/shade-gnotification-history.png` | 71822 | DATA | `36ad1f8093998f5f3d59d19227729d99b07c0beca28b5563410bc425997b7522` |
| `docs/evidence/apps-alert/board/banner-gnotification.png` | 30020 | DATA | `0c07a5f9900750d6e2e7f4bf53225fce58ea25c7418ba67ca59b2db030352ee1` |
| `docs/evidence/apps-alert/board/banner-timer-card-closed.png` | 5762 | DATA | `aa4d659e60e2c11e8da922f1b4ba1f1b74156b4d5b70fdc2781e105958da8a9a` |
| `docs/evidence/apps-alert/board/timer-reopened-resumes.png` | 7985 | DATA | `2ae369648201e9488c80979ce602087aa6c3de5717a0d0669cd8402beab4fd2b` |
| `docs/evidence/a-focused-text-field/board/timer-focus-keyboard-down.png` | 7987 | DATA | `9f3c0ab48bd43a4750b9961fc4978f09108e55486834401b0b6eda50bdbb8186` |

## Board evidence: Do Not Disturb, Home count, video at Home

Native grim captures from the board for Do Not Disturb, the Home notification count and the idle video run.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/do-not-disturb/board/quiet-ordinary-no-banner-top.png` | 11125 | DATA | `e0628f324b14cc57e9417a21b67f3680c679af4e52176d8f4f60fda588aec89d` |
| `docs/evidence/do-not-disturb/board/quiet-timer-breaks-through.png` | 5801 | DATA | `945cb4443ee71bdec39ad1e2fef64607872b73d6a018be0478a728e22cefa191` |
| `docs/evidence/do-not-disturb/board/shade-quiet-off.png` | 43220 | DATA | `b058ebff6eeaa61525733ce8256e7470f85e5ebd024c113e355c396d43dfb529` |
| `docs/evidence/do-not-disturb/board/shade-quiet-on.png` | 43557 | DATA | `c00d29cabbc74b916ed778d2a34e0a41abea9824d41184ec7603f80d5582fb5f` |
| `docs/evidence/home-notification-count/board/home-count-1-with-banner.png` | 209936 | DATA | `921c91ba84c9a2d8bc3d2fcdfb8500a3fcea606edfc8fe8fcd0bb2e6ad4c7391` |
| `docs/evidence/home-notification-count/board/home-count-3-quiet.png` | 205857 | DATA | `f0efd92d6bba85833b24a870b39797d45796c17095a4494883cc90ea087e62ec` |
| `docs/evidence/idle-dim/board/video-focused-playing.png` | 233581 | DATA | `8b16c49b640f76d6be5603489d8b691ebb304fe2e8457e9cba9093368c8a81c4` |

## Board captures: notification count, quiet row, GTK entry

Native grim captures from the board (injected touch, build zs05li2k): Home count 3/2/cleared, Settings Do Not Disturb row against the shade tile, Files search entry focused with no keyboard.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-notification-count/board/home-count-3-2-cleared.png` | 291699 | DATA | `e0abacfe4af194dad1d36ba3ebd1bc0db81889d1ef0b2119ff0cca3e65077faf` |
| `docs/evidence/do-not-disturb/board/settings-row-and-tile-agree.png` | 192515 | DATA | `704fc685540b6d5b80d2ed86e2f58a1015e79fe63e6301dd01faa9a595256943` |
| `docs/evidence/a-focused-text-field/board/gtk-search-no-keyboard.png` | 27659 | DATA | `f84e898df83a60269a81e48c65b2a427551d67a0bee6cb1cb83e58046c8321b6` |

## Board captures: GTK entry raises the keyboard

Native grim captures from the board (injected touch, build gpgh1vx6): Files search entry raising and lowering the focus keyboard after the Sway late-enter patch.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/a-focused-text-field/board/gtk-search-keyboard-up.png` | 179675 | DATA | `7f87db522bd6faf4abd885b5d6d2ccc144c5b3b4b77a64ec018b834e6a8f1202` |
| `docs/evidence/a-focused-text-field/board/gtk-search-closed-keyboard-down.png` | 19044 | DATA | `4e147d7adf71287b85acd4520cf7f86128c921d6f5a15016842a4d93007ab7ce` |

## Board capture: foot typing without keyboard flapping

Native grim captures from the board (injected touch and keys, build gpgh1vx6): terminal focused with the keyboard up, typed line, overview after switching away.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/a-focused-text-field/board/foot-typing-no-flap.png` | 97408 | DATA | `3a0f023dccc5734c7a1505817d7074cec3565d3a91a0b21392ac49175c512428` |

## Board capture: notification count while paging and with the shade

Native grim captures from the board (injected touch, build gpgh1vx6): Home count over both pages and around the pull-down shade; Weather widget covered.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-notification-count/board/home-count-paging-and-shade.png` | 486684 | DATA | `a43ab84ac42f8ff53470b7457ffc0a7062079e16e84a894c0eb633a59de5159b` |

## Board captures: exhibition clock

Native grim captures from the board (build fas6gqhw): the clock at 70 s docked idle, and twelve frames of the first ttfx effect (top-left banner, cursor shown).

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/clock-display/board/docked-idle-70s-clock.png` | 5904 | DATA | `2254e49d60b6e76e2165f749c8920d49655348662e07207ae5797fe576beaa8d` |
| `docs/evidence/clock-display/board/first-effect-top-left-cursor.png` | 54759 | DATA | `a5fb249aa9a39cc6db81dcf032c531990b1e1144a25f361f1c2324aea33201e9` |

## Board captures: centred exhibition effect and dismissal

Native grim captures from the board (build 3vk5qy3a): the centred K230 expand effect, one held banner frame, and a tap closing the card over Files.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/clock-display/board/centred-k230-expand-effect.png` | 28688 | DATA | `1c4caacf7439f364abe723f25da69267291e6c9e51b27a310e2b67bbefa6ef10` |
| `docs/evidence/clock-display/board/centred-k230-banner-174021.jpg` | 27856 | DATA | `23927a2d1e9cccf4773df366e47f8e943408adf9f39676b388ade0cd265d2f3e` |
| `docs/evidence/clock-display/board/tap-closes-card-over-files.png` | 17037 | DATA | `8804722be7641e327facab6b5f9e1694cbfa2f2aee5eef5ee0b8aedbeab15636` |

## Board capture: Quiet survives a reboot

Native grim crops of the shade on the board (build 3vk5qy3a) before and after a reboot with Quiet on.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/do-not-disturb/board/quiet-before-and-after-reboot.png` | 25134 | DATA | `67e63eb27db01ffcc19d94d7b110e3ce6e9eea2f9ce289bfcfa8852025e24285` |

## Open-with board captures

Native grim captures of xdg-open and Files opening a PNG, PDF and folder, and the Open With chooser (files-open-in-the-right-app 2.2-2.3)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/open-with/board/files-dtap-folder.png` | 47535 | DATA | `a4fb19ab2774388d6c22c726774c9ac4738086a6a6a9de00463fa22e78667fc6` |
| `docs/evidence/open-with/board/files-dtap-pdf.png` | 13186 | DATA | `3558f509fb40553a76c15ddee08e645cc763f9cfe491052fb6096e2338f2c5ea` |
| `docs/evidence/open-with/board/files-dtap-png.png` | 7946 | DATA | `ab5a1211e9695364e4aa6e09535bba8ebecbfc8d19ee6a20782c794a97f07117` |
| `docs/evidence/open-with/board/files-home.png` | 51461 | DATA | `bc645c03983cdbff49931ed519aa674760c42f181b7119988e87b316e829ab60` |
| `docs/evidence/open-with/board/files-longpress-png.png` | 61467 | DATA | `4e737d34cb70a7fe9e2df2fbb4ef68d63bec85a37c4d207e37aa765e0b1cfe6c` |
| `docs/evidence/open-with/board/files-open-with-list.png` | 39723 | DATA | `a1156285e2904a96917d241cac8ffbcf717976ff0a69d11fc3314294c6634780` |
| `docs/evidence/open-with/board/files-open-with-list-scrolled.png` | 38292 | DATA | `8f4b6df4be7e88126d385c469f852afe0b3b48b3b355153e3890f55973bad7ee` |
| `docs/evidence/open-with/board/open-pdf.png` | 13186 | DATA | `3558f509fb40553a76c15ddee08e645cc763f9cfe491052fb6096e2338f2c5ea` |
| `docs/evidence/open-with/board/open-png.png` | 7946 | DATA | `ab5a1211e9695364e4aa6e09535bba8ebecbfc8d19ee6a20782c794a97f07117` |

## Drawer-search board captures

Native grim captures of drawer search over the terminal (wifi, about, ti) and with the on-screen keyboard raised (the-drawer-search-finds-settings-and-app-actions 3.1-3.2); Wi-Fi page cropped to its title

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/drawer-search/board/about-opened.png` | 36313 | DATA | `fb06fb94750cc5fc7132f648028e07c6e5a523cbb5037fb4a4980b05efa585e0` |
| `docs/evidence/drawer-search/board/about-typed.png` | 14370 | DATA | `d4ff501cf6f6093d1dc311b1238e2fa90bf834583aa8abb5673a3336e9417bcb` |
| `docs/evidence/drawer-search/board/osk-raised.png` | 37629 | DATA | `824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1` |
| `docs/evidence/drawer-search/board/osk-te.png` | 24399 | DATA | `20104e075089ee23fd7bd29d80d783bff6e72ae7c4701363bead07c57bf7ea35` |
| `docs/evidence/drawer-search/board/osk-t.png` | 24553 | DATA | `4ac701d78889484debb9e1c7031496e77a9111cda391d7eb2fa71dbeb5a9c655` |
| `docs/evidence/drawer-search/board/term-after.png` | 17636 | DATA | `bc4e05491816fd0381ab7479f3a1a826828a9a093df4d6638df4aa2906c79e0e` |
| `docs/evidence/drawer-search/board/term-before.png` | 3382 | DATA | `0974d81adcd6cb57f75f816ed3b1a28852f569989ec067c47c2193e8c5290805` |
| `docs/evidence/drawer-search/board/ti-opened.png` | 8165 | DATA | `a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6` |
| `docs/evidence/drawer-search/board/ti-typed.png` | 29328 | DATA | `a84b2af4f626e66bb0a061d41d72124bd430ea5a4620beab473f52991ba8c6c2` |
| `docs/evidence/drawer-search/board/wifi-opened-title.png` | 3411 | DATA | `2e9b9de52d48eb758f34d58207256e7fbcb3fac86b923686c7f0db1ab59b97e1` |
| `docs/evidence/drawer-search/board/wifi-typed.png` | 13983 | DATA | `5b10ffef6f627e2e221c5025429a88257ec535ddff44313a29f39f122032eace` |

## Drawer search keyboard fix captures

Native grim captures of the drawer search keyboard before and after the osk-focus settle fix (injected board, 2026-10-28)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/drawer-search/board/osk-bug-keys-after-enter.png` | 36466 | DATA | `aa14e8407f0bca6a0dba1281a59f4e2cd862d0a0449750b0afc4de84ba59a654` |
| `docs/evidence/drawer-search/board/osk-fix-after-open.png` | 31995 | DATA | `5128d5fce7c844fa623e089c6254e00200dc028d509b32d1235316dc6584bd8b` |
| `docs/evidence/drawer-search/board/osk-fix-keys-after-enter.png` | 30165 | DATA | `899bceb716007abd22c18adfebc4786d1db42e7f8c1599e2a64d5c6c4cd7b9f3` |
| `docs/evidence/drawer-search/board/osk-fix-later.png` | 31995 | DATA | `5128d5fce7c844fa623e089c6254e00200dc028d509b32d1235316dc6584bd8b` |
| `docs/evidence/drawer-search/board/osk-fix-tapped.png` | 37629 | DATA | `824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1` |
| `docs/evidence/drawer-search/board/osk-fix-typed.png` | 25198 | DATA | `6f82c3e12c1a791527d1cf82e46a0c020af7eb5c21d4f94418a50dfb4b7cd18e` |
| `docs/evidence/drawer-search/board/osk-raised.png` | 37629 | DATA | `824e51a13bcf8269dc64ba528b9a2eed1df51f22d6c04ce3c43aa330b321bed1` |
| `docs/evidence/drawer-search/board/osk-te.png` | 24399 | DATA | `20104e075089ee23fd7bd29d80d783bff6e72ae7c4701363bead07c57bf7ea35` |
| `docs/evidence/drawer-search/board/osk-t.png` | 24553 | DATA | `4ac701d78889484debb9e1c7031496e77a9111cda391d7eb2fa71dbeb5a9c655` |
| `docs/evidence/drawer-search/board/osk-under-drawer.png` | 30791 | DATA | `5f46cefc1acdb313f64688c448d1c1cc3bd4c67d322c14dbe090a39d7361f873` |

## Files and Viewnior defect captures

Native grim captures: Files card staying short, and Viewnior rotate icons drawn (injected board, 2026-10-28)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/open-with/board/files-stays-short.png` | 24505 | DATA | `324f2c4c41a65ecbac2cf194fd740b1ebee8390e8c5bd266beef8fe1850c77bf` |
| `docs/evidence/open-with/board/viewnior-rotate-icons.png` | 8969 | DATA | `85f7fa0d98d8d5e6eb3dda2c79a100c3bf5f8a9cb76eaa032c34a0338df038de` |

## Resting display follow-up captures

Native grim captures of Settings idle rows, the shade Clock tile and the clock screen notification dot (board, 2026-10-28)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/resting-display-follow-ups/board/clock-dot-0.png` | 6362 | DATA | `5c580a11e0473ed864c890d72b86eac27d68dd3d08ecaa5b061f1578b016b30e` |
| `docs/evidence/resting-display-follow-ups/board/clock-dot-3.png` | 6968 | DATA | `8f4137e04f1b7571f4d8d0670466d048bc58901ebf2657c47b5b91bf1b41dde1` |
| `docs/evidence/resting-display-follow-ups/board/settings-idle-rows.png` | 35050 | DATA | `cdad9e553f3d513f28b33aa9d1b60744fcaca7000a43e2ebb9121695271a9d37` |
| `docs/evidence/resting-display-follow-ups/board/shade-clock-tile.png` | 43601 | DATA | `96c4071fd2bac7bffefda7761c1836a98e3362620ab06886925391a59b7aeef0` |

## Clock tile on battery captures

Native grim captures of the shade Clock tile on battery and its message (injected board, 2026-10-28)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/resting-display-follow-ups/board/clock-tile-battery.png` | 40872 | DATA | `670e0bc5d06dd3442f2adb071c9c6248832b6b8da0c485b73cf71dcda40bfa72` |
| `docs/evidence/resting-display-follow-ups/board/clock-tile-battery-tapped.png` | 43737 | DATA | `0f150ae1e483e3c5f16fb0eeebac502a7d9dae3b83c826f252c8942cbb049495` |

## Files full-card capture (open-with 2.5)

Native grim of Files opened from the drawer on build 37nvncgk, 2026-10-28.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/open-with/board/files-full-card.png` | 15192 | DATA | `630806f60e55b9133c3e52db7bd4a1a3f762d89f229eaac3f90875de30c6971c` |

## Base-attached keyboard captures (focused text field 3.5)

Native grim captures on build vf91pbq6, 2026-10-28: drawer search, foot and a GTK4 entry focused with the base attached, plus the gesture raising the keyboard.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/a-focused-text-field/board/base-attached/drawer-tap.png` | 70373 | DATA | `ee7513ae8fcfc031781673cfef7cab622fc831f615df553c9507c0bea46f6b12` |
| `docs/evidence/a-focused-text-field/board/base-attached/drawer-typed.png` | 10400 | DATA | `b1eb68ec503f1e5a9abe40b356781fb49fc2b269104241eb793191e9a5fa46ac` |
| `docs/evidence/a-focused-text-field/board/base-attached/gesture.png` | 17636 | DATA | `bc4e05491816fd0381ab7479f3a1a826828a9a093df4d6638df4aa2906c79e0e` |
| `docs/evidence/a-focused-text-field/board/base-attached/gtk-typed.png` | 15555 | DATA | `266249167404404b297e63352a2cd8a92e7c07bd32ba8f07059343566b80bbae` |
| `docs/evidence/a-focused-text-field/board/base-attached/terminal.png` | 6307 | DATA | `8aac4e8af34c0feb4f1ffd08c83c94c1fdbaad11cb7922c816dd02d71d750bb7` |

## OSK typing capture (focused text field 3.6)

Native grim on build vf91pbq6, 2026-10-28: ls typed on the on-screen keyboard ran in foot with the base attached.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/a-focused-text-field/board/base-attached/osk-typed-ls.png` | 26172 | DATA | `b21e4a13398385ec0bca98caf796173bc6b6afc2c658c4c69d8f0f29f271686e` |

## Board captures for Help, Settings About, Do Not Disturb at 200%, and the base echo (2026-10-28)

Native grim on build vf91pbq6: Help and Settings in portrait by live output rotation, the shade at the 200% text step with Quiet off/on/off, Settings landscape, and the terminal showing echo base ok.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/help-refresh/board/help-portrait-1.png` | 87164 | DATA | `b7de5b5f60f5e8557d76abe378082f879362438fd771b6dc81634e308b852879` |
| `docs/evidence/help-refresh/board/help-portrait-2.png` | 98601 | DATA | `4d99cafc7a9befb0b0687e448570cd7decfea1bc5017d5068f73190f45a7fc30` |
| `docs/evidence/help-refresh/board/help-portrait-3.png` | 82068 | DATA | `d33b368c2fc269e3f735efbcfb6c2f08d69874f01a9920b0a45f86496c789e42` |
| `docs/evidence/settings-about/board/settings-portrait.png` | 62134 | DATA | `3bfd17d7c9701e4dd7347aa149f40b05f3d018ea6c6a99705e7cb5d38e39ccb9` |
| `docs/evidence/settings-about/board/settings-landscape.png` | 70258 | DATA | `72c682ae4ad0d7725cf7ee2419625ddfbccc952ce8e4cadbe939356a0fc8bc7a` |
| `docs/evidence/settings-about/board/about-portrait.png` | 36337 | DATA | `8988895e711fcd3b23f132d11dfe52f0f20f546b0ea78fb73bd9d9378260bd66` |
| `docs/evidence/settings-about/board/date-time-portrait.png` | 37849 | DATA | `53c95d02b22e27f7611a2aa0e381bbb17ee678735f236649b25e850cbc66a80d` |
| `docs/evidence/do-not-disturb/board/shade-200-quiet-off-again.png` | 42575 | DATA | `e4593e4358dbc9bddfe37b3adced8877f94131eb52ac034e4c9f8fe4d8775387` |
| `docs/evidence/do-not-disturb/board/shade-200-quiet-off.png` | 42562 | DATA | `c96425b5fb7e4eedc9c6fed9973c5e3494b437e209d1b2516e4e7fca8f56daf5` |
| `docs/evidence/do-not-disturb/board/shade-200-quiet-on.png` | 42481 | DATA | `3a8597980c2d7babda0d46b8d6d98708c95f5e3a70cb0a7bb5746d67cbd87f20` |
| `docs/evidence/a-focused-text-field/board/base-attached/base-echo-terminal.png` | 20542 | DATA | `47f43cfafed7267fcf37c32ce1eb4f4406498025c1da7079a8f31391085f01a3` |

## Home count corner padding captures (2026-10-29)

Native grim of Home's notification count pill at the old 8 px and new 24 px corner margin.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/home-notification-count/board/count-8px-before.png` | 214066 | DATA | `3cde93ea0f347c4044ad22f79947032ee112f6b65d568078384321d766d7635f` |
| `docs/evidence/home-notification-count/board/count-24px-after.png` | 208875 | DATA | `2c960160ea76dc15f684488de7696f8d46f5a1308922592c84bb926c23cc1f66` |

## GTK text follows the text size (board)

Native grim captures of Files and Net at 100% and 200%, and Files with the pre-change GTK4 settings, for gtk-app-text-follows-the-text-size task 3.1.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/gtk-text-size/board/files-100.png` | 24649 | DATA | `ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286` |
| `docs/evidence/gtk-text-size/board/files-200.png` | 24186 | DATA | `a49355f58ae58ce7aadd60e689bd30861b12211fde63cf4b1e2ecdde8a21a5cd` |
| `docs/evidence/gtk-text-size/board/files-old-config-loading.png` | 15195 | DATA | `d74b7ff84919caf261dec14864a7ab743e6fdeacdc17e1bd379318a3a9cfe9d4` |
| `docs/evidence/gtk-text-size/board/net-100-menu.png` | 13880 | DATA | `3f9d0d96a05413066dfe64384698342a86331a7519860c2859244fa1c07e25f1` |
| `docs/evidence/gtk-text-size/board/net-100.png` | 11184 | DATA | `fa37d89428cb4942be14d61ab3cbc2e131f42d74cb1d7f939f1fe9ef1c1e2d7b` |
| `docs/evidence/gtk-text-size/board/net-200-menu.png` | 21703 | DATA | `288157ea33cc4796876d3776cb0e4a761635bea426f5dd2aba733c0572ade5c1` |
| `docs/evidence/gtk-text-size/board/net-200.png` | 15482 | DATA | `48b323e7268aa04ed653de7cae0759d95970f4194995dfbaeaf0fab18f0fa654` |

## Shade after an ordinary boot

Native grim captures from build 2867v7pm after an ordinary boot, before and after an injected swipe that opens the shade.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/shade-pass/board/ordinary-boot/boot-2867.png` | 6307 | DATA | `8aac4e8af34c0feb4f1ffd08c83c94c1fdbaad11cb7922c816dd02d71d750bb7` |
| `docs/evidence/shade-pass/board/ordinary-boot/boot-2867-shade.png` | 41162 | DATA | `275fe8f652588360252ded26f73a54eb834547b32ac80d940478b22f07c384fd` |

## Files slow load

Grim captures from build 2867v7pm: Files stuck on Loading… with stock GTK, and loaded with the patched GTK (files-finishes-loading-while-it-shows-a-spinner).

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/files-app/slow-load/stock-loading.png` | 15869 | DATA | `b7a2c501962463cdc82acc1580671567efa00f49906ef9b0a23c7aa70aade589` |
| `docs/evidence/files-app/slow-load/system-build-drawer-loaded.png` | 24649 | DATA | `ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286` |
| `docs/evidence/files-app/slow-load/ordinary-boot-loaded.png` | 24649 | DATA | `ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286` |
| `docs/evidence/files-app/slow-load/patched-loaded.png` | 24649 | DATA | `ee884d51c39d84cf27b2ab62654511aae9f0208538b32ce23eab5bebfc8e4286` |

## Clock format host renders

Host renders of the 12-hour clock (settings-chooses-a-12-or-24-hour-clock task 2.1); see docs/evidence/clock-format/host/README.md.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/clock-format/host/date-time-100-1232x568.png` | 45268 | DATA | `70f938e352231e8c5f2060b6a6f2e8a18037c8da13b8f54e76a0f4707e2cf85c` |
| `docs/evidence/clock-format/host/date-time-100-568x1232.png` | 51295 | DATA | `0d2d5567e01969fd5a6f5249a2361aad0bac46ef5c655f74aac3ffb66cf4dd17` |
| `docs/evidence/clock-format/host/date-time-200-1232x568.png` | 62002 | DATA | `cef29c9a0f6ba2e69df80c975e1bf3f6dcc126b71ad73aef91128f38c6e0e4af` |
| `docs/evidence/clock-format/host/date-time-200-568x1232.png` | 75075 | DATA | `2e38ee1899a4aa2ad29027ad33fd5f2e3fc2f90b4d5221d35861f7f9d318cafd` |
| `docs/evidence/clock-format/host/home-bubble-100-1232x568.png` | 30480 | DATA | `d8b150502bd1efba570372524ef344963882935c5a95f779a12eb1f65c2556d0` |
| `docs/evidence/clock-format/host/home-bubble-100-568x1232.png` | 34500 | DATA | `5aeb0d493d3781fafccc7f391b47ed508fa6a985d4d8e0ce625bcac0b59b89a4` |
| `docs/evidence/clock-format/host/home-bubble-200-1232x568.png` | 34542 | DATA | `98141ece1b8acfcc98d4d4c55bbbf2b4d3ed22ed52f3fafb81fcd915c68548f8` |
| `docs/evidence/clock-format/host/home-bubble-200-568x1232.png` | 38625 | DATA | `db95218fcfe2c415e6f273bb1aeb7fc4eed5ef7b02de03d3bf81f6cbfd9602b9` |
| `docs/evidence/clock-format/host/home-dot-matrix-100-1232x568.png` | 64601 | DATA | `b962cf4fef86edf4c26b900981363cd430c40f28673205fa11e82a15055e0678` |
| `docs/evidence/clock-format/host/home-dot-matrix-100-568x1232.png` | 71402 | DATA | `d73a2f09abbde3e8fe7cae79a3fba230b068d5221860ac1573a1ea818bb5dfe5` |
| `docs/evidence/clock-format/host/home-dot-matrix-200-1232x568.png` | 71196 | DATA | `8a52c2c69ec2bec2462c3c7253202ff25de0e913aedf58ef63df5539b76ce1e7` |
| `docs/evidence/clock-format/host/home-dot-matrix-200-568x1232.png` | 78678 | DATA | `1336a38b34d97b85d581b31acafd495b89f224c62cadb028fedeefcd4614ede3` |
| `docs/evidence/clock-format/host/home-thin-100-1232x568.png` | 30271 | DATA | `cdc08d6da89e4b80f791f8eeea255fcaa1e66c6de8b9775855432390f539fe1f` |
| `docs/evidence/clock-format/host/home-thin-100-568x1232.png` | 34053 | DATA | `9b8e7c04b7c729d5acfd77302d0ef0e2ddad5e0c7210fcf78527b3a41cdcb368` |
| `docs/evidence/clock-format/host/home-thin-200-1232x568.png` | 34520 | DATA | `ed7d541dbcc536ea23b2a7c4db8061e9f187881b9110c2d9bf495c8d952d98e4` |
| `docs/evidence/clock-format/host/home-thin-200-568x1232.png` | 38550 | DATA | `4a82174b3a3572b483f216ed775c32e7c5b3c30ba18cb8df4a4a46d029df1dfe` |
| `docs/evidence/clock-format/host/shade-100-1232x568.png` | 44331 | DATA | `da118b47ca6d35e125175c95376d5f2530c81d0b096e365ae5b71a95cc61530f` |
| `docs/evidence/clock-format/host/shade-100-568x1232.png` | 42333 | DATA | `68ba0fa8e9393e034d20ce795302d35e4df5996511285dba278dd1e5360442ef` |
| `docs/evidence/clock-format/host/shade-200-1232x568.png` | 48530 | DATA | `bdf0196eebf3870eb031c189a7da663f0ebdf157979d0b33879abe8aea823906` |
| `docs/evidence/clock-format/host/shade-200-568x1232.png` | 57309 | DATA | `c467bb52efc01cc48b818580016dd4f73699a5b47dc43629b151c52276e4262b` |

## Clock format board captures

Board captures of the 12-hour clock (settings-chooses-a-12-or-24-hour-clock task 3.1); see docs/evidence/clock-format/board/README.md.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/clock-format/board/clock-app-12h.png` | 7460 | DATA | `c7a9990a9ad519a472f109967724dda79ffd588111f9e9f724fbb9c8125f5bee` |
| `docs/evidence/clock-format/board/date-time-12h.png` | 35335 | DATA | `a786cf3934dd41af56fd5e54ff171724eddbc003a85e8bf8bc6e4d3cf3733a9a` |
| `docs/evidence/clock-format/board/date-time-24h.png` | 35378 | DATA | `ee2d76db051a67ac80ebfb23ee7d48c617b5b91a0a72f03cd2659c7662d078a0` |
| `docs/evidence/clock-format/board/home-12h.png` | 207575 | DATA | `2e9c19d1f3850cbb253550d9cf0eb5bfb8d4e027bc7abddab37606db6161bbec` |
| `docs/evidence/clock-format/board/idle-clock-12h.png` | 6612 | DATA | `3419f1f76acc0ebfc65d1db7d2f95bae864a8cac769b048dea2f9f9a3436d50c` |
| `docs/evidence/clock-format/board/shade-12h.png` | 41564 | DATA | `da9815f72c176b21fefd610fd39e2a8306327f644a67b29a04c487b71643679d` |
| `docs/evidence/clock-format/board/shade-24h.png` | 40920 | DATA | `2486277ce5d309fc856b62a8b85999f3931fca8d9c1f5db945fda2dc82f98002` |
| `docs/evidence/clock-format/board/shade-after-restart.png` | 41514 | DATA | `9acd2bed1022d59ed6bbb18a3c963aaf7594da941c66dd0ad7058eaa804550ee` |
| `docs/evidence/clock-format/board/shade-after-reboot.png` | 42618 | DATA | `426ddb2f197b9b76c2cf0428720f11121af32d139ec9977a7fbe061156e429c0` |
| `docs/evidence/clock-format/board/weather-12h.png` | 16917 | DATA | `f23366a3fe42967983075726827e500dd3d267d27c79a078f0c890f49ebbd481` |

## Time zone host renders

Host renders of Settings' time zone chooser and network time switch (settings-sets-the-time-zone-and-network-time task 2.2); see docs/evidence/time-zone/host/README.md.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/time-zone/host/areas-100-1232x568.png` | 44009 | DATA | `bad249ac1a72a51da8e54c44406387e1f5c7cce27bc76bcda60ac66d2c36afad` |
| `docs/evidence/time-zone/host/areas-100-568x1232.png` | 59438 | DATA | `1fcc5cbebba96be09ec2eb3fe49f156663feef5dd5bd7336ffa5afca5855a4ce` |
| `docs/evidence/time-zone/host/areas-200-1232x568.png` | 49121 | DATA | `545f18ebed5132d151103ec1bc7aaa91882fc734c443fc0a5fd605e7faa67c3f` |
| `docs/evidence/time-zone/host/areas-200-568x1232.png` | 74917 | DATA | `800dd0a0b89897515d4109eaff95928839770422eb5e09f64806ab7d1892b3df` |
| `docs/evidence/time-zone/host/date-time-100-1232x568.png` | 44826 | DATA | `c6153e1a49708e678d96ad31d5160b5b94666970528ae70ed3e4d6bb3a103a14` |
| `docs/evidence/time-zone/host/date-time-100-568x1232.png` | 51222 | DATA | `aa541c6a578948c18e2cafaa11b35f1a628ff963954e854d0f810792956b0567` |
| `docs/evidence/time-zone/host/date-time-200-1232x568.png` | 59583 | DATA | `52b65e948701b087ca743f6badbaab333f91bf787fac636c09fc936dc45431a5` |
| `docs/evidence/time-zone/host/date-time-200-568x1232.png` | 74101 | DATA | `42e5ec730dd8fadf5ad738baeb3d73e252142f2dbeefda24b684d70ff79cb6c8` |
| `docs/evidence/time-zone/host/date-time-network-off-100-1232x568.png` | 43490 | DATA | `03ec6fffb9198ec34006ef51b3b5c60d17de3bda42c78f8d81a3313ae6f3f4cb` |
| `docs/evidence/time-zone/host/date-time-network-off-100-568x1232.png` | 48261 | DATA | `adcdb6546044fba42f9fe94cc07bd7ce0dfaa824aa94b08a1700ce7fb093cde5` |
| `docs/evidence/time-zone/host/date-time-network-off-200-1232x568.png` | 56629 | DATA | `cdedcaecaa8f4dc7ebd99486d3d196110bf2bab018e551d251deeaf2375cb23e` |
| `docs/evidence/time-zone/host/date-time-network-off-200-568x1232.png` | 68837 | DATA | `d10e00173dabca7bf572b406a442a5211ebbe26111d256ab48c6405c0411345e` |
| `docs/evidence/time-zone/host/europe-page-1-100-1232x568.png` | 59213 | DATA | `bff033edca3ac55f5d7008aeb199db2b8ce8747b3c39103989efcf8d7d5a9b07` |
| `docs/evidence/time-zone/host/europe-page-1-100-568x1232.png` | 70643 | DATA | `6f19b3d3131eee0993315faec085c9f9173f2782d5d5ab0ccc20f77948ed14f7` |
| `docs/evidence/time-zone/host/europe-page-1-200-1232x568.png` | 72173 | DATA | `6a91d06a83f5a0b218fce4d827632ce42366dd34058786c76e96b754d791c0dc` |
| `docs/evidence/time-zone/host/europe-page-1-200-568x1232.png` | 86864 | DATA | `96f0f8596c229365c0b36c3a946cc14b2603763089e8d55d6bb5d63cb1d37dd4` |
| `docs/evidence/time-zone/host/europe-page-2-100-1232x568.png` | 55995 | DATA | `10e900c1a0e24918f70388aefc64135972ed062a0028ef6bfcf36ba2ebf582fb` |
| `docs/evidence/time-zone/host/europe-page-2-100-568x1232.png` | 63971 | DATA | `ad608683fb9e6c2f1bba69f87a1f162285f05961120611828b300b477f0240a6` |
| `docs/evidence/time-zone/host/europe-page-2-200-1232x568.png` | 70077 | DATA | `3dadd48d7000b418d72ec1c1692793ffe5ed849c2ac57df307666a2625a6826c` |
| `docs/evidence/time-zone/host/europe-page-2-200-568x1232.png` | 87542 | DATA | `30cc3802ef27fbdf0e7c41d9fed8dd979df778cbc4d8d928bd7b31d6b0971b73` |

## Time zone board captures

Board captures of the time zone chooser and network time switch (settings-sets-the-time-zone-and-network-time task 3.1); see docs/evidence/time-zone/board/README.md.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/time-zone/board/tz-01-date-time.png` | 36438 | DATA | `cb2bed6826b8ac07bebbecb5130bfd329a43f0eb16d8612d91fb6c80316ffba5` |
| `docs/evidence/time-zone/board/tz-02-areas.png` | 34382 | DATA | `f7d7613d27999a164a9dd8eeae279191979ad8b1759f9f1e0b5ac53e32a627a1` |
| `docs/evidence/time-zone/board/tz-03-europe-1.png` | 46384 | DATA | `8e681d41720f7ee58320fc67610cf43b1bd89a88f021dc39d22b2bffb61bc0b7` |
| `docs/evidence/time-zone/board/tz-04-europe-2.png` | 42960 | DATA | `15e44bdff760367f35894641c25c51d4ea1c200f839daa0977d6afbfba4ffe77` |
| `docs/evidence/time-zone/board/tz-05-date-time-london.png` | 34466 | DATA | `17f1935ff386fc83518a9dcb32f64a1056845bd3d29c77e3b17b49f43c2cb31a` |
| `docs/evidence/time-zone/board/tz-06-shade-london.png` | 40756 | DATA | `1af4237a65f066aab18a2bb41087c8c32ece215b30f1ea270126302a0d7dc474` |
| `docs/evidence/time-zone/board/tz-08-clock-app-london.png` | 6990 | DATA | `134dc09ba5911187924bdab79317d2f8415797e1b9fe1816a8d18fed8759db90` |
| `docs/evidence/time-zone/board/tz-10-network-off.png` | 33455 | DATA | `cc98d7f17bc149d9d1b83397db62e7860f8164dc2ba80b229fb75cc2d031741a` |
| `docs/evidence/time-zone/board/tz-11-shade-after-reboot.png` | 41027 | DATA | `53cd47895761b1f174c611dfa88d7a75a5d6a1a8ec92c0de522a47a8db4cab24` |
| `docs/evidence/time-zone/board/tz-12-date-time-after-reboot.png` | 33719 | DATA | `55fc62e9b2af0e35ef7d2df82e9ecd912a28eac5024ccb2a4b436800331a0aed` |
| `docs/evidence/time-zone/board/tz-13-america-3.png` | 51260 | DATA | `074d24ce73861ccd2e7c4c01ee97943fe0e4bddcb20b45d0399c7f0aab9cd3ce` |
| `docs/evidence/time-zone/board/tz-14-restored.png` | 36506 | DATA | `e2d1d3f73c3b22becc3089e86350235fc91d31dc9a70db48c55b289e911f25f8` |

## Notification actions host renders

Host renders of an app's notification actions in the shade (pending-timers-survive-restarts-and-apps-hear-dismissals task 2.3); see docs/evidence/notification-actions/host/README.md.

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/notification-actions/host/shade-actions-100-1232x568.png` | 64485 | DATA | `678367829bf66639c943f97576391d288f68e61dda66db7ec999c4e7c35fbbc0` |
| `docs/evidence/notification-actions/host/shade-actions-100-568x1232.png` | 55715 | DATA | `9f8cdafb7e50f19be53f31d00f197f2a555254914059c9386a65ed3d1d3450a1` |
| `docs/evidence/notification-actions/host/shade-actions-200-1232x568.png` | 69585 | DATA | `047c2616339b278350d069d5e899e6a9911ba08af72119d5db7a1bd302b58ded` |
| `docs/evidence/notification-actions/host/shade-actions-200-568x1232-scrolled.png` | 67812 | DATA | `9b59aaf70f5e2090ac2ee43d219eb2da44891d89f26f93bcc297034bcfbaba11` |
| `docs/evidence/notification-actions/host/shade-actions-200-568x1232.png` | 67621 | DATA | `b73e5e22cdf135f25ecc0bb9a5fdec208a043c22c0a43abd25a4c46c59c195ab` |

## Pending timer across a shell restart, board

Injected-touch grim captures of a 2:00 Timer kept by k230-timer@.service across a shell restart (task 3.1)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/timer-restart/board/tr-10-set-2min.png` | 8165 | DATA | `1c5681a1da7b97f9134b358d775789eeb682f4609f5fa92439165fe6615e8e66` |
| `docs/evidence/timer-restart/board/tr-11-running.png` | 8004 | DATA | `e8d06358d50e99e6da66362e826c3111dd0e9227a40dd91ef1e961f027fa25b3` |
| `docs/evidence/timer-restart/board/tr-12-shade-finished.png` | 47205 | DATA | `580d03b18dcde77746a0859bee41c1b466062bb3a0a8a8e0dfe5d59eda4f197b` |
| `docs/evidence/timer-restart/board/tr-20-reopened-adopts.png` | 7970 | DATA | `9c7023203bc718725d99f2edddd8ca71144e5f62a69eb09f322eef938f1597bb` |
| `docs/evidence/timer-restart/board/tr-21-reset.png` | 8165 | DATA | `a2c14dbe49dfc069aaa1697a9e4dbd39fac7f4ba4da29228b8651c8683d091d6` |

## Notification actions and close reasons, board

Injected-touch grim captures of probe notifications with actions in the landscape shade (task 3.2)

| Path | Bytes | Class | SHA256 |
| --- | ---: | --- | --- |
| `docs/evidence/notification-actions/board/na-01-shade.png` | 60332 | DATA | `01a84a243268886658f98dbee3a32f6bbb1bf6b015a4d9ce5a3c8301892ac850` |
| `docs/evidence/notification-actions/board/na-02-after-snooze.png` | 59060 | DATA | `c6d0d1c54541827f945726bdf375fcf4ddcaf94a26b91bafa08c9918c845714c` |
| `docs/evidence/notification-actions/board/na-03-after-swipe.png` | 59060 | DATA | `c6d0d1c54541827f945726bdf375fcf4ddcaf94a26b91bafa08c9918c845714c` |
| `docs/evidence/notification-actions/board/na-08-top.png` | 58377 | DATA | `a59a8f680c2e8f23837f7c51db888580f94439fafe4b7662d82d1c976edf0f83` |
| `docs/evidence/notification-actions/board/na-09-after-swipe.png` | 59703 | DATA | `0ada06ad166889c23312655338977a0c945debdb3d23075f25dbe56ddfb6ad2c` |
| `docs/evidence/notification-actions/board/na-10-after-restart.png` | 57720 | DATA | `ec33352904f609ea9a2011bc9c778ebae84bee96bb71a0cb35a693a73ecf38dc` |
| `docs/evidence/notification-actions/board/na-11-after-open.png` | 60114 | DATA | `5cb895b8ed8376e0dc403566d5c7acdb5614b8032856a283565cfe76de99313a` |
| `docs/evidence/notification-actions/board/na-12-cleared.png` | 41428 | DATA | `ba9ca84370dcf3083e2e8a6f00d866b79fe640baef49a83e17fe160d7e1ff2cd` |
| `docs/evidence/notification-actions/board/na-13-before-dismiss-all.png` | 57605 | DATA | `d83931bd84b2f22b006d9723d0bb3502da57addf5f67feeaaf56778ac6c9b7d2` |
| `docs/evidence/notification-actions/board/na-14-after-dismiss-all.png` | 40871 | DATA | `3af44cf361cc8fa9bc1aa1c648885cbf18c4fba13057b10e3def76862ed002db` |
