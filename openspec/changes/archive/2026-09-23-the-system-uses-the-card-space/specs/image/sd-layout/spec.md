## ADDED Requirements

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
