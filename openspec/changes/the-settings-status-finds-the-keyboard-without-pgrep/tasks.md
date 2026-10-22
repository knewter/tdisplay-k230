## 1. Host

- [x] 1.1 Replace the `pgrep` child with a `/proc` scan, and test the matching rules and the no-child production read. Proof: `python3 -m unittest tests.test_settings_status tests.test_device_settings`.
- [x] 1.2 Build the landscape system. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel` (`sgjam1h0`).

## 2. Board (hardware-only)

- [x] 2.1 Test-activate `sgjam1h0`, then compare `k230-settings status` timing and keyboard state for the old and new wrappers as the `shell` user (`docs/evidence/interaction-jank/shade-pull/README.md`: 103 → 28 ms per call, both `action`).
- [x] 2.2 Run injected shade pulls before (`g2yjvzv4`) and after (`sgjam1h0`), and record the presented cadence and client callback-to-commit (run-base, run-n, run-n2, run-n3).
- [ ] 2.3 Promote `sgjam1h0` (or its successor on master) to the boot default, and verify an ordinary boot plus one shade-pull run on it.
