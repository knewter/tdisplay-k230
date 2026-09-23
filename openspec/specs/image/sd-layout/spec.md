# image/sd-layout Specification

## Purpose
Defines what is written to the SD card and how a card is produced without
endangering the machine producing it.

## Requirements

### Requirement: The card carries stage 1 and our system in known regions

*Grounding: observed on hardware. Our layout has now been written to a card
and booted: stage 1 raw at 1M and 1.5M, U-Boot at 2M, environment at 3M and
3.5M, the boot ext4 at 4M and the root ext4 at 128M. The board boots from it
and mounts `/` from `/dev/mmcblk1p2` (`docs/evidence/hardware-userspace.md`).
One size in the list is empirical rather than chosen: the boot partition is
112 MiB because 83 MiB of content did not fit the original 80.*

The card SHALL carry the vendored stage 1 and the system this project builds in
documented regions, and the layout SHALL be recorded as offsets and sizes
rather than implied by a tool's defaults.

*Grounding for the shipped layout, read from the vendor image: raw boot
firmware occupies sectors 0 through 102399; partition 1 begins at sector 102400
and is 30 MB of FAT32 labelled `BIN`; partition 2 begins at sector 163840 and
is 500 MB of FAT32 labelled `SDCARD`.*

#### Scenario: A card is examined after flashing

- **WHEN** someone inspects a flashed card's partition table
- **THEN** it matches the layout the repository documents

### Requirement: Flashing names the target by a stable identifier

*Grounding: observed on this host. The card reader presents two slots as
`/dev/disk/by-id/usb-Generic-_USB3.0_CRW_-SD_201506301013-0:0` and `-0:1`,
while `/dev/sda` through `/dev/sdd` are the four 8 TB members of the RAID10
array. Device letters were seen to move across a replug of the reader during
this session.*

The flashing procedure SHALL identify the target by a `/dev/disk/by-id` path,
not by a kernel device node.

This is not stylistic. The development host carries four 8 TB RAID members on
`/dev/sda` through `/dev/sdd`, device letters are reassigned when a reader is
replugged, and a `dd` to the wrong node destroys the array. A `by-id` path can
only ever resolve to the one reader slot.

The procedure SHALL also show what is on the card and require confirmation
before writing, because a card that looks blank may not be.

#### Scenario: A card is flashed

- **WHEN** the flashing procedure runs
- **THEN** the target is given as a by-id path, its current contents are shown, and writing waits for confirmation

#### Scenario: The target is given as a bare device node

- **WHEN** someone passes `/dev/sdX` instead of a by-id path
- **THEN** the procedure refuses rather than guessing

### Requirement: The running system can use the card beyond the compact image

*Grounding: `docs/evidence/storage-capacity/board-before.json`, `board-after.json` and `board-repeat.json` record two physical boots of the integrated image system and matching boot files on the existing compact root. The boot service grew ext4 from 2,173,693,952 to 127,800,422,400 bytes; the second boot reported no change. Shell and Wi-Fi recovered. `image-build.json` separately proves the downloadable image remains compact. No full-image reflash or manual resize was used for this trial.*

On a card with the repository's supported layout and unallocated trailing space, the system SHALL grow its final root partition and ext4 filesystem during boot so that the trailing capacity becomes usable without a manual resize. The downloadable image SHALL remain compact. The system SHALL retain root contents, filesystem identity, and the fixed root start offset. Stage 1 SHALL not own this growth.

#### Scenario: First boot on a larger card
- **WHEN** a compact image boots on a larger card with the expected final root partition
- **THEN** the root filesystem gains usable capacity from the trailing space
- **AND** the normal shell starts with existing root contents and filesystem identity intact

#### Scenario: A grown card boots again
- **WHEN** the same card reboots after successful growth
- **THEN** its partition boundaries and filesystem identity remain unchanged
- **AND** the shell returns without repeated destructive work

### Requirement: Root growth preserves boot regions and refuses unsupported layouts

*Grounding: physical first/repeat boot captures in `docs/evidence/storage-capacity/` preserve root/boot identities, the MBR boot code, firmware-gap hash, all eight selected boot-file hashes and a root-file sentinel. The actual disposable-system QEMU cases in `qemu/result.json` separately prove unsupported-layout refusal, tool-failure preservation and partition-only retry. Those negative cases are guest proof, not destructive tests on the physical card.*

The system SHALL preserve raw stage-1 payloads, the boot partition's start, size and contents, and the root partition's start and identity. It SHALL grow only the positively identified mounted ext4 root in the supported final-partition layout. If the root device, labels, partition table or filesystem is unexpected, or any later partition exists, it SHALL refuse growth before writing and retain a bootable system with a recorded reason. A growth error SHALL not erase data or require root reformatting. A subsequent boot SHALL safely handle a partition already enlarged before filesystem growth completed.

#### Scenario: Boot data survives growth
- **WHEN** root growth completes
- **THEN** protected firmware bytes and named boot files match their pre-growth values
- **AND** boot partition boundaries and the root start offset match the documented layout

#### Scenario: There is a later partition or the layout is not recognized
- **WHEN** the card has a partition after root, an unexpected layout or an unsupported root filesystem
- **THEN** neither partition nor filesystem growth writes occur
- **AND** boot continues with the existing capacity and a diagnostic identifying the refusal

#### Scenario: No additional capacity exists
- **WHEN** the supported root already occupies the available trailing space
- **THEN** boot succeeds without changing partition boundaries or existing file contents

#### Scenario: Partition growth finished before filesystem growth was interrupted
- **WHEN** the system boots with a valid enlarged root partition and its original smaller ext4 filesystem
- **THEN** it safely completes filesystem growth without recreating the partition or losing contents
