## Purpose

Defines what is written to the SD card and how a card is produced without
endangering the machine producing it.

## ADDED Requirements

### Requirement: The card carries stage 1 and our system in known regions

<!-- UNVERIFIED: our own layout has not been written or booted. The shipped
layout below is observed; ours is not yet. -->

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
