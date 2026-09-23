## ADDED Requirements

### Requirement: The running system can use the card beyond the compact image

<!-- UNVERIFIED -->
*Grounding for the problem: `docs/evidence/storage-capacity/preflight.json` records a 127,934,660,608-byte physical card, a 2,173,693,952-byte root partition and only 77,070,336 available filesystem bytes. Automatic growth has not been implemented or observed.*

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

<!-- UNVERIFIED -->
*Grounding for the boundaries: the existing `image/sd-layout` hardware evidence fixes the raw stage-1 areas, boot partition and root start. `docs/evidence/storage-capacity/preflight.json` confirms the current two-partition ext4 card. Refusal and preservation during growth remain unverified.*

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
