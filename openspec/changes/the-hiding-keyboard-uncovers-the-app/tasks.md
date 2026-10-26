## 1. Host

- [x] 1.1 Add `kg_reserved` to the keyboard policy and use it for the usable area in `card_shell_keyboard_adjust_usable`. Proof: `python3 -m unittest tests.test_keyboard_gestures` (17 tests, including `hide-reserve`).
- [x] 1.2 Carry a resize that `ordinary_sync_usable` recorded without committing to its next committing call (`ordinary_resize_pending`), found by 2.1.
- [x] 1.3 Build the landscape system. Proof: `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape-hdmi.config.system.build.toplevel` (`dwdcnvqb` for this source).

## 2. Board (hardware-only)

- [x] 2.1 Test-activate the build. Capture native frames during an injected slow grip hide and a hold-and-reverse, showing app content, not the backdrop, below the moving keyboard. Re-run the keyboard cycles with `--bench` against the boot default. Proof: `docs/evidence/interaction-jank/keyboard-hide` (board, injected touch, grim): 0 light rows above the grip mid-hide and held, against 84–130 before 1.2; no presented-interval median worse than `h4rqzlgr` on the same boot.
- [x] 2.2 The operator slides the keyboard down on real glass and confirms that no opaque strip appears. Physical proof: a timestamped operator report tied to the installed build (`docs/evidence/shell-design-review/operator-report.md`: "looks good" on `1r8zfd5s`, 2026-10-26).
- [x] 2.3 Promote the build from master to the boot default and verify an ordinary boot (`1r8zfd5s`, which carries this fix, boot `887f0c98…`, `docs/evidence/shell-design-review/promotion/receipt.json`).
