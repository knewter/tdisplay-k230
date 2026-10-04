# Positive breadcrumb controller host qualification

On 2026-10-04 at 02:14:43 UTC (October 3, America/Chicago), the actual
`prepare_trial` then `prepare_uart_progress(..., uart_progress_breadcrumbs=True)`
invocation passed with exit 0. This is **host artifact preparation only**.
The [receipt](result.json) records exact realized identities, hashes and checks.
No UART, board command, implicit build, stage or flash was performed.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs-controller`,
branch `mainline-uart-progress-breadcrumbs-controller`, base `8e66e299`,
controller revision `c88af531`. The preparation functions were compared as
Python ASTs with frozen root revision `2a548135` and matched. Root's later
CRLF-only record parsing correction applies to physical capture; it changes
neither these preparation functions nor their artifact qualification.

## Actual invocation and artifacts

Host Python 3.14.7 provides native Zstd support for the archived initrd;
compression and selected payload bytes were not changed.

The [runner](qualification-command.py), SHA256
`19262715f3a13914d1cee9227c6066833a52ddd986b17eb1247431a445940966`, was executed
from a protected mode-0700 directory, with reports/results/manifests mode0600:

```sh
TMPDIR="$HOME/tmp/k230-mainline-uart-breadcrumbs-host-qualification/test-tmp" \
  python3 "$HOME/tmp/k230-mainline-uart-breadcrumbs-host-qualification/qualify.py"
```

The runner first required the coordinator's resumed frozen matching build
receipt to have actual return code 0 and exactly two realized output paths.
The earlier build wrapper ended143/broken-pipe and is a separate failed run;
its partial log is not used to infer success. Full-build/installed-object proof
belongs to tasks5g.2/5g.3, separately from this preparation gate.

Selected bundle:
`/nix/store/mhq10143lsmgr6wlll431a8s3ggb8q6m-k230-mainline-drm-trial-boot-files`.
System: `ac7radxa3iazk4gd5m8scg8yad9h3q5j`; kernel output:
`n8f93vnx87nq5n36zsal7idp2s6c9dkv`; same kernel derivation:
`4hc3qsi5f2rnzav6q02y04ybsyqhcnav`; realized dev output:
`xl3cyf9bbksb5yy2nxc6dgy0fbfd0ii8`. Full store paths appear in the receipt.

Read-only Nix queries tied the selected kernel output and actual dev config
to that same derivation. Required built-ins were present, with config SHA256
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
The derivation's source is realized `k5a5zrhqy9ypr3mja1r50mdlcgi74i1f` and its
actual worker SHA256 matches reviewed
`7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22`.
The hash-bound selected Image contains each complete static breadcrumb string
once, at offsets22211136 and22211200, plus the unique exact setup key.
This rejects the legacy reporter despite its CONFIG=y; strings alone do not
substitute for config/source/derivation proof.

The exact five-load manifest checks passed byte counts, SHA256/CRC32 and load
ranges. The protected stage-one wrapper entry uses the supplied verified
normal report plus existing protected CRC99b89787; it was **not freshly read
from the board** here. The physical controller must repeat protected normal
preflight and each load's CRC. Host normal-report acceptance checks supplied
baseline identity, not fresh live state. The generated pre/postflight helper
contains its real registration-marker absence assertion, to run on the board.

The selected system Image matches the manifest. Its wrapped initrd matches
the selected payload and valid uImage header/data CRCs. Direct archive
inspection verifies actual RISC-V ELF Bash5.3p15 and systemd261.2, required
initrd tools, initrd-release, and their shared executable dynamic loader.
The exact volatile policy retains sole immutable init, serial console,
async0, three qualified fsck/service controls and rdinit=/bin/sh; original
trace gates are removed, and each reporter gate occurs once. The safe full
literal `setenv` command is386 bytes, below512, with no variable expansion.

The private manifest is
`~/tmp/k230-mainline-uart-breadcrumbs-host-qualification/candidate-manifest.json`,
SHA256 `c0fdb2481f9156573dc2efe7d031f7d56e07c41eaf8858f725e778fd277e2358`.
It may be copied by the sole operator into the trial's protected run directory;
raw normal report, prepared helper state and future reception nonce stay private.

## Named host tests and remaining gate

[Test receipts](test-runs.json) preserve the original214-test run's three
`Disk quota exceeded` fixture errors and separate passing bounded scratch rerun.
Focused17 tests passed0.212s; the named214-test command passed35.486s with
owned `~/tmp` scratch. No further broad repeat or unrelated cleanup occurred.
Root separately passed the merged CR regression18 and original numeric20 tests.

Task5g.4's actual positive host qualification is complete. The physical
comparison, worker/sleep/SBI-call-return/RX interpretation, protected return,
ordinary root and deliberate glass remain **UNVERIFIED**. No candidate reboot
is issued by this diagnostic, even after complete records and a receipt.
Only independent protected normal postflight establishes recovery.

The sole operator's pending hardware command uses new private log/result paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs \
  --bundle /nix/store/mhq10143lsmgr6wlll431a8s3ggb8q6m-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_NEW_LOG --result PRIVATE_NEW_RESULT
```

This prepares at most one fresh receipt stimulus after exact fresh received
arguments/init-entry/primary-prompt qualification, then passive capture only.
Host arrival order is not cached-counter measurement timing. Missing or
malformed output permits no repeated stimulus, candidate reboot or causal claim.
Task5b.5 stays open; this change cannot be archived.
