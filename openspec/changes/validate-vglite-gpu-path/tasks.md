## 1. Source-built validation package

- [x] 1.1 Add a source-built optional VG-Lite validation executable for RGB565, alpha/color, DRM dma-buf import, and bounded GPU/Pixman timing; verify with `nix build .#k230-vglite-validation --max-jobs 1 --cores 8`.
- [x] 1.2 Expose the validation executable as a flake package without adding it to the system closure; verify with `nix eval .#packages.x86_64-linux.k230-vglite-validation.name`.

## 2. Evidence and board procedure

- [x] 2.1 Document the source/API boundary, private DRM constraints, exact board commands, output contract, and integration gate; verify `openspec validate validate-vglite-gpu-path --strict` and `git diff --check`.
- [ ] 2.2 Board coordinator: run each validation subtest with the shell active, capture the transcript in `docs/evidence/`, and verify there was no modeset or service interruption. Hardware proof only; do not tick from a host build.
- [ ] 2.3 Make an integration recommendation from the captured board evidence; verify the recommendation distinguishes private-buffer, dma-buf, and compositor/scanout claims. Hardware evidence required.
