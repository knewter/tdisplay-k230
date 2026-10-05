# Selected init exec-return probe — source and host checkpoint

Worktree `/home/jadams/tmp/k230-mainline-init-exec-return`, branch
`mainline-init-exec-return`, base `8557a21494a46d26e9df195e7d5a17fbeea6a6b1`.
This is source/native/object/evaluation proof. Full matching build, actual new
artifact qualification, output, userspace transition and ordinary acceptance
remain **UNVERIFIED**. No board/UART/camera operation occurred. Root owns the
planning checkboxes and physical evidence; task 5b.5 remains open.

The additive p2 child adds strict exact-value `k230.init_exec_return=1`, default
disabled. It emits at most one INFO line `K230_INIT_EXEC_RETURN_V1 ret=%d` only
after the selected ramdisk `run_init_process` returns, before the unchanged
success/error branch. Original fallback calls, return value, argv/env, init and
printk behavior remain unchanged. The runtime flag has ordinary `.sbss` lifetime:
`free_initmem` precedes its read. Only its setup function is init-only.
A zero value means successful exec setup, not user-mode transition, loader,
constructors or systemd main. A complete record cannot prove its own print call
returned. Missing/partial output is unknown; no forcing, retry or fallback.

The typed begin-only `--init-exec-return` requires the synchronous, marker-free
ordinary selectors and excludes all logging variants. It binds actual same-drv
kernel/dev/config, reviewed main.c and unique compiled Image setup/format before
opening UART. It checks original archived systemd/init/Bash/common-loader bytes;
Zstandard inspection requires host Python 3.14. Inherited aliases/instrumentation
and malformed/duplicate/stale/interleaved records fail closed. A received record
grants no input or recovery authority. Selected passive capture retains facts
on the 180s unknown outcome; further candidate input requires the existing fresh
login, exact args, one zero record and unchanged ordinary identity gates. Original
boot/wait/read/load/CRC/identity/recovery functions retain their AST bodies.

`python3 tests/test_mainline_init_exec_return.py`: **15 PASS**. Native GCC executes
the patch additions around the original selected-caller branch, covering exact
setup, default behavior, signed values, no ramdisk and regular state lifetime.
Pump/transport fixtures cover fresh exact args, complete/split/CRLF records,
malformed/duplicate/stale/echo/truncated output, same-chunk login/prompt, typed
saved resume, pre-open rejection, actual existing p2 rejection and unknown
post-boot zero input. The actual-p2 test skips if those host artifacts are absent;
this host executed it. The new real artifact positive gate is separate.

Previous info-kmsg **9**, info-console **10**, debug-console **13**, ordinary **36**
tests pass. Strict OpenSpec validation and diff checks pass. Evaluation proves
all **107** old package derivation identities unchanged and selected config and
artifact parameters equal to the parent. [Exact identities](identity-evaluation.json).
No runtime gate is baked into the bundle: the controller adds only the new token
while preserving the previous masks, async join, sole serial console and init.

Source realization:

```sh
flock /tmp/k230-nix-build.lock nix build --offline --no-write-lock-file --no-link --max-jobs 1 --cores 16 --print-out-paths .#kernelMainlineInitExecReturn.src
```

The immutable source is `dsgrv7744lzh418z22gb865c0j09g1qs`; main.c SHA is
`a21ac6a296d4cb3602f127d6270aa4026afe98e582e35d4957494b30c5f86499`.
An actual GCC 15.3 RISC-V `main.o`, `W=1`, passed using privately copied p2/24h
prepared headers and exact config `52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
No immutable header mutation or kernel link occurred. [Object receipt](result.json)
and [compile log](compile.log) retain hashes. Exact new headers/full link remain
a later actual-build proof.

Private scratch and full logs live under `~/tmp/k230-mainline-init-exec-return-host`.
An initial unbuilt draft used initdata; review corrected that before source
realization. Initial test development caught a syntax error and same-chunk login
framing; a resume fixture also bypassed the boot stream and was corrected to use
the real legacy readiness pump. These failed fixture runs were not hardware or
build successes. Final focused/regression results above supersede them.

After full matching outputs exist, run the separately reviewed read-only tool:

```sh
python3 tools/mainline-init-exec-return-qualify.py --bundle BUNDLE --dev DEV --normal-report PRIVATE_NORMAL --build-receipt PRIVATE_BUILD_RECEIPT
```

It creates a fresh protected host directory; no build, UART or live preflight.
Require actual source/Image/dev/config/archive/helper/DT/manifest/load/CRC proof
and document every dependency delta before a root-operated trial after NEW
protected recovery. Physical output/ordinary root/glass remain unverified.
