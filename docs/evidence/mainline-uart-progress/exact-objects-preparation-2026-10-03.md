# Exact selected-header object proof preparation

Evidence class: source preparation, isolated config-validator fixtures and
read-only Nix evaluation. Actual exact-header object compilation and inspection
are **UNVERIFIED**; task5f.2 remains unchecked. This note adds no physical claim.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress`, branch
`mainline-uart-progress`, base `7538ec5894703da21b15e777f8ea87f9ed4054b9`.
Owned: separate exact-object recipe, additive flake output, task5f.2 proof command
and this preparation/selection receipt. No build or board/UART/camera access;
the coordinator holds the separate matching full-build slot.

`kernelMainlineUartProgressExactObjects` copies the actual selected reporter
kernel's `dev/lib/modules/7.3.0-rc5/build` headers and installed `.config` into a
writable local build directory, compiling the same three patched translation
units with the matching `dev/.../source` and cross GCC. No CONFIG define is
forced and no kernel/module link is requested. Before compilation it requires
exactly one `CONFIG_K230_UART_PROGRESS=y` assignment and the corresponding
single `#define CONFIG_K230_UART_PROGRESS 1` generated-header definition.
It retains both actual config/header files and requires them to remain unchanged
through the object compile. Logs, ELF inspection, source/dev paths and hashes
are exported for coordinator review. A failed compile prints the retained log.

The existing preliminary object recipe is byte-for-byte unchanged (SHA-256
`647a609274c3c909ca65683230b6d21c1b23abe2cd2e75612d116bf0ec178340`).
Its installed-base-plus-explicit-overlay proof remains the separately qualified
[source/object evidence](source-object-host-2026-10-03.md); it is not relabeled
as exact new-header proof.

Read-only evaluation completed exit0:

```sh
nix eval --offline --no-write-lock-file --json --impure --expr \
  'let f = builtins.getFlake "/home/jadams/tmp/k230-mainline-uart-progress"; p = f.packages.x86_64-linux; old = builtins.fromJSON (builtins.readFile /home/jadams/tmp/k230-mainline-uart-progress/docs/evidence/mainline-uart-progress/wiring-identities.json); in assert p.kernelMainlineUartProgress.drvPath == old.preservedKernel; assert p.kernelMainlineUartProgressObjects.drvPath == old.preservedObjects; { kernel = p.kernelMainlineUartProgress.drvPath; preliminary = p.kernelMainlineUartProgressObjects.drvPath; exact = p.kernelMainlineUartProgressExactObjects.drvPath; dev = p.kernelMainlineUartProgress.dev.outPath; }'
nix-instantiate --parse nix/kernel-mainline-uart-progress-exact-objects.nix
nix-instantiate --parse flake.nix
python3 tests/test_mainline_uart_progress.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

[Selection receipt](exact-object-selection.json) records the evaluated exact
object derivation `gwx7li1qqrii4183pbs8pcn4fvg2qidc`, selected `a3r0fw…` dev output,
and unchanged kernel/preliminary object identities. Evaluation does not realize
those dependencies. Read-only `nix derivation show` of this exact object
confirmed its actual build command selects that dev build/source and contains
no `-DCONFIG_K230_UART_PROGRESS`. The only flake modification adds the new output;
no existing output definition or source/config recipe changes.

The recipe's actual Python config guard was extracted and executed in temporary
fixture directories outside the repository: valid y/config-header pair passes;
missing config, disabled config, duplicate config, missing header and wrong
header each fail. All six fixtures passed. The unchanged twelve actual-code
source tests passed (0.403s); parse, strict and whitespace checks passed.
These are fixtures/evaluation, not RISC-V compilation or board execution.

Coordinator proof command after matching kernel/dev realization:

```sh
nix build .#kernelMainlineUartProgressExactObjects --no-link --print-out-paths
```

Review the returned compile log, actual installed config/autoconf and hashes,
source/dev paths and the three objects' ELF layout/lifetimes before ticking5f.2.
Full matching artifact inspection and every physical/recovery gate remain
separate; no UART, Bash reception, root or automatic-return result follows from
this preparation.
