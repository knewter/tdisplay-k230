## 1. Candidate evaluation

- [x] 1.1 Evaluate `nano`, `lf`, and `nnn` against the pinned riscv64 package set, record desktop IDs, package derivations, and whether each builds without adding an unsupported toolchain; verify with the narrow Nix evaluation command and saved JSON evidence.
- [x] 1.2 Measure each candidate's NAR/closure delta against the current shell image and record startup and memory observations; verify with the named derivation closure commands and an evidence file that labels estimates versus measured values.
- [x] 1.3 Select at most one editor and one file browser from the recorded results and write the rejection reason for every omitted candidate; verify the selected set is no larger than the approved bounded list and does not add a network installer or general desktop suite.

## 2. Desktop entries and Help surface

- [x] 2.1 Add selected terminal applications as minimal visible desktop entries using `Terminal=true` and the existing Foot bridge; verify `k230-desktop-catalog list` discovers each ID and `k230-desktop-catalog launch ID` preserves the configured terminal environment.
- [x] 2.2 Add a built-in Help card/page to the existing portrait launcher with concise pages for Apps, Keyboard, Windows/Home, System, Terminal, Monitor, Back, and Previous/Next; verify the host launcher tests cover page bounds, Back, and empty-catalog behavior.
- [x] 2.3 Keep Help and the existing built-ins available when no optional candidate is selected or a candidate launch fails; verify an injected launch-error workflow leaves a usable Back control.

## 3. Package and hardware validation

- [x] 3.1 Build the launcher and each selected package separately for the pinned target and record the exact derivation outputs; verify with the narrow package build commands before attempting an image build.
- [x] 3.2 Build the shell image with the selected set and compare startup/closure evidence against the recorded baseline; verify the report distinguishes host/package proof from QEMU or hardware proof.
- [x] 3.3 Boot the resulting image and confirm startup, catalog discovery, Help rendering, and candidate launch/return using injected input; verify with the existing shell evidence workflow and label physical-finger, reboot, and final-glass checks as unverified until separately observed.

## 4. Review and integration

- [x] 4.1 Capture portrait screenshots and a concise evidence record for Help pages and each selected app, including desktop ID, package source, closure delta, startup result, and injected touch result; verify all links and claims in the evidence README.
- [x] 4.2 Run the relevant shell tests and validate the OpenSpec change; verify with `python3 tests/test_touch_menu.py`, `python3 tests/test_desktop_catalog.py`, and `openspec validate the-shell-offers-offline-apps-and-help --strict`.

For task 1.1, run for each candidate (substitute `lf` or `nnn` for `nano`):
`nix eval --raw --impure --expr '(builtins.getFlake (toString ./.)).nixosConfigurations.k230.pkgs.nano.drvPath'`.
For task 3.1 use `nix build --impure --expr '(builtins.getFlake (toString ./.)).nixosConfigurations.k230.pkgs.nano' --option max-jobs 1 --option cores 8 --option substituters https://cache.nixos.org`;
coordinate the builder slot first. Measure `nix path-info -S` and the closure
set difference against the recorded current system. These are host claims.
Task 3.2 uses `nix build .#sdImage` with the same coordinated limits.
Task 3.3 and startup/memory observations in 1.2 require the physical board;
a host process or QEMU cannot prove this panel workflow.

2026-09-22 progress: host candidate outputs/desktop IDs and closure differences
are in `docs/evidence/offline-app-candidates/`; the injected physical-board Help,
error recovery, nano and nnn trials are in `docs/evidence/offline-help-injected/`.
The final lf board trial records startup and 8,576 KiB RSS, completing task 1.2;
it remains rejected in favor of nnn on closure size and observed memory. Fresh-image integration, boot, catalog discovery and injected launches are
recorded in `docs/evidence/offline-wifi-image/README.md`. Navigation tests include `python3 tests/test_launcher_navigation.py`.
