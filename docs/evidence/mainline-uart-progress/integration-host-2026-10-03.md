# UART progress integration: host checks, physical trial pending

Coordinator worktree `/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, integration base `f05fc34e2e54ed928f00712cecb93077bf1d130a`.
Reviewed source commit `deded9a4d9585110af7a437ebb9fc6e7fb54dd5e` is integrated
as `ff7397da`; reviewed controller `f92acae8e7b2f2fc2e2c9cf78963475c76902ba7`
as `27d7d9e8`. Source/API review, object inspection and the new controller's
exact arguments, one-stimulus and unknown-no-input policies were reviewed.
No board/UART/camera/build-slot reservation was held for these host checks.

Owned integration paths: the two reviewed increments, this note, and
`.github/workflows/spec-site.yml` adding the two focused source/controller gates.
Existing default modes remain covered by the existing trial suites.

```sh
TMPDIR="$HOME/tmp" python3 tests/test_mainline_uart_progress.py
TMPDIR="$HOME/tmp" python3 tests/test_mainline_uart_progress_controller.py
TMPDIR="$HOME/tmp" python3 -m unittest discover -s tests -p 'test_mainline_drm*trial.py'
TMPDIR="$HOME/tmp" python3 -m unittest discover -s tests -p 'test_mainline_shell_pid1_comparison.py'
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

All checks passed: 12 actual-code native fixtures (0.098s), 20 capture/config
fixtures (0.374s), 214 existing trial tests (25.354s), 14 shell comparison tests
(1.195s), strict OpenSpec and whitespace. Native and mocked wire/config tests
are host evidence, not firmware execution, UART reception, recovery or glass
acceptance. CI now invokes the two new focused commands.

Source/configuration task 5f.1 is complete. The separately compiled three
RISC-V objects use installed base headers plus the explicit new config overlay;
5f.2 remains open for exact new configured-header compilation. Complete matching
kernel/dev/system/bundle, real bundle/config qualification, physical progress
and protected recovery remain separate gates. Task 5f.4 therefore stays open,
even though the controller and its host tests landed. Usable mainline root,
panel/glass and task 5b.5 remain UNVERIFIED.

The normal board was independently restored after the earlier Bash comparison;
see [the physical recovery packet](../mainline-system-trial/shell-pid1-physical-2026-10-03/operator-reset-recovery.json).
That manual reset is not recovery proof for the future reporter trial.
Published revision/CI inspection is coordinator follow-up after this commit.
