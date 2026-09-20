## Context

See proposal.md — Why. What constrains the approach:

- **The tree is still gaining blobs.** `firmware/stage1/fw_jump.bin` and
  `fw_jump_add_uboot_head.bin` were committed on 2026-09-20 while this change
  was being drafted, taking the committed count from three to five. Each
  addition is individually well reasoned; that is how the count grows.
- **The sources are already on disk.** `.build/k230_linux_sdk` is a checkout
  of `kendryte/k230_linux_sdk` at `1104236`, BSD-2-Clause. Canaan's U-Boot
  changes are not a patch series but a directory rsynced over vanilla
  u-boot-2022.10 (`UBOOT_OVERLAY_DIRS`, `buildroot-overlay/boot/uboot/uboot.mk:581`).
  Nothing has to be reverse-engineered.
- **Three of the four packaging steps are already proven reproducible** with
  nixpkgs tools, byte for byte, and recorded in `docs/blob-inventory.md` §D.
  Only compilation remains vendor-bound.
- **The ISA is plain.** `readelf -A` on the built SPL reports
  `rv64i2p1_m2p0_a2p1_c2p0_zicsr2p0_zifencei2p0_zmmul1p0`. The T-Head cache
  operations in `arch/riscv/cpu/k230/cache.c` are hand-encoded
  (`asm volatile(".long 0x0295000b")  /* dcache.cpa a0 */`) and the vendor
  CSRs are written by number. Nothing needs the Xuantie assembler.
- **One part will never be open.** 32 KiB of Synopsys DDR PHY training
  microcode, embedded in the SPL at `0x1fc74`. It arrives as C, so building
  from source compiles it rather than removing it.
- **`image/boot-chain` is owned by an in-flight change.** It is not yet in
  `openspec/specs/`; `the-board-boots-what-we-built` holds it. The delta here
  is written against that change's text and assumes it archives first. This is
  a sequencing constraint, not an unknown.
- **The board cannot be bricked by this.** Stage 1 lives on the SD card, not
  in internal flash, so the worst outcome is a card that does not boot and a
  known-good card that does.

## Goals / Non-Goals

**Goals:**

- Stage 1 produced by `nix build`, from sources pinned by hash, with no Docker
  and no vendor toolchain.
- No unreadable executable in the path from source to card.
- One document that accounts for every blob, and a check that keeps it
  accounting for them.

**Non-Goals:**

- Bit-identity with the vendor's binaries. Once a different compiler is used
  it is gone, and chasing it would mean packaging Xuantie GCC, which is the
  thing we are removing.
- Touching the SD layout, the boot command, or the environment's contents. The
  stage 1 we build does exactly what the committed one does; changing its
  behaviour is a separate change and mixing the two would make a boot failure
  ambiguous.
- Removing the DDR PMU training firmware, or any blob in sections B and C of
  the inventory.

## Decisions

**Build stage 1 as an ordinary derivation, not a fixed-output one.**
`the-board-boots-what-we-built`'s design chose a fixed-output derivation;
`firmware/stage1/PROVENANCE.txt` then chose committed binaries on the grounds
that a fixed-output derivation needs a URL and these were built locally. Both
are answers to the wrong question. A hash over an opaque artifact records that
it has not changed, not what is in it. An ordinary derivation over pinned
sources records both. Layer: **Nix**.

**Vendor the packaging *script*, not the packaging *binary*.**
`firmware_gen_no_securiy.py` — the thing that applies the `K230` header — is
about 100 lines of readable Python inside the U-Boot tree, and it is already a
source input. Use it as-is. Rejected: reimplementing the header format in Nix.
It is simple enough to reimplement and that is exactly the trap: a subtly
different SHA-256 field produces a BootROM that refuses the image with no
console output to say why, and the bug would look like a DDR failure.
Layer: **Nix**, over vendor source.

**Restore the `sed -i -e "1s/\x08/\x09/"`.** The vendor's pipeline flips the
gzip header's CM byte to `0x09` so the SPL decompresses U-Boot with the SoC's
ugzip DMA engine rather than in software. `tools/gen-stage1.sh` omits this and
the committed `fn_ug_u-boot.bin` carries `0x08`. Both paths are linked into
the SPL (`nm` shows `zunzip` and `k230_priv_unzip`) so the software path
should work, but it is not the path the vendor ships or tests, and "should
work" is how the next hour gets spent. Match the vendor. Rejected: adopting
the software path deliberately — defensible, and cheaper to reason about, but
it would be the first place to look after any SPL hang and it buys nothing.
Layer: **stage 1 packaging**.

**Replace `k230_priv_gzip` with `pkgs.gzip`, and keep the proof.** It is GNU
gzip 1.6 with the name changed; output is identical on the real `u-boot.bin`
at every level the SDK tries. Record the comparison as evidence rather than a
claim, because the whole argument for the substitution is empirical. Rejected:
keeping the vendor binary and pinning its hash. Pinning the hash of an
unreadable program only guarantees that we keep running the same unreadable
program. Layer: **Nix**.

