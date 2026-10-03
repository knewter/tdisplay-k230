# Finite UART progress controller — host preparation, 2026-10-03

This is host source/test evidence for group 5f.4 of
`the-board-runs-a-mainline-kernel`. No board, UART, kernel build, candidate
staging, reset, ordinary root, or glass interaction was performed here.
Physical progress records and matching realized-bundle qualification remain
**UNVERIFIED**. Tasks 5f.4, 5f.5 and 5b.5 remain open.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress-controller`, branch
`mainline-uart-progress-controller`, base `a5629a3d`. Owned paths are the
existing minimal controller, the new focused test file, this note and the
narrow 5f.4 task proof/preparation entry. No board or build slot is reserved.

## Artifact and argument gates

The new typed `--uart-progress` selector requires `--mode minimal` and
`--same-image-shell-pid1`. Shutdown debugging/tracing, clock comparison and
other modes are rejected before preparation or serial access. Existing
invocations retain their original paths.

Existing manifest byte/hash/CRC checks, protected wrapper, load ranges,
selected-system identity, archived RISC-V Bash/systemd executables and common
dynamic loader checks still run. The protected preflight and postflight
helper really asserts that `/nix-path-registration` is absent, including a
dangling symlink. Actual archive inspection requires host Python with native
Zstd support (Python 3.14 on the operator host); there is no compression change
or dependency on candidate Python.

The controller additionally runs only these bounded read-only host queries:

```text
nix-store --query --deriver SELECTED_KERNEL_STORE
nix-store --query --outputs SELECTED_KERNEL_DRV
```

The selected kernel and a realized `-dev` output must be outputs of that same
immutable derivation. Its installed
`lib/modules/7.3.0-rc5/build/.config` must uniquely enable
`CONFIG_K230_UART_PROGRESS`, `CONFIG_RISCV_SBI`, `CONFIG_RISCV_TIMER`,
`CONFIG_SERIAL_8250`, `CONFIG_SERIAL_8250_DW` and `CONFIG_OF` as built-ins.
The result preserves the exact kernel/derivation/config paths and config SHA.
Missing/unknown outputs or config fail before UART access. The controller
never builds an absent output, and embedded Image strings are not used as
configuration proof. Root must realize the matching kernel dev output during
5f.3; this host change does not satisfy that gate.

The original artifact must have the exact SBI-only argument shape already
required by the Bash PID1 comparison. Only the volatile value removes its two
trace enabling tokens, retains the immutable `init`, sole serial console,
`consoleblank`, `fsck.mode=skip`, both qualified service masks and
`initramfs_async=0`, and adds `rdinit=/bin/sh` plus exactly
`k230.uart_progress=1`. The full literal `setenv` is reconstructed and checked
for unsafe characters and the existing 512-byte input bound before serial
access. Five loads/counts/CRCs and exact printed U-Boot arguments still gate
`bootm`; no persistent environment, card file or profile changes are added.

## One stimulus and passive observation

Capture begins immediately after `bootm`, rather than after the shell prompt.
Only a fresh candidate Linux 7.3.0-rc5 banner scopes trusted records. Exactly
one fresh candidate `Kernel command line:` line must equal the prepared
volatile value before any stimulus. Missing, mismatched or duplicate received
arguments leave the input gate closed.

Within 90 seconds, a fresh `Run /bin/sh as init process` followed by an
anchored `sh-5.3# ` primary prompt permits one fresh builtin receipt command.
Newlines and complete qualified progress records may follow that prompt in
the same pump batch; arbitrary output, command echoes, continuation prompts,
truncated records and pre-entry/pre-candidate prompts do not qualify it.
No Ctrl-U, repeated receipt, proc/identity command, exit or candidate reboot
follows. Even a successful receipt does not establish the full existing
PID1/proc/root prerequisites for a safe candidate reboot.

The host passively captures for at most the 180-second observation deadline,
including after missing readiness or an unanswered stimulus. A transport
failure preserves partial facts and stops; an unknown write records one
attempt without retry. Capture has a separate 1-MiB parser bound; the private
wire log is retained, and independent normal-return recognition continues
with a rolling phase buffer. Results distinguish the configured deadline from
actual monotonic elapsed capture time.

`K230_UP1` records require exact complete framing, version, ordered unique
sample numbers 0–5 and fixed-width lowercase numeric fields. There is no
arbitrary printk insertion repair. Busy/unavailable/wrong/changed binding
states must have zero, unmeasured UART fields; timer IRQ zero likewise means
unmeasured, not a measured interrupt count of zero. Malformed, truncated,
duplicate or reordered records preserve partial data and prevent a complete
observation claim. Records can arrive before readiness; none are silently
aligned to the stimulus.

`observed_after_stimulus` records **host arrival order only**. A delayed record
can contain state sampled before the input write. It does not establish an
RX delta caused by that write. Sequence progress shows reporter scheduling;
jiffies/ktime show timekeeping observations; timer IRQ counts include possible
reporter wakeups. RX counts include processed breaks and precede filtering and
TTY delivery; failed flip insertion is not Bash receipt. Cached clock rate is
an independent observation. No final record does not prove an SBI call failed
to return, and finite sample count does not guarantee firmware wall-clock
completion.

A natural fresh SPL → exact vendor Linux banner → login → root prompt is
recognized independently of candidate readiness. Only then may the existing
protected postflight helper run. Exact normal identities, all eight file
hashes, three services, marker absence and a new boot ID are required. An
incomplete observation remains a recovered diagnostic failure even if normal
returns. Without protected normal return the result is observation-only and
recovery-required; the controller never attempts candidate reset. Operator
recovery remains a separate root-owned physical gate.

## Host checks and next operator command

Focused tests use actual parser/command functions, the real capped pump with
fixture transport, isolated immutable/config/archive fixtures and a complete
mocked load/CRC/preflight wire path. No test opens serial or invokes a Nix build.

```text
python3 tests/test_mainline_uart_progress_controller.py
python3 tests/test_mainline_drm_system_trial.py
python3 tests/test_mainline_drm_initrd_shell_trial.py
python3 tests/test_mainline_shell_pid1_comparison.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Checks completed at 2026-10-03 23:30 UTC: focused **20 passed** (1.208s),
ordinary **36 passed** (4.136s), existing minimal **100 passed** (23.763s),
shell comparison **14 passed** (1.404s); strict validation and diff check
passed. These are four host suites, not physical protocol observations.

Focused coverage includes fresh received arguments, primary prompt plus report
in one read, split/rolling transport, one/no stimulus, unknown write/read,
duplicate/stale/malformed/truncated records and receipts, early independent
normal return, missing/disabled/wrong-derivation config, exact literal
transport, default compatibility, and failed protected postflight facts.

After source review, actual 5f.3 bundle/config realization and fresh protected
normal recovery, the sole board operator may use fresh private paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --bundle BUNDLE \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```

These placeholders do not authorize a trial from this worker. The matching
realized-bundle preparation, physical records and subsequent protected normal
recovery are still required and cannot be inferred from these host fixtures.
