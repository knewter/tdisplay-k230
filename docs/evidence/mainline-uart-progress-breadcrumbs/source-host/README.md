# Worker-only breadcrumbs: source and native fixture proof

Evidence class: actual patched C native fixtures, pinned-source patch/API
inspection and read-only Nix evaluation. New source realization, matching
full kernel/system/bundle/dev build, actual new-configured RISC-V object
layout and every physical breadcrumb/receipt/return result are **UNVERIFIED**.
Task 5b.5 remains open. No full build or board/UART/camera action was performed.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs`, branch
`mainline-uart-progress-breadcrumbs`, base `8e66e299`. Owned: new layered
recipe/patch, additive flake definitions, new native tests, this source-host
proof and task 5g.1–3 notes only. No build-slot/hardware reservation.

The new recipe layers its reporter-only patch over the unchanged optional
UART-progress source. The original source/recipe, cached 8250 getter, timer
getter, Kconfig, six sample records/delays/stop checks and every previously
selected output remain unchanged. Matching optional system and standard trial
collector inherit the original serial-only ordinary artifact parameters, with
both original trace tokens and no new runtime flags. A separate ExactObjects
attribute reuses the existing exact selected-dev recipe; it has not been built.

`patch --batch --fuzz=0 -p1` against immutable base
`/nix/store/4av3w0kigacwah6w04zfpnky4gsh0k59-linux-mainline-k230-uart-progress-src`
passed. Its reporter was first byte-compared with the original repository C.
Applied `drivers/soc/canaan/k230-uart-progress.c` SHA-256:
`7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22`.
The pinned `include/linux/build_bug.h:79` declares the added static_assert API.
No API or kernel pin update is introduced.

Exact emitted bytes, each from a distinct aligned64 ordinary static const
array, with literal length excluding NUL and compile-time sizeof<=64:

```text
\nK230_UPB1 point=worker-entry\n
\nK230_UPB1 point=first-post-sleep\n
```

Only exact new `k230.uart_progress_breadcrumbs=1`, existing
`k230.uart_progress=1`, CONFIG_RISCV_SBI and DBCN availability permit direct
breadcrumbs. Absent/bare/invalid new flags preserve the original six-sample
behavior. Entry is sample0 after its first stop check/before first sleep;
post-sleep is after that sleep and second stop check/before first snapshot.
At most two single attempts are added to six original writes. No IRQ, TTY,
PID1, formatting, printk/emergency, priority/affinity or retry/fallback is added.
The setup function alone has init lifetime; helper/flags/strings remain ordinary.
Actual matching RISC-V layout/page-bound proof still requires task 5g.3.

Native command:

```sh
python3 tests/test_mainline_uart_progress_breadcrumbs.py
python3 tests/test_mainline_uart_progress.py
```

Thirteen new fixtures pass (0.326s), compiling actual Gnu-patch-applied worker
C with isolated callbacks, plus all twelve original source/API fixtures.
The new tests compare absent-gate bytes/event order against the original actual
worker; assert exact two lines and event placement, paired/invalid/null gates,
extension absence, CONFIG-off helper behavior, stop boundaries and full/partial/
zero/error no-retry/eight-call bounds. Alignment/length checks execute on native
pointers. CONFIG-off is an isolated helper fixture: selected kernel Kconfig
requires SBI and is not represented as a valid board configuration. No native
callback is firmware, a hardware sleep, an IRQ or real UART reception.

Reproducible read-only evaluation:

```sh
nix eval --offline --no-write-lock-file --json --impure --expr \
  'import /home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs/docs/evidence/mainline-uart-progress-breadcrumbs/source-host/check-identities.nix { root = /home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs; }'
nix-instantiate --parse nix/kernel-mainline-uart-progress-breadcrumbs.nix
nix-instantiate --parse flake.nix
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

The expression checks every existing package drv, every exposed kernel source/
config drv, inherited structured config/parameters and matching selected
system kernel. It does not realize a derivation. Evaluation exited0: all 91 existing package
identities and ten exposed kernel source/config pairs remain equal; inherited
structured configuration/parameters and matching selected system kernel also
passed. [identities.json](identities.json) retains the evaluated paths and
source-layering receipt, distinct from built artifacts. Read-only
`nix derivation show /nix/store/j1sybrggrxciw73csgwb1wx25r9q89cn-linux-mainline-k230-uart-progress-breadcrumbs-src.drv`
shows env.src is the exact unchanged 4av3 source above and env.patches contains
only the new breadcrumb patch. Its evaluated output is
`/nix/store/k5a5zrhqy9ypr3mja1r50mdlcgi74i1f-linux-mainline-k230-uart-progress-breadcrumbs-src`;
it was not realized. New kernel/system/bundle/exact-object drv paths are in
the receipt; their matching build/configured-header/layout gates remain open.
Nix parsing, strict change validation, all 56 validations and whitespace checks passed. Independent source/API review approved.

A later point proves progress past an earlier call, not its full returned
write count. Entry alone does not prove firmware return or wakeup; post-sleep
proves the earlier call/sleep/stop checks passed but not snapshot/receipt.
Missing output remains unknown. Sleep/scheduling/firmware have no wall-clock
completion guarantee, and two new calls can perturb behavior. Controller mode,
full build/artifact inspection, exact target object proof, protected physical
one-stimulus capture and independent recovery belong to later tasks/root.

Cached start/handoff `python3 tools/work-status.py` scans both completed exit0.
Final repeated native runs: thirteen new tests passed (0.404s), twelve original
tests passed (0.189s); strict validation and Nix/whitespace checks passed again.
