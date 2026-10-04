# Post-sample source and native fixture proof

Evidence class: actual patch-applied C native fixtures, immutable source/API
inspection and pure Nix identity evaluation. Matching full kernel/system/bundle,
selected generated config/dev headers and target RISC-V object layout remain
**UNVERIFIED**, as do new physical records and recovery. Task 5b.5 stays open.
No full kernel build or board/UART/camera action was performed.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-post-sample`, branch
`mainline-uart-progress-post-sample`, base
`9248ffa445629ac3f0a87a73aa1f85a0695bba3d`. Owned: new source patch/recipe,
additive flake outputs, native fixtures, this source-host evidence and only
5h.1–3 notes. The shared lock is used only for pure evaluation; no derivation
is realized by this increment.

GNU `patch --batch --fuzz=0 -p1` applied the new zero-context patch to immutable
`/nix/store/k5a5zrhqy9ypr3mja1r50mdlcgi74i1f-linux-mainline-k230-uart-progress-breadcrumbs-src/drivers/soc/canaan/k230-uart-progress.c`.
Its reviewed baseline SHA-256 is
`7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22`.
Applied worker SHA-256:
`aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b`.
The new recipe layers over the unchanged Breadcrumbs recipe/source. Original
reporter/Breadcrumbs recipes and patches, cached getter/timer, config and
artifact parameters are untouched. New named kernel/system/trial/ExactObjects
outputs reuse the original generation/inspection recipes.

Two distinct ordinary static const arrays have 64-byte alignment, sizeof<=64 including
NUL, with one literal-length write excluding NUL. Only setup has init lifetime;
helper/flag/buffers have ordinary lifetime. Actual RISC-V alignment/page/lifetime
proof awaits the matching selected dev in task 5h.3.

```text
\nK230_UPP1 point=after-n1-write\n
\nK230_UPP1 point=third-post-sleep\n
```

The exact new `k230.uart_progress_post_sample=1` requires both existing exact
progress/Breadcrumbs gates, CONFIG_RISCV_SBI and DBCN availability. After-n1-write
occurs only sample1 immediately after the original numeric SBI call returns;
third-post-sleep occurs only sample2 after unchanged sleep/stop check and before
snapshot. Six numeric samples, two previous breadcrumbs, stops, delays, getter
behavior, format and normal priority remain unchanged. Two single attempts add
no formatting, retry/fallback, printk/emergency, IRQ/TTY/PID1 or clock/scheduler
policy. Maximum is ten attempts if calls return. No new SBI or static_assert API
is introduced; the current source's SBI write implementation is unchanged.

```sh
python3 tests/test_mainline_uart_progress_post_sample.py
python3 tests/test_mainline_uart_progress_breadcrumbs.py
python3 tests/test_mainline_uart_progress.py
```

Fifteen new fixtures passed (0.335s), plus thirteen Breadcrumbs fixtures (0.573s)
and twelve original source/API fixtures (0.193s). New tests compile actual
repository patch-applied worker C with GCC `-std=gnu11 -Wall -Wextra -Werror`
and isolated callbacks. They compare absent-gate bytes/events against the
actual prior worker; execute exact/bare/invalid/null/prior/config/availability
gates, precise callback placement, stops and ten full/partial/zero/error
attempts without retries. Native pointer alignment and literal bounds are
checked. Modeled non-returning n1 and new-after callbacks use a C longjmp to
stop execution before later points; this is not firmware or scheduling proof.
CONFIG-off is an isolated helper fixture, not a valid selected board kernel.
Callbacks capture argument bytes, not delivered UART bytes.

Reproducible pure evaluation and narrow checks:

```sh
flock -n /tmp/k230-nix-build.lock nix eval --offline --no-write-lock-file \
  --json --impure --expr \
  'import /home/jadams/tmp/k230-mainline-uart-progress-post-sample/docs/evidence/mainline-uart-progress-post-sample/source-host/check-identities.nix { root = /home/jadams/tmp/k230-mainline-uart-progress-post-sample; }'
nix eval --offline --no-write-lock-file --raw \
  .#packages.x86_64-linux.toplevel-mainline-uart-progress-post-sample.drvPath
nix derivation show /nix/store/xdrlaz1619lvaz1chx3ag6627605ralw-linux-mainline-k230-uart-progress-post-sample-src.drv
nix-instantiate --parse nix/kernel-mainline-uart-progress-post-sample.nix
nix-instantiate --parse flake.nix
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

Pure evaluation passed equality for all 95 pre-existing package derivations
and 11 exposed kernel source/config pairs against the declared base. Assertions
also passed inherited structured config/parameters and selected system/kernel
equality. The source derivation has `env.src` exactly equal to the immutable
Breadcrumbs source above and only the new PostSample patch. The public-safe
[identity receipt](identities.json) records the evaluated paths; these are
derivations/output selections, not realized matching artifacts. The receipt
expression initially printed the parent system in its `system` field; that
field was corrected and the selected PostSample system was separately evaluated.
Parse, strict, all-change validation (56 passed) and whitespace checks pass.
Both cached start/handoff status scans completed with exit 0. Tasks 5h.2–3 remain
open until the named matching build/inspection and exact selected-header object
commands; the shared pure-evaluation lock was released.

Visible after-n1-write proves that prior numeric call returned, not its full
count or this new call's return. A later third point proves progress through
that call and third sleep/stop, not snapshot or n2. Missing output stays unknown;
finite attempt count is not a firmware/sleep wall-clock deadline. Root owns
matching builds, actual controller preparation and the protected one-stimulus
physical comparison/recovery; no production fix, RX delivery or usable root
is claimed here.
