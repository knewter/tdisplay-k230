## 1. Image (host)

- [x] 1.1 Give `mkBoardImage` an optional device tree and build `.#sdImage` from `k230-mainline-drm-shell` with its kernel and the mainline DRM DTB as `k230-tdisplay.dtb`. Proof: `nix build .#sdImage`, plus an inspection of the boot partition (kernel identity, DTB `/chosen/bootargs` init, stage-1 slot hashes) recorded in `docs/evidence/mainline-sd-image/`.
      Image 20mxf9lr…; boot `Image`/`initrd.uimg` byte-identical to the installed bundle p3hh3j32…; DTB and bootargs.txt `init=` select installed system kp6ldmdx…; DTB has the SD `sd_ref` core clock; stage-1 slots equal `.#stage1` ([inspection](../../../docs/evidence/mainline-sd-image/host-inspection.json)).
- [x] 1.2 Confirm vendor images are unchanged: `.#sdImage-coherent` evaluates to the same derivation as on master. Proof: matching `nix eval --raw .#sdImage-coherent.drvPath` before and after.
      `sdImage-coherent` i7sfnn3k… and `sdImage-rvv-trial` xqnk1nz1… drvPaths identical before and after.

## 2. Hardware (operator-scheduled)

- [ ] 2.1 Flash the image to a card (this erases it), power on, and verify 7.3.0-rc5 and active shell services over serial. Proof: serial record.

## 3. Publication

- [x] 3.1 Review, land, push, verify CI and the published page. Proof: `openspec validate --strict`, CI run id, page revision.
      Strict validate passes; landed e1334c83; CI/Pages run 37837179903 success; https://knewter.github.io/tdisplay-k230/work/ serves e1334c83f1ab. Change stays open for 2.1.
