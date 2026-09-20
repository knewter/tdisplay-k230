# Tasks

Groups 1 through 4 make **no hardware claim** and can run while the board is in
pieces. Group 5 is the only one that needs the board, and it needs it because
DDR training happens before there is a console: nothing else can prove a stage 1
we compiled. QEMU proves nothing anywhere in this change — its `k230` machine
loads a kernel directly and models neither the SPL nor the SD card.

## 1. The inventory, and a check that keeps it honest

- [x] 1.1 Inventory every opaque binary this project ships, executes, or is one defconfig line from acquiring, with sha256, class, scope and the event that would remove it. Verify by committing `docs/blob-inventory.md` and confirming every sha256 in it reproduces: `sha256sum -c` over the MANIFEST's file-backed rows
- [ ] 1.2 Write `tools/blob-scan.py`: walk the committed tree, plus any vendor checkout passed as an argument, classify each file as text or binary, and exit non-zero on a binary with no MANIFEST entry or a mismatched hash. It must also check the stage-1 release hash pinned in `nix/stage1.nix`, because a blob fetched by URL is not a blob the filesystem walk will find. Verify with `./tools/blob-scan.py` exiting 0 on the current tree and `./tools/blob-scan.py --self-test` exiting non-zero against a planted unlisted binary and against a mutated release hash
- [ ] 1.3 Call it from `./scripts/build_site.py` alongside the existing evidence check. The citation that publishes the inventory is already in the `image/vendor-blobs` delta, so it takes effect when the capability reaches `openspec/specs/`; this task confirms it does. Verify with `./scripts/build_site.py` exiting 0 and `site/dist/evidence/docs-blob-inventory-md/index.html` existing
- [ ] 1.4 Capture the scan's passing and failing output to `docs/evidence/blob-scan.txt`, and resolve the `UNVERIFIED` marker on "A binary that is not in the inventory fails the build" against it. Verify with `openspec validate --all`

## 2. Stop executing the vendor binary

- [ ] 2.1 Record the gzip equivalence as committed evidence rather than a claim in a document: vendor `k230_priv_gzip -n8` against nixpkgs `gzip -n -8` over the SDK's `u-boot.bin` at levels 4 through 9, with both sha256 sets. Verify by committing `docs/evidence/gzip-equivalence.txt` and confirming it shows identical hashes at every level
- [ ] 2.2 Replace `k230_priv_gzip` in the stage-1 pipeline with `pkgs.gzip`, and add the `sed -i -e "1s/\x08/\x09/"` the vendor applies and `tools/gen-stage1.sh` omits. Verify with `nix build .#stage1-packaging` reproducing `fn_ug_u-boot.bin` from the existing `u-boot.bin` and the result differing from the committed file in exactly the CM byte and the two checksums that cover it

## 3. Stage 1 from source

- [ ] 3.1 Add a `uboot-k230` derivation: fetch u-boot-2022.10 (sha256 `50b4482a…`) and `kendryte/k230_linux_sdk` at `1104236`, rsync the overlay, apply `k230_canmv_v3_defconfig`, build with `pkgsCross.riscv64`. Pin `gcc13` if GCC 15 fights. Verify with `nix build .#uboot-k230` producing `u-boot.bin` and `spl/u-boot-spl.bin`
- [ ] 3.2 Assert the SPL fits: fail the derivation if `u-boot-spl.bin` exceeds `CONFIG_SPL_SIZE_LIMIT` (0x80000). Verify with `nix build .#uboot-k230` and the build log printing the measured size against the limit
- [ ] 3.3 Wire the proven packaging from task 2.2 onto the compiled output — gzip, `mkimage` with `SOURCE_DATE_EPOCH`, the CM byte, `firmware_gen_no_securiy.py` — to produce `fn_u-boot-spl.bin` and `fn_ug_u-boot.bin`. Verify with `nix build .#stage1` and `file`/`xxd` on the result showing the `K230` magic and a CM byte of `0x09`
- [ ] 3.4 Build the environment from `default.env` rather than carrying `env.env`. Verify with `nix build .#stage1` and `sha256sum` on the produced `env.env` matching `f522ba13aa8a2e643e61e4fde9f2babb604e86b2f38a487be37c7bdc0b14c957` — this one step stays bit-identical, so it is checkable without the board

## 4. OpenSBI, which became a committed blob mid-draft

- [ ] 4.1 Add an `opensbi-k230` derivation: fetch `riscv-software-src/opensbi` 1.4, apply the SDK's nine-file `opensbi-1.4-overlay`, generic platform, `FW_TEXT_START=0`. Do **not** substitute nixpkgs OpenSBI 1.8.1 — upstream matches `canaan,kendryte-k230` but without `THEAD_QUIRK_DISABLE_MAEE`, and that quirk clears `MXSTATUS.MAEE` so standard page-attribute bits behave. Verify with `nix build .#opensbi-k230` producing `fw_jump.bin` and `strings` on it finding `canaan,kendryte-k230`
- [ ] 4.2 Header it as `docs/evidence/uboot-env.txt` says stage 1 expects: `mkimage -A riscv -O linux -T kernel -C none -a 0 -e 0 -n linux`. Verify with `nix build .#fwJump` and `mkimage -l` on the result showing a RISC-V Linux kernel image at load 0 and entry 0
- [ ] 4.3 Delete `firmware/stage1/fw_jump.bin` and `fw_jump_add_uboot_head.bin` once 4.2 produces a working equivalent, and confirm nothing in the flake copies a binary out of `.build/`. Verify with `./tools/blob-scan.py` exiting 0 and `grep -rn '\.build/' flake.nix nix/` returning nothing

## 5. Boot what we compiled — **hardware claim**

- [ ] 5.1 Flash a second card with the stage 1 from task 3.3 alongside the existing system, keeping the known-good card untouched. Verify with `./tools/flash.sh` against a `/dev/disk/by-id` path and `fdisk -l` on the result showing the documented offsets
- [ ] 5.2 Power the board with a known-good data cable and capture the console. Verify by committing `docs/evidence/stage1-from-source.txt` containing the `PMU Major Msg:` training sequence and `U-Boot 2022.10` from a binary this project built, and confirming it reaches the same prompt the vendored chain reaches
- [ ] 5.3 Delete `firmware/stage1/fn_u-boot-spl.bin`, `fn_ug_u-boot.bin` and `env.env`, and rewrite `nix/stage1.nix` and `firmware/stage1/PROVENANCE.txt` around the derivations. Verify with `nix build .#stage1` succeeding and `git ls-files firmware/` listing no binary at all — the OpenSBI pair went in task 4.3, so this is the commit where `firmware/` becomes text

## 6. Ground the specs

- [ ] 6.1 Resolve the `UNVERIFIED` marker on "Stage 1 is built from source this project can read" against the transcript from task 5.2, and confirm the DDR PMU requirement still names the firmware's offset in the *new* SPL rather than the old one. Verify with `openspec validate every-blob-is-built-from-source-or-named`
- [ ] 6.2 Re-run the inventory scan after the deletions so `docs/blob-inventory.md` describes the tree as it then is, and record in it that A1–A3 are now derivations. Verify with `./scripts/build_site.py` exiting 0 and `openspec validate --all`
