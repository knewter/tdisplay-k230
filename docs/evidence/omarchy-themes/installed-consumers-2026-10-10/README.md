# Deploy the completed theme consumers — 2026-10-10

Worktree `/home/jadams/tmp/k230-theme-install-2026-10-10`, branch
`deploy/themes-2026-10-10`, base/source `ddbe7204c5a64869fcb512c29fb1ef6ec6930095`.
Owned paths: the userspace-update authorization branch in
`tools/coherent-shell-board-install.py`, its host tests, and this deployment
record; the archived theme's status/evidence references will be reconciled
when installation is actually observed. The exclusive build lock protects the
matching bundle construction; the board/serial lock protects each board action.

The operator asked to continue after the completed theme parent was archived
and the new packages were identified as not yet installed. Their existing
instruction explicitly waived additional proof collection. The installer now
keeps this authorization distinct from an operator real-finger report. The
new evidence class requires explicit deployment/waiver flags, the authorized
source revision, exact candidate system/kernel/bundle/executable, and an
accepted baseline. It rejects claimed finger checks and any kernel/Image/initrd
change; the baseline profile and hashes must match the board's protected stage.
All original registration, candidate-running, init-selector, rollback-root,
protected-selector and atomic boot-file checks remain.

`python3 tests/test_coherent_shell_board_install.py` passed 13 host cases;
`python3 tests/test_coherent_shell_board_boot.py` passed five. The three new
cases distinguish authorization from physical observations and reject changed
boot code or a mismatched protected baseline. Logs are committed here. These
host checks do not claim installation. Build, staging and ordinary-boot results
are recorded below only after their actual operations finish.
