## Context

See `proposal.md` for the capacity failure and `docs/evidence/storage-capacity/preflight.json` for the physical measurements. The root starts at 128 MiB after the fixed boot/firmware areas. `nix/hardware.nix` declares ext4 by label without growth. The observed card has ample unused tail space; reclaiming old diagnostic packages would only postpone this limit on fresh images.

## Goals / Non-Goals

**Goals:** let a fresh, compact image use its actual card capacity; make repeat boots and interrupted two-phase growth safe; provide proof for both filesystem behavior and fixed boot boundaries.

**Non-Goals:** see the proposal. In particular, do not turn this into a generic host-disk tool or delete store paths/home data to make a test fit.

## Decisions

- **Owner: system userspace, configured by Nix.** Growth happens after identifying the mounted root. Stage 1, kernel patches and flash-image byte counts remain unchanged. Increasing the static image size wastes transfer time and still guesses the user's card size, so it is rejected.
- **Guard both partition and filesystem mutation together.** Require the known labels, ext4 root, unchanged documented starts/boot size, a supported partition table and no later partition. Derive the physical target from the mounted root, never a guessed `mmcblk` number. Any failed check precedes either mutation. A layout with later partitions is refused even if a gap could be consumed safely; partition rearrangement is outside this scope.
- **Reuse pinned tools, with explicit service ordering.** The inspected nixpkgs `nixos/modules/system/boot/grow-partition.nix` exposes `boot.growPartition` using cloud-utils `growpart`; it tolerates exit 1 for already-full partitions and orders before filesystem growth. It does not supply this project's complete layout guard and has an infinite timeout. Use those pinned utilities behind a single guarded, finitely bounded oneshot; reuse stock options only if both mutation phases can be gated together. Do not independently enable filesystem auto-growth on a refused layout. A failed growth job must not make the existing root/shell unavailable.
- **Keep expansion and flashing contracts distinct.** A newly flashed card retains the existing compact layout. A successful boot may extend only the end of root. Existing stable-target flash checks and recovery routes remain intact; this change does not introduce routine whole-image readbacks.
- **Test disposable media before the board.** Exercise actual partition/filesystem tools in an isolated QEMU guest with sparse disk fixtures, including data sentinels and named firmware/boot regions. Host parsing or fake command success cannot prove ext4 preservation. Record exact guest/kernel/tool identities and keep board boot evidence separate.

## Risks / Trade-offs

- [A mistaken target could damage boot data] → derive and validate the mounted root, refuse unsupported layouts before writing, test negative layouts and preserve a known recovery artifact.
- [Growth interrupted between phases] → retain start/identity, recognize already-grown partitions, and test retry with the smaller valid filesystem.
- [Boot could wait indefinitely] → bound the service and retain the existing shell route with a clear growth failure; test an injected tool failure.
- [The hardware bootloader sees an unexpected partition change] → keep firmware/boot locations fixed and require actual board boot plus a second reboot before archive.
- [Full-card root changes runtime partition sizes] → document compact image versus post-boot layout; do not shrink on rollback. Removing growth configuration leaves the valid enlarged filesystem usable.

## Migration Plan

Land this proposal first. Implement/evaluate the narrow guarded service and run disposable-image tests. Build a matching system/image only after those checks pass. Preserve the normal recovery image, reserve the board, and record pre-growth identities/boundaries and boot-file hashes. Prove first boot, increased available capacity, root sentinel retention, normal shell/Wi-Fi recovery without publishing credentials, and a second reboot with unchanged boundaries. A source build or temporary manual resize does not satisfy the default-image boot requirement. Keep every physical task open until that evidence is committed.
