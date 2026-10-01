## Purpose

Let people download source-pinned development handheld images and inspect their checksums, system selection and actual validation limits.

## ADDED Requirements

### Requirement: Source-pinned development image release
<!-- UNVERIFIED: new host publication capability; physical image acceptance is separate. -->
The host release task SHALL build an explicit committed source revision using the pinned flake's coherent Rust-shell image and normal vendor kernel. It SHALL publish a fresh GitHub prerelease with a compressed image, SHA256SUMS and machine-readable provenance identifying the source revision, image derivation, system and kernel. Artifacts SHALL remain outside Git.

#### Scenario: Person downloads a development snapshot
- **WHEN** an operator runs the release task for a clean committed revision and unused tag
- **THEN** the resulting release provides the compressed image and checksums with exact source and system provenance
- **AND** notes identify host checks obtained and explicitly state that the image has not been physically accepted when no such proof exists

### Requirement: Existing releases and provenance are protected
<!-- UNVERIFIED: new host publication capability. -->
The host release task MUST reject dirty tracked source, staging inside the repository, source/provenance mismatches, and existing release or tag names. It SHALL retain GC roots through publication and verify uploaded asset sizes and SHA256 digests.

#### Scenario: Operator attempts an ambiguous or duplicate release
- **WHEN** the source is dirty, an asset does not match its provenance, or a tag already exists
- **THEN** the task exits without replacing an existing release or asset
