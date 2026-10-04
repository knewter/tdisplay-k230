# Memory intervention source and native fixture proof

Evidence class: actual patch-applied C native fixtures, immutable source/API
inspection and pure Nix identity evaluation. Matching full kernel/system/bundle,
actual selected config/dev headers and RISC-V object/lifetime/layout remain
**UNVERIFIED**. Positive controller preparation, physical output/receipt/recovery
and task 5b.5 stay open. No full kernel build or board/UART/camera action occurred.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-memory`, branch
`mainline-uart-progress-memory`, base `a4d6958dddf9572320b63c96b4777c959424ece9`.
Owned: new Memory patch/recipe, additive flake family, native fixtures,
source-host evidence and only task 5i.1. Shared build lock used only for pure
identity evaluation, never derivation realization.

GNU `patch --batch --fuzz=0 -p1` applied the new zero-context patch to immutable
`/nix/store/wnvbxaiqgbhhajsajy5mlpn36zf8alga-linux-mainline-k230-uart-progress-post-sample-src/drivers/soc/canaan/k230-uart-progress.c`.
Parent worker SHA-256:
`aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b`.
Applied Memory worker SHA-256:
`307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`.
Portable native fixtures reconstruct the same parent from existing repository
patches, then apply only the new Memory layer. Existing patches/recipes,
getter/timer sources, configuration and artifact parameters are untouched.

Only exact `k230.uart_progress_memory=1`, base progress opt-in, CONFIG_RISCV_SBI
and actual DBCN availability enable the intervention. It suppresses every worker
output, including numeric and both earlier point families, while retaining six
5000ms sleeps, cached snapshots, stop checks, normal priority and termination.
The typed controller rejects simultaneous Breadcrumbs/PostSample selectors;
the source suppresses their worker writes even if those flags are present.
Absent/bare/invalid Memory gate retains inherited behavior and creates no
observer. No IRQ/PID1/TTY/MMIO/clock/console-policy or scheduler-policy change is added.
The added normal-priority observer changes the workload/timing; this remains an
intervention rather than a passive observation of identical execution.

A separate ordinary atomic state packs stage bits[2:0], current index[5:3] and
completed-snapshot bitmap[11:6]. Each publication is one `atomic_set_release`;
observer uses ONE `atomic_read_acquire`, with no retry/seqcount loop. The last
completed index is derived from that single bitmap in a six-iteration bounded
loop. State/helpers/flags/completion/buffer have ordinary lifetimes; setup alone
uses init lifetime. The new public summary format, with lowercase two-digit hex:

```text
\nK230_UMP1 s=%u n=%u m=%02x l=%u w=%u\n
```

| Stage s | Meaning | n and m |
| --- | --- | --- |
| 0 | initialized | n6, m00 |
| 1 | before sleep | n0..5, m=(1<<n)-1 |
| 2 | returned sleep and stop check | n0..5, m=(1<<n)-1 |
| 3 | snapshot and cached observations completed | n0..5, m=(1<<(n+1))-1 |
| 4 | all six completed | n5, m3f |
| 5 | stopped at an existing check | n0..5, m=(1<<n)-1 |
| 6 | worker creation failed | n6, m00 |

Allowed masks are 00/01/03/07/0f/1f/3f. l is the highest completed index or6
when mask00. w1 means completion wait returned nonzero and requires terminal
stage4/5/6; w0 means timeout returned zero and may contain a terminal stage if
publication races timeout. Receipt and recovery are separate facts.

The observer is created before the worker, waits once with
`wait_for_completion_timeout(..., msecs_to_jiffies(45000))`, then copies state
and attempts ONE final bounded-size DBCN write. Its ordinary 256-byte buffer has
256-byte alignment; length must be positive and less than sizeof(buffer).
Observer creation failure returns the known init error without starting a
worker/output. Worker creation failure publishes stage6 then completes the
wait. Worker termination publishes its terminal state before completion.
The selected source declares the atomic acquire/release API in
`include/linux/atomic/atomic-instrumented.h` and completion/wait API in
`include/linux/completion.h`; exact matching target object proof remains open.

```sh
python3 tests/test_mainline_uart_progress_memory.py
python3 tests/test_mainline_uart_progress_post_sample.py
python3 tests/test_mainline_uart_progress_breadcrumbs.py
python3 tests/test_mainline_uart_progress.py
```

Thirteen new fixtures passed (0.420s), plus prior 15/13/12 fixtures
(0.318s/0.201s/0.068s). New tests compile actual patch-applied C with GCC
`-std=gnu11 -Wall -Wextra -Werror` and isolated callbacks. They execute gates,
all twelve stop boundaries, creation failures, completion/timeout/terminal
races, exact coherent publication values and one acquire read, unchanged
absent-mode bytes/events and one full/partial/zero/error output attempt.
Callback timing/atomics/completion are isolated native models, not actual
concurrent Linux scheduling, kernel memory-ordering or firmware progress proof.
CONFIG-off is an isolated fixture, not a valid selected board kernel. Callback
argument capture does not establish delivered UART bytes. Parent-only unused
new fixture stubs are exempted from unused-function warnings.

```sh
flock -n /tmp/k230-nix-build.lock nix eval --offline --no-write-lock-file \
  --json --impure --expr \
  'import /home/jadams/tmp/k230-mainline-uart-progress-memory/docs/evidence/mainline-uart-progress-memory/source-host/check-identities.nix { root = /home/jadams/tmp/k230-mainline-uart-progress-memory; }'
nix eval --offline --no-write-lock-file --raw \
  .#packages.x86_64-linux.toplevel-mainline-uart-progress-memory.drvPath
nix derivation show /nix/store/h485sr26ipaabfmn29x5qj38qxxzp3x1-linux-mainline-k230-uart-progress-memory-src.drv
nix-instantiate --parse nix/kernel-mainline-uart-progress-memory.nix
nix-instantiate --parse flake.nix
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

Pure identity evaluation passed all 99 pre-existing package drv identities
and 12 exposed kernel source/config pairs, inherited structured config/parameters
and selected kernel assertion against the full declared base. The source
derivation layers exactly over immutable PostSample source with only the new
Memory patch. [Receipt](identities.json) records these evaluated selections,
not realized matching artifacts. An initial evaluation rejected an abbreviated
Git base hash before evaluating any identity. The successful expression initially
printed its parent system in an output-only field; that field now uses the
selected config toplevel and the Memory system was separately evaluated.
Parse/strict/all validation (56 passed) and whitespace checks pass. Both cached
start/handoff scans completed0, and the pure-evaluation lock is released.
Actual matching full/build-object/controller/hardware tasks remain open.

This is an intervention removing repeated firmware TX from the measured
worker. A received summary proves recorded progress BEFORE its final output
call; it does not prove that call returned or diagnose firmware/IRQ/RX/root.
Finite kernel wait is not an absolute boot or firmware wall-clock deadline.
Missing summary leaves worker, observer, timer/scheduler and output unknown;
an M-mode stall can prevent the S-mode observer from executing. Root owns
matching build, positive preparation, physical use and fresh normal recovery.
