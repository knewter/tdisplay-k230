## 1. Launcher implementation

- [x] 1.1 Extend the Apps page in `nix/touch-menu.sh` with coloured, 56-pixel-high Terminal, Monitor, New terminal, and Back targets that fit the 568-pixel bar; preserve existing home, keyboard, window, and system actions. Verify the i3bar frames have explicit names, widths, and colours.
- [x] 1.2 Add the New terminal action using the existing readable terminal profile, while Terminal keeps focus-or-start recovery behaviour. Verify action tests distinguish focus-or-start from a deliberate additional Foot launch.

## 2. Laptop verification

- [x] 2.1 Extend `tests/test_touch_menu.py` for the launcher page, target geometry, colours, Back, and New terminal. Verify `python3 tests/test_touch_menu.py` passes and `nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath` succeeds. This is a laptop claim.

## 3. Physical verification

- [ ] 3.1 **Hardware.** On the panel, tap Apps, Terminal, Monitor, New terminal, and Back, recording whether each interaction was a real glass touch or injected. Verify with a camera capture and a committed manifest under `docs/evidence/shell-features/`; release the board after capture.
