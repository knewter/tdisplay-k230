# Tasks

Task groups here make **hardware claims** unless they say otherwise. A QEMU run
proves nothing in this change — QEMU's `k230` machine models neither the
vendored boot chain nor the SD card.

## 1. Obtain and pin stage 1

- [x] 1.1 Build `k230_linux_sdk` with `k230_canmv_v3_defconfig` in Docker on Ubuntu 20.04, and keep the firmware stage. Verify by recording the SDK commit, the defconfig, and the sha256 of the artifact in `docs/evidence/stage1-provenance.txt`
- [x] 1.2 Pin that artifact as a fixed-output derivation in the flake. Verify with `nix build .#stage1` and confirm the hash matches what was recorded
- [x] 1.3 Read the vendored U-Boot's environment and record how it expects to find a kernel — filename, filesystem, and any script it sources. Verify by committing the extracted environment to `docs/evidence/uboot-env.txt`

## 2. An SD image

- [ ] 2.1 Build an image placing stage 1 and our kernel, DTB and initrd where task 1.3 says U-Boot will look. Verify with `nix build .#sdImage` and `fdisk -l` on the result showing the documented layout
- [x] 2.2 Write `tools/flash.sh` taking only a `/dev/disk/by-id` path, refusing bare device nodes, and printing the card's current contents before writing. Verify by running it against a bare `/dev/sdX` and confirming it refuses, and against a by-id path with the write declined

## 3. The board boots it

- [ ] 3.1 Flash a card and power the board with a known-good data cable. Verify by capturing the console to `docs/evidence/hardware-boot.txt` and confirming stage 1 hands off to our kernel
- [ ] 3.2 Reach an interactive prompt and run one command that could only run on this hardware. Verify by extending that transcript with the output of `cat /proc/cpuinfo` showing two C908 harts
- [ ] 3.3 Record what differs between the QEMU boot and this one. Verify by committing that comparison to `docs/evidence/boot-path-differences.md`, citing both transcripts

## 4. Ground the specs

- [ ] 4.1 Resolve the `UNVERIFIED` markers in `image/boot-chain` and `image/sd-layout` against the committed hardware transcript, or restate what remains unproven. Verify with `openspec validate the-board-boots-what-we-built`
- [ ] 4.2 Confirm the modified `system/nixos-config` boot requirement is met on hardware and cite the transcript path from it. Verify with `openspec validate --all`
