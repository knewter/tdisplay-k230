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
described in `firmware/stage1/PROVENANCE.txt`. The `MANIFEST` section at the
end is the machine-readable form.

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

## B. Blobs the Linux path would pull in

None of these is on our path *today*. Each is one defconfig line away, and
`k230_canmv_v3_defconfig` already sets most of those lines — so if we ever
build the SDK's rootfs rather than our own NixOS closure, they arrive
silently. That is exactly the accident this table exists to prevent.

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

### B3, B4 — radio firmware for radios this board does not have

The defconfig sets `BR2_PACKAGE_AIC8800=y` and `BR2_PACKAGE_RTL8733BS=y`
because `k230_canmv_v3_defconfig` targets Canaan's reference board.
`docs/findings.md` records that *this* board carries an RTL8189FTV on SDIO
(MMC1, enable on GPIO45). So 8.8 MB of AICSemi RF firmware and a Broadcom
BCM43438 image are dead weight we would ship by inheritance.

**The interesting part is what we need instead, and it is not a blob.**
`BR2_PACKAGE_RTL8189FS=y` resolves to buildroot's own package, which fetches
`jwrdegoede/rtl8189ES_linux` at `94cc959d` — **GPL-2.0 source, built as a
kernel module, no firmware file at all.** The RTL8189FTV keeps its MAC
firmware on-chip. So the radio on this board is, unusually, blob-free under
Linux; the obstacle is a driver build, not a licence.

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
# class  sha256                                                            path
E2  3872df5a4e60c53b163a49b31d7b41ee0a407d08d06d18fefe6f8102b3866a94  firmware/stage1/fn_u-boot-spl.bin
E2  0f8feb747ef4437afbe26b9081c19acbd99475086f2b82db64cc3d3195c54579  firmware/stage1/fn_ug_u-boot.bin
E1  f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957  firmware/stage1/env.env
E1  c6d029a05f2d3038fd02f9b18716b595f4e8beeebca33f3598328fbde99bf11e  (sdk)tools/k230_priv_gzip
IO  517aa534255e88c941882be40f5e5735349cd1e3b144b536155e51bdc6309c8b  embedded:fn_u-boot-spl.bin@0x1fc74+0x8000  ddr-pmu-imem
IO  1c0819e81446a8944a3ecf95304642ecec2071451d430e21925e5d7daea47313  embedded:fn_u-boot-spl.bin@0x1f5f4+0x67c   ddr-pmu-dmem
E1  023b5495c9450af553c24d8c518cf8f191c9ed8e5622e7a7405007172cb4fb10  firmware/stage1/fw_jump.bin
E1  d0279bc93038793906764d22dfea298d82a89999dd0b26b23d69cce98497e544  firmware/stage1/fw_jump_add_uboot_head.bin
IO  -  (silicon) K230 BootROM
E2  md5:8cefc7e94f760eaecc3620ffb238bf4a  Xuantie-900-gcc-linux-6.6.0-glibc-x86_64-V3.0.2-20250410.tar.gz
IO  28680932ac879d8591fbaaaab7b8c1ee2d305c2a82471fb2f38c449316cfb91f  dl:nncase_k230_v2.11.0_runtime_linux.tgz
IO  525e4611b587afb1ab406548ddc6a5e1add3e5fa74ff2829da9441d4a62f3075  dl:nncaseruntime_k230-2.11.0-py3-none-linux_riscv64.whl
NP  c11b83cfb92b9b01cdfb7150c75674c69563add2c8c1e71df1dc741694aae5a4  (sdk)buildroot-overlay/board/canaan/k230-soc/rootfs_overlay/etc/firmware/fw_bcm43438a1.bin
NP  6a35357449419dd493b201487f1a8467298dce0b990ad061bd00962a039c0b88  (sdk)buildroot-overlay/board/canaan/k230-soc/rootfs_overlay/boot/nuttx-7000000-uart2.bin
NP  91f53b9af6bacf9f91bb3995727cb4f9712810baaffbb2f230ff0ce87ab4464e  (sdk)buildroot-overlay/package/ai2d_kpu/test.kmodel
NP  56d35ded2a717fafcc1a357fd6e634531fa1693e59c77707140d8c6e1693eae9  (sdk)buildroot-overlay/package/face_detect/utils/face_detection_320.kmodel
NP  bb6c1142da99f017861d6d5ffaf956eb2b4a29cc393a6a7bc5bedad392499e15  (sdk)buildroot-overlay/package/yolo/utils/yolo11n.kmodel
NP  11c6f0aa707c63d351fb54fa24be3df23ae579590cd448921ffa3614a6a05190  (sdk)buildroot-overlay/package/yolo/utils/yolo26n.kmodel
NP  91b6c3e9bc2fc5d0bf5258e1217b6d8a81b4330521922165db255fe98795901c  (sdk)buildroot-overlay/package/yolo/utils/yolov5n.kmodel
NP  0b4bcdd3eef7ad05d827127ec630d2354659f6db1b0c627ecb4af32cb2004a09  (sdk)buildroot-overlay/package/yolo/utils/yolov8n.kmodel
NP  group:103-files  (sdk)buildroot-overlay/package/aic8800{,_sdio/src}/fw/**            8.8 MB
NP  group:7-files    (sdk)buildroot-overlay/package/k230_assistant/dist/lib/*.a
NP  group:1-file     (sdk)buildroot-overlay/package/opencv4/3rdparty/csi-cv/libcsi_cv_c908v.a
NP  group:3-files    (sdk)buildroot-overlay/package/ai2d_kpu/{input,ai2d_input,result}.bin
IO  e776d472979e32d761fd22a6c1f69e1bdee6aa32663169e684900e61eb08dd43  (lilygo)src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/extdrv/realtek/wlan_lib/libwlan_v1_1.a
IO  5f6baf7c785916beb7e18bda2535585cabaa62315dd8446f256d651900c06564  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libnncase.rt_modules.k230.a
IO  f6674a664be8133e368ab0f08df3e42d351e1f50811fdbddb6cf195cab6c0264  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libNncase.Runtime.Native.a
IO  1ac694e7197944e7217e21b50acfa2a8b14956355cf28e2f887d16d2a608fb01  (lilygo)src/rtsmart/libs/nncase/riscv64/nncase/lib/libfunctional_k230.a
IO  88c690d309fa5bc04b53ad909b450d97a9b9ebe887ee634891d8e4e44845118e  (lilygo)src/rtsmart/libs/nncase/riscv64/rvvlib/librvv.a
NP  6e5eac63398ecf18dd8327585232c2245d0087a699b6a964291b35660f8a94f7  (lilygo)src/rtsmart/rtsmart/tools/udb-tools/linux/udb
IO  group:14-files   (lilygo)src/rtsmart/mpp/kernel/lib/*.a                              6.6 MB
IO  group:39-files   (lilygo)src/rtsmart/mpp/userapps/lib/*.a                             18 MB
E1  group:25-files   (lilygo)src/rtsmart/libs/opencv/lib/*.a
NP  group:87-files   (lilygo)src/rtsmart/libs/kmodel/**
NP  group:19-files   (lilygo)src/canmv/resources/examples/*.{bin,kmodel}
IO  group:2-files    repo/firmware/CanMV-K230-V3P0_rtsmart_release{V1.2,V1.3}.zip
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
   forever tax. This board got lucky: its RTL8189FTV has a GPL driver and
   needs no firmware file, while the *reference* board it shares a defconfig
   with pulls 8.8 MB of AICSemi RF firmware.
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
