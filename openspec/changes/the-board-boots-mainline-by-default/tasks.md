## 1. Mainline boot bundle (host)

- [ ] 1.1 Add `kernelMainlineDrmShellBootFiles` (coherent boot-files layout, mainline DTB presented as `k230-tdisplay.dtb`) and run the existing host inspection on it. Host proof: `nix build .#kernelMainlineDrmShellBootFiles` plus `python3 tools/coherent-shell-boot-inspect.py` on the result.

## 2. Trial and qualification (board)

- [ ] 2.1 Stage the bundle with `tools/coherent-shell-board-stage.py prepare`, adapting tooling only where it pins vendor-only facts (with tests). Hardware proof: stage `check` passes on the board.
- [ ] 2.2 Trial-boot the staged bundle with `tools/coherent-shell-board-boot.py` and complete its touch qualification (operator present). Hardware proof: qualification record.

## 3. Install and rollback drill (board)

- [ ] 3.1 Install with `tools/coherent-shell-board-install.py install`; reboot; verify 7.3.0-rc5, installed system booted, shell services active, no failed units; also verify one reset-button power-on. Hardware proof: install journal and post-boot serial checks.
- [ ] 3.2 Rollback drill: `install.py rollback`, reboot, verify vendor 6.6 with byte-identical backups; reinstall mainline and verify again. Hardware proof: rollback-result.json and both post-boot checks.

## 4. Protected normal and publication

- [ ] 4.1 Regenerate the trial tooling's normal baseline from the installed mainline system and update tests pinning `6.6.36`. Proof: affected tests pass.
- [ ] 4.2 Review, land, push, verify CI and the published page. Proof: `openspec validate the-board-boots-mainline-by-default --strict`, CI run id, page revision.
