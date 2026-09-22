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

## 2. Installed application catalogue

- [x] 2.1 Use GDesktopAppInfo/GAppInfo for refresh-on-open XDG discovery,
filtering, precedence, safe launch, and pagination; retain built-ins and test
fixtures for hidden/overridden/space-containing Exec entries.
- [x] 2.2 Render dynamic labels with Pango/Cairo and bridge Terminal=true to
Foot; verify graceful unsupported launch behavior.

## 3. Laptop package verification

- [x] 3.1 Build the named launcher derivation with `nix build
  .#touch-launcher --option max-jobs 2 --option cores 8` after the coordinated
  builder slot is idle; inspect `nix path-info -Sh .#touch-launcher`. This is
  a cross-package claim, not hardware proof.
- [x] 3.2 Run `python3 tests/test_touch_menu.py`, `python3 tests/test_desktop_catalog.py`,
  `nix eval --raw .#nixosConfigurations.k230.config.system.build.toplevel.drvPath`,
  and `openspec validate the-shell-launches-apps-without-a-keyboard --strict`.
  Record their laptop-only result and a labelled layout preview.

## 4. Physical verification

- [x] 4.1 **Hardware.** On the panel, tap Apps, Terminal, Monitor, New
  terminal, and Back. Record whether each interaction was real glass touch or
  injected, with camera capture and a committed manifest under
  `docs/evidence/shell-features/`. Release the board after capture.

Fixed baseline 4.1 evidence: `docs/evidence/shell-features/portrait-launcher/README.md`
and its final camera recording, screenshots, action script and window-tree log.
Input was injected; actual finger accuracy remains the parent shell change's task.

- [x] 4.2 **Hardware.** Record the desktop-aware launcher listing the installed
  Foot/Htop entries, paging, launching a Terminal=true entry, and reflecting a
  temporary entry's addition and removal on reopen. Capture keyboard layout and
  an error path with a recoverable Back control. Commit the script, console,
  screenshots, camera clip and provenance under `docs/evidence/shell-features/`.
- [ ] 4.3 Integrate the verified configuration in a bootable source-built image
  and capture the desktop-aware launcher after reboot. A runtime service override
  alone does not complete this task.

Discovery task 4.2 evidence: `docs/evidence/shell-features/desktop-launcher/README.md`
and its video, screenshots and console. Input was injected on the physical board.

The user separately confirmed launcher finger usability on 2026-09-22; see
`docs/evidence/shell-features/desktop-launcher/README.md`. Existing video
provenance stays injected. Broader axis/battery/system-control tasks stay open.
