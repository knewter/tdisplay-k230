# Tasks

Task groups here make **hardware claims** unless they say otherwise. A QEMU run
proves nothing in this change — QEMU's `k230` machine models neither the
vendored boot chain nor the SD card.

**Group 2 was added after the change was proposed.** The plan assumed the
kernel from `a-riscv-nixos-closure-cross-builds` could boot this board. It
cannot: mainline ships no K230 device tree and no `SOC_CANAAN_K230`, so a
stock nixpkgs kernel has nothing to boot with. The Xuantie kernel was going
to be `the-screen-comes-up-under-linux`'s work; it is pulled forward here
because nothing in groups 4 and 5 is reachable without it. The panel and
touch remain that change's job.

## 1. Obtain and pin stage 1

- [x] 1.1 Build `k230_linux_sdk` with `k230_canmv_v3_defconfig` in Docker on Ubuntu 22.04, and keep the firmware stage. Verify by recording the SDK commit, the defconfig, and the sha256 of the artifact in `docs/evidence/stage1-provenance.txt`
- [x] 1.2 Pin that artifact in the flake. Verify with `nix build .#stage1.verified` and confirm the hashes match what was recorded
- [x] 1.3 Read the vendored U-Boot's environment and record how it expects to find a kernel — filename, filesystem, and any script it sources. Verify by committing the extracted environment to `docs/evidence/uboot-env.txt`

## 2. A kernel that can boot this SoC

- [x] 2.1 Package `ruyisdk/linux-xuantie-kernel` at the revision `k230_canmv_v3_defconfig` pins, built from source with `k230_defconfig` plus the options NixOS requires. Verify with `nix build .#packages.x86_64-linux.kernel` and confirm `Image` is produced
- [x] 2.2 Confirm it emits a K230 device tree, which the stock kernel does not. Verify with `ls $(nix build --no-link --print-out-paths .#packages.x86_64-linux.kernel)/dtbs/canaan/` showing `k230-canmv-v3.dtb`
- [x] 2.3 Record why mainline could not be used, so this pin is understood as forced rather than preferred. Verify by committing the Kconfig and device-tree evidence to `docs/evidence/why-xuantie-kernel.txt`

## 3. An SD image

- [x] 3.1 Build an image placing stage 1 at the raw offsets from the SDK's `genimage.cfg`, and a boot ext4 carrying the three filenames task 1.3 found U-Boot loads. Verify with `nix build .#sdImage` and `fdisk -l` on the result showing the documented layout
- [x] 3.2 Write `tools/flash.sh` taking only a `/dev/disk/by-id` path, refusing bare device nodes, and printing the card's current contents before writing. Verify by running it against a bare `/dev/sdX` and confirming it refuses, and against a by-id path with the write declined

## 4. The board boots it

- [x] 4.1 Flash a card and power the board with a known-good data cable. Verify by capturing the console to `docs/evidence/hardware-boot.txt` and confirming stage 1 hands off to our kernel
- [x] 4.2 Reach an interactive prompt and run one command that could only run on this hardware. Verify by extending that transcript with the output of `cat /proc/cpuinfo` showing a `thead,c908` hart
      - Clause corrected during implementation. It originally read "showing
        two C908 harts", written from the datasheet before anything had
        booted. The SoC does have two C908s, but no K230 device tree declares
        a `cpu@1` -- every `cpu@1` under `dts/canaan` belongs to the K210 --
        so Linux sees one hart and the second core is Canaan's AMP core for
        RT-Smart. No spec delta in this change asserted a hart count, so this
        corrects a verification instruction, not a requirement.
        Evidence: `docs/evidence/hardware-userspace.md` -- `uarch: thead,c908`,
        `mvendorid: 0x5b7`, run at a root prompt on the board.
- [x] 4.3 Record what differs between the QEMU boot and this one. Verify by extending `docs/evidence/boot-path-differences.md`, citing both transcripts

## 5. Ground the specs

- [x] 5.1 Resolve the `UNVERIFIED` markers in `image/boot-chain` and `image/sd-layout` against the committed hardware transcript, or restate what remains unproven. Verify with `openspec validate the-board-boots-what-we-built`
- [x] 5.2 Confirm the modified `system/nixos-config` boot requirement is met on hardware and cite the transcript path from it. Verify with `openspec validate --all`
