The optional transition source is implemented and host-checked. Hardware behavior remains **UNVERIFIED**. This packet does not prove userspace execution, ordinary root, panel/glass acceptance or recovery.

The base is `ea54f9e0` on branch `mainline-init-exec-transition-source`. The additive `kernelMainlineInitExecTransition`, its dev output, `k230-mainline-init-exec-transition` system and matching trial bundle use the unchanged parent config and artifact parameters. No gate is baked into those parameters. `source-build.json` records the actual source-only build, and `source-hashes.json` pins the four realized files. Its derivation layers exactly one transition patch over the retained exec-return source `dsgrv7744lzh418z22gb865c0j09g1qs`.

Both runtime gates require exact value `1`. Only selected ramdisk exec success in PID1 arms the witnesses. The parent's `K230_INIT_EXEC_RETURN_V1 ret=%d` call and original returns/fallbacks remain. Ordinary flags and helpers survive `free_initmem`; the setup function alone is init-only. Each witness consumes its one-shot before one ordinary INFO call:

- `K230_INIT_EXEC_TRANSITION_V1 point=kernel-init-return` after `fn(fn_arg)` returns and before `syscall_exit_to_user_mode` in the RISC-V kernel-thread return path.
- `K230_INIT_EXEC_TRANSITION_V1 point=first-user-ecall` inside the successful user-entry helper branch, before syscall-number validation/dispatch.

The latter is the first eligible observed PID1 ECALL, not necessarily the first trap or completed syscall. Exact parent `include/linux/entry-common.h:185–208` guarantees enabled interrupts and instrumentable context after that entry helper. No output is inserted after exit-to-user, where interrupts are disabled and context tracking has entered USER (`entry-common.h:342–345`, `irq-entry-common.h:275`). No assembly, sret, exit work, syscall result, timer/IRQ/TTY/MMIO policy or init executable changes.

A visible witness does not prove its own output call returned. A later ECALL witness establishes user instruction execution and kernel entry setup; it does not establish dispatch completion, loader completion, constructors or systemd main. Missing earlier output remains incomplete/unknown without negating an independent valid later fact. Printk can still block or perturb the run; there is no forced output, fallback or retry.

Commands run from this worktree:

```sh
TMPDIR="$HOME/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -B tests/test_mainline_init_exec_transition_source.py
TMPDIR="$HOME/tmp" K230_TRANSITION_FORCE_FIXTURE=1 PYTHONDONTWRITEBYTECODE=1 python3 -B tests/test_mainline_init_exec_transition_source.py
nix-instantiate --parse nix/kernel-mainline-init-exec-transition.nix
nix-instantiate --parse flake.nix
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --cached --check
```

Each native run passed all 10 tests. The actual run applies the patch with GNU `--fuzz=0` to realized parent source and executes the extracted patched definitions, selected caller and architecture functions. The CI run uses explicitly labeled parent excerpts at their original lines; it is a semantic fixture, not a full source realization. Tests cover exact gates, non-PID1, unsuccessful exec, absent arm, entry-work/user-mode rejection, invalid syscall, output failure/reentrant callbacks, one-shot cap and unchanged original architecture bodies apart from the new calls.

`object-result.json` records the exact locked GCC 15.3 RISC-V `W=1` command and successful compilation of all three objects against a private writable copy of retained parent `9dd` dev headers/config. `object-compile.log` contains no compiler warning. `object-symbols.txt` shows ordinary `.sbss` flags and `.text` helpers, init-only setup and the expected architecture references. The full readelf/log digests are retained in the receipt. A read-only scratch-root failure stopped before compilation; it was retried in fresh writable scratch, without changing source or configuration. Initial native extraction and evaluation harness corrections are recorded separately in `result.json`.

All prior package derivation identities are being compared against the actual full base attribute set; that read-only evaluation remains PENDING at this checkpoint, not a completed identity proof. Its receipt will follow separately.

The build lock is released. Full matching kernel/dev/system/bundle, actual new-header objects and controller/artifact qualification remain separate coordinator gates. Retain those outputs with registered GC roots. Only after those gates and NEW protected normal recovery may the coordinator stage one guarded 180-second capture. Witnesses grant no candidate input authority; unknown readiness sends no further input or reboot. Task 5b.5 stays open.
