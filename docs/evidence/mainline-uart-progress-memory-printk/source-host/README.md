# MemoryPrintk source and native proof

Evidence class: layered source realization, native callback fixtures and pure Nix
evaluation. Full matching kernel/dev/system/bundle, selected-header target objects,
actual controller preparation, physical output and recovery remain **UNVERIFIED**.
Task 5b.5 remains open. No board/UART/camera or full kernel build was performed.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-memory-printk`, branch
`mainline-uart-progress-memory-printk`, base
`e2a02cb0015e027f10c7d3fbbacfe1534163a329`. Owned paths: additive layered patch,
recipe/flake variants, native test, this source evidence and only task 5l.1.
The coordinator owns review/integration/CI and the sole matching full build.

New exact setup gate `k230.uart_progress_memory_printk=1` selects one ordinary
`pr_info("\nK230_UMK1 s=%u n=%u m=%02x l=%u w=%u\n", ...)` in the existing observer.
The leading newline gives printk an initial empty message line before the
timestamp-prefixed UMK line, separating it from a possible Bash prompt. The
branch returns immediately, with no selected final explicit DBCN attempt,
retry, force flush, emergency interval or second channel. Existing Memory,
progress, CONFIG_RISCV_SBI and actual DBCN availability gates still control
observer creation. The new gate alone cannot create an observer. Absent/bare/
invalid values preserve the original observer and worker behavior.

The worker/init tail is byte-identical to the Memory parent. Six 5000ms sleeps,
cached snapshots/stop checks, packed release publications, completion, one
45-second wait and one acquire read are unchanged. New flag has ordinary data
lifetime; only its setup function is init-only. Observer and fixed format have
ordinary lifetimes. Field types are unsigned int; the existing masked fields
and bounded six-index loop keep output below 256 bytes. There is no new MMIO,
TTY/IRQ access, scheduling policy, lock, firmware or console-driver change.
Registered Linux console ownership performs any normal backend operations.

## Reproducible native and source checks

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=$HOME/tmp \
  python3 -B tests/test_mainline_uart_progress_memory_printk.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR=$HOME/tmp \
  python3 -B -m unittest discover -s tests -p 'test_mainline_uart_progress*.py'
nix-instantiate --parse flake.nix >/dev/null
nix-instantiate --parse nix/kernel-mainline-uart-progress-memory-printk.nix >/dev/null
nix eval --offline --impure --json --expr \
  'import ./docs/evidence/mainline-uart-progress-memory-printk/source-host/check-identities.nix { root = ./.; }' \
  > docs/evidence/mainline-uart-progress-memory-printk/source-host/identities.json
nix build .#kernelMainlineUartProgressMemoryPrintk.src --offline --dry-run --no-link --print-out-paths
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressMemoryPrintk.src --offline --no-link --print-out-paths
```

The 10 focused tests compile the actual complete patch chain using native GCC
with `-Wall -Wextra -Werror`, replacing kernel interfaces only with isolated
callbacks. They execute selected and original Memory code, asserting exactly
one printk/zero selected SBI calls, silent worker and unchanged delays/snapshots,
publications/events, all stop boundaries, initialization failure, timeout and
terminal-publication race. They test base/Memory/new/config/extension gates,
exact setup parsing, invalid-after-valid clearing and ignored printk return
without retry/fallback. The 170-test discovery passed before the leading-newline refinement; corrected
focused tests passed again afterward. Discovery includes prior source
and progress-controller fixtures. These are host fixtures, not concurrent
kernel execution or UART reception.

The initial evaluation invocation used an eight-character base revision in a
Git flake URL and failed before evaluating identity assertions. The checked-in
expression corrects this to the full base revision. No source or artifact failed.
The initial no-leading-newline source/evaluation runs were deliberately cancelled
when review identified a possible physical-line concatenation after the Bash
prompt. The one-call format was corrected to begin with a newline; fresh
native/evaluation/source receipts below refer only to that corrected patch.
Only the corrected new source derivation was selected by offline dry run and realized
under a nonblocking shared lock. No kernel build, fetch or bootstrap was selected.
Source path, layered parent, patch, applied worker SHA and identity counts are
recorded in [proof.json](proof.json); evaluated paths are in
[identities.json](identities.json). The shared lock is released after source
realization. All 103 prior package drv identities and 13 exposed kernel source/config
pairs matched the full base. New system selects the new kernel, preserves exact
parent boot parameters and structured kernel configuration. Existing outputs,
including Memory, remain unchanged.

| New evaluated output (not a full build claim) | Identity |
| --- | --- |
| kernel | `/nix/store/fdjxx6cggxp2ffhsf7lwmz7mndd2588v-linux-riscv64-unknown-linux-gnu-7.3.0-rc5.drv` |
| source | `/nix/store/1pn3icn3crv39rlrmqwari98ja13qj1s-linux-mainline-k230-uart-progress-memory-printk-src.drv` |
| config | `/nix/store/342hsxcdyaf1qw8d5rd2y29zf4sp3a90-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5.drv` |
| dev | `/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| system | `/nix/store/cjnl8m4w2q2f8jx8j64h52rgzbazx7km-nixos-system-nixos-26.11.20260919.20b1ddd.drv` |
| bundle | `/nix/store/lf61l828xhx31y9csvrxsdk21z42b4kb-k230-mainline-drm-trial-boot-files.drv` |
| exactObjects | `/nix/store/rg0ngd72rmxmccx0542wvarsbp8cjwlw-k230-mainline-uart-progress-exact-objects.drv` |


## Limits and next gates

Existing selected Memory config and source ground timestamp framing:
PRINTK/PRINTK_TIME/8250 console/DW are built in; PRINTK_CALLER is disabled.
`kernel/printk/printk.c:1355–1394` prints six-decimal time and adds a caller field
only under PRINTK_CALLER. PRINTK_EXECUTION_CTX records metadata without forcing
a kthread prefix. New actual installed configuration and linked Image must be
inspected after the coordinator's full build; pure configuration equality is
not a replacement for that proof. The separately typed controller must retain
fresh received arguments/Linux ttyS0 backend markers, zero input, strict new
namespace and independent protected recovery; combined nohlt is excluded.

A received UMK record would show progress through observer snapshot/formatting
and changed Linux output, not that printk returned or that DBCN caused prior
silence. Console ownership/IER handling, nbcon scheduling and possible waits
are new output-path dependencies. The kernel wait/call count is not a wall-clock
console-return guarantee. Missing output leaves worker/observer/timeouts/
scheduling/output unknown. RX, ordinary root and glass acceptance remain separate.
