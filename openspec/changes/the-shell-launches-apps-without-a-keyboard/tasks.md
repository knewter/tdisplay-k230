## 1. Launcher implementation

- [x] 1.1 Give the original bar Apps row named actions and test its JSON/action
  behavior. This remains the persistent entry point and fallback.
- [x] 1.2 Add New terminal with the existing readable Foot profile while
  retaining Terminal focus-or-start behavior. Verify it through the menu
  action test.
- [x] 1.3 Add the local Wayland SHM/layer-shell launcher and its fixed action
  bridge. Verify host source checks and package installation expose the client
  and action helper without arbitrary command input.
- [x] 1.4 Wire Apps to start the portrait launcher without removing the
  Keyboard, Windows/Home, or System bar controls. Verify the menu protocol
  test covers the start action.

## 2. Laptop package verification

- [x] 2.1 Build the named launcher derivation with `nix build
  .#touch-launcher --option max-jobs 2 --option cores 8` after the coordinated
  builder slot is idle; inspect `nix path-info -Sh .#touch-launcher`. This is
  a cross-package claim, not hardware proof.
- [x] 2.2 Run `python3 tests/test_touch_menu.py`, source-level launcher tests,
  `nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`,
  and `openspec validate the-shell-launches-apps-without-a-keyboard --strict`.
  Record their laptop-only result and a labelled layout preview.

## 3. Physical verification

- [ ] 3.1 **Hardware.** On the panel, tap Apps, Terminal, Monitor, New
  terminal, and Back. Record whether each interaction was real glass touch or
  injected, with camera capture and a committed manifest under
  `docs/evidence/shell-features/`. Release the board after capture.
