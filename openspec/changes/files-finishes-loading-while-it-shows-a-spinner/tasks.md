## 1. Host

- [x] 1.1 Add `nix/patches/gtk4-wayland-cairo-damage.patch` and apply it to
  gtk4 in the board overlay in `nix/hardware.nix` (riscv64 only). Proof: the
  patched gtk4 builds:
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.pkgs.gtk4`.
  *Host build, 2026-10-29: derivation `kdn7aa7w…` built to `44233ral…`. The overlay evaluates to the same derivation.*
- [ ] 1.2 Build the board system with the patch. Proof:
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel`.

## 2. Board (hardware-only; one operator holds the board)

- [x] 2.1 Before deploying, load the patched `libgtk-4.so` into a test
  launcher with `LD_LIBRARY_PATH`. Record `WAYLAND_DEBUG` damage for the
  lone-spinner window and for Files, and the time until Files' main thread
  goes idle on the home folder. Proof: the numbers in
  `docs/evidence/files-app/slow-load/README.md`.
  *Board, injected launches, 2026-10-29: spinner damage went from 444 of 444 frames full-buffer to 2 of 794, and Files went idle 8.4 s after launch instead of being still busy after 300 s.*
- [ ] 2.2 Test-activate the system build. Open Files from the drawer with
  injected touch, and grim-capture the loaded home folder with no stale
  pixels around the loading bar. Record the time to idle. Proof: the same
  README and its captures.
- [ ] 2.3 Glass: the operator opens Files from the drawer and reports
  whether the folder appears promptly. Physical proof: a timestamped
  operator report tied to the installed build.
- [ ] 2.4 Promote the build to the boot default and verify an ordinary boot.

## 3. Closeout

- [ ] 3.1 Archive once 2.1–2.4 are done. Proof:
  `openspec validate files-finishes-loading-while-it-shows-a-spinner --strict`.
