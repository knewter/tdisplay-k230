## 1. Mainline boot bundle (host)

- [x] 1.1 Add `kernelMainlineDrmShellBootFiles` (coherent boot-files layout, mainline DTB presented as `k230-tdisplay.dtb`) and run the existing host inspection on it. Host proof: `nix build .#kernelMainlineDrmShellBootFiles` plus `python3 tools/coherent-shell-boot-inspect.py` on the result.
      Bundle rqx0jajd…: [host inspection](../../../../docs/evidence/mainline-default-boot/host-inspection.json) PASS after allowing the `k230-mainline-drm-shell` configuration name (tests added). Vendor `coherentShellBootFiles` derivation unchanged.

## 2. Trial and qualification (board)

- [x] 2.1 Stage the bundle with `tools/coherent-shell-board-stage.py prepare`, adapting tooling only where it pins vendor-only facts (with tests). Hardware proof: stage `check` passes on the board.
      On-board prepare+check READY; [staged state](../../../../docs/evidence/mainline-default-boot/staged-state.json). Stage tool now accepts an imported, registered candidate (3 tests).
- [x] 2.2 Trial-boot the staged bundle with `tools/coherent-shell-board-boot.py` and complete its touch qualification (operator present). Hardware proof: qualification record.
      Trial PASS (7.3.0-rc5, three services). [Qualification](../../../../docs/evidence/mainline-default-boot/qualification.json) rests on the operator's earlier on-glass session with the same system/kernel/shell, re-affirmed for install; the routes were not re-touched on this trial boot ID (see [evidence](../../../../docs/evidence/mainline-default-boot/README.md)).

## 3. Install and rollback drill (board)

- [x] 3.1 Install with `tools/coherent-shell-board-install.py install`; reboot; verify 7.3.0-rc5, installed system booted, shell services active, no failed units; also verify one reset-button power-on. Hardware proof: install journal and post-boot serial checks.
      Install PASS and ordinary reboot verified (7.3.0-rc5, `running`, no failed units, native Home). Reset-button power-on 2026-10-08: 7.3.0-rc5, mainline system/profile, three services active, `running`, no failed units ([record](../../../../docs/evidence/mainline-default-boot/reset-button-postboot.json)).
- [x] 3.2 Rollback drill: `install.py rollback`, reboot, verify vendor 6.6 with byte-identical backups; reinstall mainline and verify again. Hardware proof: rollback-result.json and both post-boot checks.
      Rollback PASS, ordinary boot 6.6.36/`p1a1hz…`; reinstall PASS, ordinary boot 7.3.0-rc5 ([evidence](../../../../docs/evidence/mainline-default-boot/README.md)).

## 4. Protected normal and publication

- [x] 4.1 Regenerate the trial tooling's normal baseline from the installed mainline system and update tests pinning `6.6.36`. Proof: affected tests pass.
      `NORMAL_BASELINE` → [postboot.json](../../../../docs/evidence/mainline-default-boot/postboot.json); normal system/uname read from it. Remaining `6.6.36` strings in tests are synthetic vendor banners (still valid rejection fixtures). Initrd-shell, system-trial, coherent boot/install/stage, pid1, debug and observer tests pass.
- [x] 4.2 Review, land, push, verify CI and the published page. Proof: `openspec validate the-board-boots-mainline-by-default --strict`, CI run id, page revision.
      Strict validate passes; landed 538bcaeb; CI/Pages run 37647787229 build+deploy success; https://knewter.github.io/tdisplay-k230/work/ serves revision 538bcaeb8977.
