## 1. Package and portrait adaptation

- [x] 1.1 Pin upstream source/licenses and package the app with software Wayland
  rendering and bounded portrait/file-dialog adaptations; verify
  `nix build .#omawrite --cores 6 --no-link --print-out-paths` and record the
  exact output, architecture and closure size.
- [x] 1.2 Exercise editing/save/reopen, portrait controls/dialog cancellation
  and palette changes with the actual app; run
  `python3 tests/omawrite_runtime.py --sway <sway> --omawrite <app> --output <dir>`.
  This is host/headless proof, not device or finger acceptance.
  PASS: [host evidence](../../../../docs/evidence/omawrite/README.md).

## 2. Image defaults

- [x] 2.1 Preserve the Editor desktop ID, install its Omawrite icon/launch path
  and MIME defaults, and build the coherent image with
  `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --cores 6 --no-link --print-out-paths`.
  Inspect its installed desktop/MIME entries and retain Nano for CLI recovery.

## 3. Device proof and delivery

- [x] 3.1 Reserve the board; run a bounded trial of the exact app/system with
  `python3 tools/console.py /dev/ttyACM0 --wait=3 '<recorded trial command>'`.
  Commit the expanded command, native captures, backend identity, scratch-file
  edit/save/reopen result, Open/Save dialog observations, keyboard show/hide,
  and Overview/Home return. Distinguish injected input from real fingers.
- [x] 3.2 Persist the qualified system using the existing guarded userspace
  install helper; record system/profile/boot bundle identity and healthy services.
  Keep the previous image available; do not read back the entire card.
- [x] 3.3 Land source/evidence on master, inventory media, validate with
  `openspec validate the-editor-opens-omawrite --strict`, and verify the matching
  CI/Pages deployment and published evidence. Archive only if every named
  requirement has its proof; preserve any unperformed evidence gate explicitly.