**Compile with `pkgsCross.riscv64`, and be willing to pin an older GCC.**
U-Boot 2022.10 against nixpkgs GCC 15.3.0 is a three-year gap and old U-Boot
trees routinely need warning suppressions for new compilers. If the build
fights, pin `pkgsCross.riscv64.buildPackages.gcc13` rather than patching the
vendor tree — a compiler pin is a one-line, legible, reversible constraint and
a patch series against Canaan's overlay is not. Rejected: packaging the
Xuantie toolchain. 1.9 GB, MD5-only provenance, and the ISA evidence says it
is unnecessary. Layer: **Nix**.

**Build Canaan's OpenSBI 1.4 in the flake, not nixpkgs' 1.8.1 — and this is
the one place a newer upstream is the wrong answer.** OpenSBI was not a blob
when this change was drafted; `fw_jump.bin` and `fw_jump_add_uboot_head.bin`
were committed to `firmware/stage1/` on 2026-09-20, mid-draft, for the same
build-convenience reason as U-Boot, and `PROVENANCE.txt` says as much. They
are E1: the whole Canaan delta is nine readable C files over
`riscv-software-src/opensbi` 1.4.

The tempting shortcut is `pkgs.opensbi`. It is wrong here, and not for the
usual version-skew reason. Upstream v1.8 *does* match
`canaan,kendryte-k230` in `platform/generic/thead/thead-generic.c` — but with
`thead_pmu_quirks` only. Canaan's overlay matches the same compatible with
`THEAD_QUIRK_DISABLE_MAEE` and calls `thead_disable_maee()` to clear
`MXSTATUS.MAEE`, and upstream's `c9xx_errata.h` has no such bit. MAEE left on
is a page-attribute fault: the kind that boots fine and corrupts memory later.
So: fetch opensbi 1.4, apply the overlay, generic platform,
`FW_TEXT_START=0`, header it with `mkimage` exactly as `post-image.sh` does.
Rejected: `pkgs.opensbi` with a patch, and `pkgs.opensbi` unchanged — the
first is the same work with a worse diff, the second is a bet on a quirk we
can see is absent. Revisit if upstream gains a K230 MAEE quirk. The v0.9 in
`docs/rtsmart-boot-log.txt` is LilyGO's shipped RT-Smart firmware and is in
neither chain. Layer: **Nix**.

**Keep the committed binaries until a compiled stage 1 has booted, then
delete them in the same commit as the evidence.** A bringup failure with no
fallback on a board whose console appears only after DDR training is a bad
afternoon. Rejected: deleting them at the start to force the issue. Layer:
**repository**.

**Enforce "accounted for", not "absent".** The scanner requires every binary
to have an inventory entry; an entry saying "permanent, here is why" passes.
Rejected: banning binary files, which would fail the moment a photograph of
the screen is committed as evidence — and photographs are grounding in this
project. Rejected: a git pre-commit hook, which is bypassable and does not see
the vendor checkouts where most of these blobs live. The check belongs in
`./scripts/build_site.py`, which already refuses to publish a spec whose
evidence is missing. Layer: **tooling**.

**Publish the inventory by citing it, not by adding a renderer.**
`scripts/render_specs.py` already copies any `docs/` path cited from a
`*Grounding:*` line into the site. A requirement in `image/vendor-blobs`
citing `docs/blob-inventory.md` publishes it at `/evidence/…` and makes its
deletion a build failure. No new code. Layer: **docs**.

## Risks / Trade-offs

- **The SPL we compile hangs before the console exists.** → The single most
  likely failure, and it would look like silence. Mitigations: the committed
  binaries stay until a compiled one boots; the DDR init file and its Kconfig
  (`CONFIG_CANMV_V3_LPDDR4_2667`) are taken unchanged, so the training data is
  identical; and the recovery is writing a different card.
- **U-Boot 2022.10 does not build under GCC 15.** → Pin GCC 13. Cheap,
  visible, reversible.
- **The SPL grows past `CONFIG_SPL_SIZE_LIMIT=0x80000`.** → Low: the vendor's
  SPL is 206 064 bytes against a 524 288-byte limit. Check the size in the
  derivation so a regression fails the build rather than the board.
- **Bit-identity is lost, so the proof changes shape.** → Today every step can
  be checked against a recorded sha256. After this change the compilation step
  can only be proven by booting. Say so in the task, and capture the console.
- **`the-board-boots-what-we-built` archives after this, or never.** → The
  `image/boot-chain` delta then has nothing to modify. Merge by hand; the
  proposal says so rather than leaving it to be discovered at archive time.
- **The inventory rots.** → That is what the scanner is for. A document nobody
  is forced to update is a document that describes last year's tree.

## Migration Plan

The removal of `firmware/stage1/*.bin` and `env.env` is the only destructive
step and it is last, gated on a committed console transcript. Rollback at any
earlier point is `git checkout` of those three files plus the existing
`nix/stage1.nix`. The flake attribute `stage1.verified`, which today checks
the committed hashes, is replaced by the derivation itself: a build that does
not produce the expected artifact fails, which is a stronger check than a
hash comparison against bytes we chose.

## Open Questions

Whether the hardware `ugzip` path is meaningfully faster than the software
one at 345 KB. It does not change the specs, the approach, or the tasks — the
decision above is to match the vendor either way — but if the difference is
milliseconds, a future change could drop the `sed` and the one-byte
non-standard header with it.
