## Why

A person cannot download the latest coherent handheld image from GitHub without rebuilding it and manually reconstructing its provenance. Publishing a source-pinned development snapshot should be a repeatable local task with auditable assets.

## What Changes

- Add a manual host command that builds the pinned coherent Rust-shell image with the normal vendor kernel, stages a compressed image, SHA256SUMS and provenance outside Git, then creates a fresh GitHub prerelease.
- Reject dirty tracked source, mismatched revisions and existing release/tag names; retain Nix GC roots through publication and verify uploaded asset hashes.
- Document usage and record the first publication's host evidence and physical-validation limits.
- Non-goals: automatic CI releases, changing the default image, flashing, kernel experiments, or claiming physical boot acceptance.

## Capabilities

### New Capabilities

- `image/releases`: Downloadable development image snapshots with exact source and validation provenance.

### Modified Capabilities

None.

## Impact

Host tooling in `tools/release-image.py`, host tests, release documentation and GitHub Releases. Uses Git, pinned Nix, Python, xz and authenticated gh. No board access is needed; the published image's physical acceptance remains separate.
