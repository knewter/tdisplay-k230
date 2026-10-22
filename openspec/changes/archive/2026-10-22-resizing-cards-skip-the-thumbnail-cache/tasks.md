## 1. Host

- [x] 1.1 Skip the scaled cache in `scaled_mirror` while in motion when the size differs from the cached thumbnail. Proof: `python3 -m unittest tests.test_card_scaled_cache`.
- [x] 1.2 Build the landscape system. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel` (`pb5l6lmb`).

## 2. Board (hardware-only)

- [x] 2.1 Profile busy-arm entry and tap on the boot default, and run the busy arm before (`sgjam1h0`) and after (`pb5l6lmb`, test-activated) with `card-entry.py --bench` (`docs/evidence/interaction-jank/card-resize/README.md`: entry interval 38.3 → 19.2 ms median, acknowledgement 129 → 69 ms).
- [x] 2.2 Run the video arm on `pb5l6lmb`, and check rest-state grim captures of the deck and expanded card (entry intervals over budget 38 → 2; drag and tap unchanged; captures normal).
- [x] 2.3 Promote the build from master to the boot default, and verify an ordinary boot plus one busy-arm run on it (`pb5l6lmb`, boot `69d72d47…`, run-boot-busy: entry interval median 19.2 ms, acknowledgement 73 ms).
