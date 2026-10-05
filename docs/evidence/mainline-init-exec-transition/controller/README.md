# PID1 transition controller host preparation

This is host source/fixture evidence for group 5t, based on
`ea54f9e0f367e04c8a8baba8d11a2f6c5ebb37b9` in the isolated
`mainline-init-exec-transition-control` branch. No UART, board, full kernel
build or recovery command was used. Matching full-artifact positive
qualification and physical results remain **UNVERIFIED**; task 5b.5 stays open.

The begin-only `--init-exec-transition` selector requires `--init-exec-return`,
`--wait-initramfs-in-initcall` and `--without-boot-markers`. It appends exactly
`k230.init_exec_transition=1` after the parent gate. The fixed fixture produces
351 argument bytes and a 369-byte literal `setenv` command, below the existing
512-byte limit. Its system pathname is a test vector; the real matching new
system and manifest must be qualified before any UART opening. Saved selection
is strictly boolean and an old missing field means false. Existing unselected
transport, load/CRC, normal checks, identity and recovery function bodies remain
unchanged; the parent read-only qualifier is byte-identical.

Pre-UART qualification verifies the same derivation's immutable source/dev,
config and Image through the existing common inspector. It requires built-in
PRINTK, PRINTK_TIME and SERIAL_8250_CONSOLE, disabled PRINTK_CALLER, the unique
parent format/setup and both unique new literal formats/setup. It rejects a
contradictory enabled/disabled PRINTK_CALLER fixture. The independently read
realized source is
`/nix/store/79yd40jv8h4x866bm1vyw94cm948grax-linux-mainline-k230-init-exec-transition-src`:

| File | SHA-256 |
| --- | --- |
| init/main.c | 0363265487f8fdbd2ba2fcbbda64e3003bc970ed708c73bb6b31ba4e609ea5b5 |
| arch/riscv/kernel/process.c | 2ddbcc113d4a943704edaf576d02638c12c605a6e4468ee82c7f731fdbe3d693 |
| arch/riscv/kernel/traps.c | 0c8aa2616ae1a1a2da6962b12e121ea3b220a940e46a37f82d62b0064c70d433 |
| include/linux/k230-init-exec-transition.h | 071b94a44889f3a61ec17a3af8f276c3a82e081f85c8c89779f0b8ee0d6e6848 |

The complete timestamp-only LF/CRLF records have fixed V1 namespaces and known
points. Fresh Linux, exact received arguments and the `/init` announcement must
precede them. Duplicate, malformed, reversed, interleaved, echoed, truncated or
contradictory records cannot qualify readiness. Missing earlier records remain
explicitly incomplete while a valid later ECALL can independently show its
entry point. A complete sequence alone permits no input: ordinary login and
primary prompt must also qualify before the unchanged candidate identity checks.
Unknown completion stops further input and retains private observations.

The result separates original exec-result output return (supported by either
valid later point), first new point output return (supported by a later ECALL
when both new points were observed), and the last record's own output return
(**UNVERIFIED**). The ECALL point proves successful entry setup, not syscall
handler completion, loader or systemd main, usable root, touch or a fault cause.

`tools/mainline-init-exec-transition-qualify.py` is a read-only actual-artifact
command. It calls the reviewed parent's `archive_delta`, `archived` and
`hardware_dt` helpers rather than introducing another dependency/DT policy.
Only the already reviewed byte/mode-identical module-tree relocation is allowed.
It also checks exact config and system/init bytes, checksums, chosen bootargs,
manifest/CRCs and the sole two-gate transformation. Its normal report is a
protected historical host anchor, never fresh board recovery. No actual new
full-bundle positive result is claimed here.

Commands run with `TMPDIR=$HOME/tmp` and `python3 -B`:

- `tests/test_mainline_init_exec_transition.py`: **17 PASS**, including actual
  parent rejection without build/UART, four realized source hashes, simulated
  four-file/config/Image failures, strict split-pump ordering and incomplete
  facts, retained early facts beyond the receive ring, saved-state strict types,
  full five-load/CRC/printenv transport, and unknown accepted boot-write/flush
  failure with no subsequent input.
- `tests/test_mainline_init_exec_return.py`: **17 PASS**.
- `tests/test_mainline_drm_system_trial.py`: **36 PASS**.
- `tests/test_mainline_initrd_info_kmsg_logging.py`,
  `tests/test_mainline_initrd_info_logging.py`,
  `tests/test_mainline_initrd_debug_logging.py`: **9 + 10 + 13 PASS**.
- Read-only peer-source review in the source agent's isolated tree:
  `tests/test_mainline_init_exec_transition_source.py`: **10 native PASS**.
- `openspec validate the-board-runs-a-mainline-kernel --strict`: **PASS**.
- `git diff --check`: **PASS**.

Initial new fixtures exposed a command-CR expectation and two callback-signature/
mock-recursion mistakes; they failed without board access and were corrected.
The conflicting PRINTK_CALLER fixture prompted the explicit enabled-assignment
rejection. Final passing tests exercise those corrected paths.

After matching full build and independent host review, the coordinator's bounded
operator command is:

```sh
python3 tools/mainline-init-exec-transition-qualify.py \
  --bundle BUNDLE --dev DEV --normal-report PRIVATE_NORMAL
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --init-exec-return --init-exec-transition \
  --bundle BUNDLE --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log PRIVATE_LOG --result PRIVATE_RESULT
```

This is a passive 180-second readiness bound after guarded staging/normal
preflight. A new protected recovery gate, matching full build/artifact proof,
coordinator review/integration/CI and the physical trial remain separate.
