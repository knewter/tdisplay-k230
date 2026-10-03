# Optional UART-progress system and bundle preparation

Evidence class: read-only Nix evaluation and source inspection. Complete matching
kernel/system/initrd/bundle build, exact new configured-header compilation,
artifact inspection, physical records and protected automatic return remain
**UNVERIFIED**. Task5f.3 and task5b.5 remain open.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress`, branch
`mainline-uart-progress`; this additive increment follows source/object commit
`deded9a4d9585110af7a437ebb9fc6e7fb54dd5e`, itself based on `a5629a3d`.
Owned paths: additive `flake.nix` definitions and this wiring evidence/proof.
No source/protocol/controller/default change, board/UART/camera or build slot.

The new `k230-mainline-uart-progress` configuration extends the original SBI-only
system, replacing its kernel with the reviewed optional reporter kernel.
`toplevel-mainline-uart-progress` exposes its system and
`kernelMainlineUartProgressTrialBootFiles` uses the existing `mainline-drm-trial.nix`
collector with that exact configuration/kernel and unchanged DRM hardware DT.
The collector generates its sole `init=SELECTED_SYSTEM/init`, matching initrd
wrapper, closure inventory and checksum list as before; these actual artifacts
still require the coordinator's build and inspection.

Kernel parameters are exactly equal to the existing SBI-only configuration:
serial console only, ordinary init, the two original trace enabling tokens,
and existing root/log parameters. No `k230.uart_progress=1`, rdinit or async
comparison flag is baked into the artifact. The reviewed controller qualifies
those original arguments, removes both trace tokens and adds the sole volatile
reporter gate plus `initramfs_async=0`, the three qualified initrd controls and
`rdinit=/bin/sh`. The kernel worker and frozen public record protocol are unchanged.

Reproducible evaluation, without realization:

```sh
nix eval --offline --no-write-lock-file --json --impure --expr \
  'import /home/jadams/tmp/k230-mainline-uart-progress/docs/evidence/mainline-uart-progress/check-wiring.nix { root = /home/jadams/tmp/k230-mainline-uart-progress; }'
nix-instantiate --parse flake.nix
nix-instantiate --parse docs/evidence/mainline-uart-progress/check-wiring.nix
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Evaluation completed exit0; parse, strict and whitespace checks passed.
The expression asserts the original22 output identities and both new reviewed
kernel/object identities are unchanged, selected-system kernel equality, exact
inherited parameter equality, original trace-token uniqueness and no baked-in
reporter gate. It independently re-instantiates the existing collector to check
bundle recipe equality. [Evaluation receipt](wiring-identities.json) records the
selected derivations and params. This is evaluation, not artifact or board proof.

The coordinator owns the next complete build:

```sh
nix build .#kernelMainlineUartProgressTrialBootFiles --no-link --print-out-paths
python3 tools/mainline-drm-trial-inspect.py BUNDLE
```

Only after matching-build/controller review and fresh protected normal recovery
may the board operator perform task5f.5's explicit one-stimulus/passive capture.
No automatic recovery or UART reception is claimed by this preparation.
