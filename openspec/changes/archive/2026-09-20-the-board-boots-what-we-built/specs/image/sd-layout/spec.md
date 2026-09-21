## Purpose

Defines what is written to the SD card and how a card is produced without
endangering the machine producing it.

## ADDED Requirements

### Requirement: The card carries stage 1 and our system in known regions

*Grounded on hardware. Our layout has now been written to a card and booted:
stage 1 raw at 1M and 1.5M, U-Boot at 2M, environment at 3M and 3.5M, the boot
ext4 at 4M and the root ext4 at 128M. The board boots from it and mounts `/`
from `/dev/mmcblk1p2` (`docs/evidence/hardware-userspace.md`). One size in the
list is empirical rather than chosen: the boot partition is 112 MiB because
83 MiB of content did not fit the original 80.*

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
