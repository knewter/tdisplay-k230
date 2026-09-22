## 1. Candidate evaluation

- [ ] 1.1 Evaluate `nano`, `lf`, and `nnn` against the pinned riscv64 package set, record desktop IDs, package derivations, and whether each builds without adding an unsupported toolchain; verify with the narrow Nix evaluation command and saved JSON evidence.
- [ ] 1.2 Measure each candidate's NAR/closure delta against the current shell image and record startup and memory observations; verify with the named derivation closure commands and an evidence file that labels estimates versus measured values.
- [ ] 1.3 Select zero, one, or both candidates from the recorded results and write the rejection reason for every omitted candidate; verify the selected set is no larger than the approved bounded list and does not add a network installer or general desktop suite.

## 2. Desktop entries and Help surface

- [ ] 2.1 Add selected terminal applications as minimal visible desktop entries using `Terminal=true` and the existing Foot bridge; verify `k230-desktop-catalog list` discovers each ID and `k230-desktop-catalog launch ID` preserves the configured terminal environment.
- [ ] 2.2 Add a built-in Help card/page to the existing portrait launcher with concise pages for Apps, Keyboard, Windows/Home, System, Terminal, Monitor, Back, and Previous/Next; verify the host launcher tests cover page bounds, Back, and empty-catalog behavior.
- [ ] 2.3 Keep Help and the existing built-ins available when no optional candidate is selected or a candidate launch fails; verify an injected launch-error workflow leaves a usable Back control.

## 3. Host and image validation

- [ ] 3.1 Build the launcher and each selected package separately for the pinned target and record the exact derivation outputs; verify with the narrow package build commands before attempting an image build.
- [ ] 3.2 Build or evaluate the shell image with the selected set and compare startup/closure evidence against the recorded baseline; verify the report distinguishes host/package proof from QEMU or hardware proof.
- [ ] 3.3 Boot the resulting image and confirm startup, catalog discovery, Help rendering, and candidate launch/return using injected input; verify with the existing shell evidence workflow and label physical-finger, reboot, and final-glass checks as unverified until separately observed.

## 4. Review and integration

- [ ] 4.1 Capture portrait screenshots and a concise evidence record for Help pages and each selected app, including desktop ID, package source, closure delta, startup result, and injected touch result; verify all links and claims in the evidence README.
- [ ] 4.2 Run the relevant shell tests and validate the OpenSpec change; verify with `pytest` for the launcher/catalog tests and `openspec validate --change add-offline-shell-apps-and-help --strict`.
