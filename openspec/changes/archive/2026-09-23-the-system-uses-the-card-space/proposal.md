## Why

The handheld cannot stage the next complete system trial because its root filesystem has only 77 MB free, even though the physical card is about 128 GB. The flashed image leaves the root partition at about 2.2 GB; the same limit also restricts ordinary app installation and Nix updates. Board measurements are committed in `docs/evidence/storage-capacity/preflight.json`.

## What Changes

- Grow the image's final root partition and ext4 filesystem into the card's available trailing space during boot, with repeat boots behaving as a no-op once full.
- Keep the compact distributable image and all raw stage-1 regions, boot-partition boundaries, labels and root start offset intact.
- Refuse ambiguous or unsupported layouts, including a later partition, without moving or overwriting existing data; retain a usable boot and an actionable diagnostic on failure.
- Record disposable-image tests and actual board boot/reboot proof before claiming the default image expands correctly.

Non-goals: moving partitions, shrinking filesystems, general disk management, automatic deletion of Nix generations or app data, changes to flashing target authorization, GPU/RVV default selection, or restoring mutable home-directory state.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `image/sd-layout`: distinguish compact flashed root size from safely expanded running size while preserving fixed boot locations.

## Impact

The system owns growth through NixOS configuration and a bounded layout guard. Likely paths are `nix/hardware.nix`, a narrow growth helper/module if the pinned NixOS options need extra guards, and dedicated disposable-image tests. Stage 1 and flashing remain unchanged. Host/QEMU tests can proceed independently; acceptance requires the physical board, a recovery artifact and serial ownership. This unblocks staging larger trial closures but does not itself prove RVV, card performance or GPU correctness.
