# Selected init exec-return — actual full and host qualification

Worktree `/home/jadams/tmp/k230-mainline-init-exec-return`, branch
`mainline-init-exec-return`, base `8557a21494a46d26e9df195e7d5a17fbeea6a6b1`.
The kernel and matching bundle build used frozen source commit `b5bedcb8`.
Controller correction `67d40217` removed duplicate helper definitions without
changing their established bodies, kernel source, config or Nix identities.
The executed qualifier correction is `d361f364`; both code corrections were
reviewed. This packet proves actual host build and artifact preparation only.
No UART, board, camera, live preflight or deployment operation occurred.

[Full build receipt](build-result.json) records return **0** for the sequential
kernel/dev (1,415.33 seconds) and bundle (110.68 seconds), completed
2026-10-05 05:03:16 UTC under the exclusive build lock. Commands:

```sh
flock /tmp/k230-nix-build.lock nix build --no-write-lock-file --no-link --max-jobs 1 --cores 16 --print-out-paths .#kernelMainlineInitExecReturn .#kernelMainlineInitExecReturn.dev
flock /tmp/k230-nix-build.lock nix build --no-write-lock-file --no-link --max-jobs 1 --cores 16 --print-out-paths .#kernelMainlineInitExecReturnTrialBootFiles
```

Actual outputs are kernel `wdrzkb9idb4pl88ws1b7y7vx0j79840l`, dev
`9ddh3qgnq1sj3ibqvd9124w4bfij2y6w`, system
`gi850b5xn2s398grgfw7xlbwdf1n5cbf`, and bundle
`5f2j4y8hy9cclbqjx4nshhxi4jiwz7iq`. The immutable selected source is
`dsgrv7744lzh418z22gb865c0j09g1qs`, main.c SHA
`a21ac6a296d4cb3602f127d6270aa4026afe98e582e35d4957494b30c5f86499`.
All 107 original package identities were unchanged in the
[earlier evaluation](../host/identity-evaluation.json).

The first real full attempt failed in offline mode because a bootstrap
prerequisite was unavailable. [Its receipt](offline-attempt-result.json) remains
separate. Removing only `--offline` allowed the exact pinned dependency to be
substituted and the build to complete. An earlier nonpersistent launcher did
not complete a build. [Run history](run-history.json) retains these failures,
commands and private log hashes; a failure was not overwritten as success.

The actual new dev config is byte-identical to p2/24h, SHA
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
A fresh private copy of these new prepared headers compiled the actual patched
main.c with GCC 15.3 for RISC-V, `W=1`: **PASS** in 4.46 seconds.
[Object command/receipt](new-header-object.json) and [compile log](new-header-compile.log)
record the exact paths and hashes. Readelf verifies ELF64 little-endian RISC-V,
one-byte runtime flag in ordinary `.sbss`, and setup function in `.init.text`.
Only the private copy was writable; immutable headers were not changed.
The complete linked kernel build is a separate proof from this object check.

The [executed host command](qualification-command.json) returned **0** at
2026-10-05 05:10:02 UTC, using the successful full receipt and a protected normal
report. That report is an historical host anchor; root's independent fresh
normal recovery is not performed or claimed by this qualifier. Host Python 3.14
was used for actual Zstandard initrd inspection. The executable tool is
[mainline-init-exec-return-qualify.py](../../../../tools/mainline-init-exec-return-qualify.py).

[Positive receipt](positive-host-result.json) binds actual same-derivation
kernel/dev/config/source/Image, unique compiled format/setup bytes, SHA256SUMS,
DT arguments, original DT hardware, systemd/init/Bash/common-loader bytes and
five load-file/CRC expectations. Raw quiet arguments are **299 → 323 bytes**;
the full literal U-Boot command is **341 bytes**. The sole new volatile token is
`k230.init_exec_return=1`; original synchronous/marker-free policy and three
qualified controls remain. No new logging, reporter, target, timer or IRQ policy
is selected.

Initial actual qualification failed closed on the archive's `lib` symlink.
Independent inspection and peer review found precisely a module-store-root
relocation: both archives have 2,025 entries, the referenced 17-entry module
and firmware trees have identical bytes and modes, and no other shared entry
changes. The corrected qualifier permits only that exact symlink/tree relocation;
mutation fixtures reject changed units/dependencies/module content/modes and
unsafe targets. The first failed qualification and fresh successful retry remain
separate in run history. Corrected focused fixtures: **17 PASS**; established
controller regressions **68 PASS** after the duplicate-helper correction.
Strict OpenSpec and whitespace checks pass.

Physical record, output-call return, userspace transition, ordinary login/root,
real touch and protected candidate return remain **UNVERIFIED**. A zero record
would prove exec setup succeeded, not that userspace ran; record presence cannot
prove its own printk call returned. Missing output is unknown. Task 5b.5 remains
open. Root must review/land this packet, repeat protected live preflight and stage
matching artifacts before the bounded operator trial:

```sh
python3 tools/mainline-drm-system-trial.py begin --bundle /nix/store/5f2j4y8hy9cclbqjx4nshhxi4jiwz7iq-k230-mainline-drm-trial-boot-files --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL --state PRIVATE_STATE --log PRIVATE_UART --result PRIVATE_RESULT --wait-initramfs-in-initcall --without-boot-markers --init-exec-return
```

Private manifest and report are deliberately not committed. The diagnostic
record grants no input authority; the existing fresh login, exact arguments and
identity gates remain mandatory. Unknown readiness stops further candidate input
and leaves protected recovery to the sole board operator.

A later [host availability check](availability-2026-10-05.json) found the new
source/kernel/dev/bundle paths absent before staging. Fresh preparation failed
closed before UART; no board change occurred. The cause has not been verified.
Historical build and qualification remain valid records, but current staging
requires restoring the exact pinned outputs, retaining store roots, and a fresh
hash/qualifier check. That restoration was pending at the availability check. Subsequent
[restoration, registered roots and fresh qualification](../restoration-host/README.md)
passed independently with exactly matching bytes; no physical result is claimed.
