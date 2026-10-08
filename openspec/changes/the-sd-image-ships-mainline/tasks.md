## 1. Image (host)

- [ ] 1.1 Give `mkBoardImage` an optional device tree and build `.#sdImage` from `k230-mainline-drm-shell` with its kernel and the mainline DRM DTB as `k230-tdisplay.dtb`. Proof: `nix build .#sdImage`, plus an inspection of the boot partition (kernel identity, DTB `/chosen/bootargs` init, stage-1 slot hashes) recorded in `docs/evidence/mainline-sd-image/`.
- [ ] 1.2 Confirm vendor images are unchanged: `.#sdImage-coherent` evaluates to the same derivation as on master. Proof: matching `nix eval --raw .#sdImage-coherent.drvPath` before and after.

## 2. Hardware (operator-scheduled)

- [ ] 2.1 Flash the image to a card (this erases it), power on, and verify 7.3.0-rc5 and active shell services over serial. Proof: serial record.

## 3. Publication

- [ ] 3.1 Review, land, push, verify CI and the published page. Proof: `openspec validate --strict`, CI run id, page revision.
