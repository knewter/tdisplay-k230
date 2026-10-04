# Memory-summary controller preparation (host only)

Prepared on 2026-10-04 UTC in worktree
`/home/jadams/tmp/k230-mainline-uart-progress-memory-controller`, branch
`mainline-uart-progress-memory-controller`, base `a4d6958d`. Owned: the minimal
controller, its new focused test, this evidence and only task 5i.4's preparation
note. No build slot or board/UART reservation was taken. Source and fixtures are
ready; task 5i.4 stays **UNVERIFIED** and unchecked until actual NEW matching
bundle/dev/source/Image positive preparation passes. No build or hardware action
was performed here. Task 5b.5 remains open.

`--uart-progress-memory` is a typed opt-in requiring `--mode minimal`,
`--same-image-shell-pid1` and `--uart-progress`. It rejects Breadcrumbs/PostSample
selectors and the existing clock/shutdown/mode conflicts. Default invocations
remain unchanged. After qualifying the original artifact, it adds only
`k230.uart_progress_memory=1` to the qualified base progress policy. The full
literal U-Boot argument command is reconstructed, checked for unsafe/duplicate
values and bounded below 512 bytes. Printed arguments and exactly one fresh
matching received kernel command-line record remain required before the sole
builtin receipt stimulus. A summary never authorizes input. No retry, additional
candidate command or candidate reboot follows that one stimulus or unknown
completion. Passive capture remains bounded to 180 seconds.

Before UART access, common preparation inspects actual manifest/CRC/load ranges,
U-Boot initrd wrapper, archived RISC-V Bash/original systemd and shared ELF loader.
Read-only Nix queries require an already-realized kernel.dev config from the same
selected kernel derivation, with the six existing required built-in options.
Its exact immutable source must contain the reviewed Memory worker SHA256
`307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`.
The selected linked Image must contain exactly one complete NUL-terminated format
literal and one exact `k230.uart_progress_memory=` setup key. No implicit build is
performed. Actual compressed archive inspection requires a supported host decoder;
the previous selected archive uses Python 3.14 native Zstd. Fixture artifacts do
not prove NEW linked source/config/archive presence.

Frozen producer format:

```text
\nK230_UMP1 s=%u n=%u m=%02x l=%u w=%u\n
```

The exact single line uses decimal one-digit fields and two lowercase hex digits
for the bitmap. Parser stage rules are:

| Stage `s` | Meaning | Required index `n` and bitmap `m` |
| --- | --- | --- |
| 0 | initialized | n=6, m=00 |
| 1 | before sleep | n=0..5, m=(1<<n)-1 |
| 2 | after sleep | n=0..5, m=(1<<n)-1 |
| 3 | snapshot done | n=0..5, m=(1<<(n+1))-1 |
| 4 | six complete | n=5, m=3f |
| 5 | stopped | n=0..5, m=(1<<n)-1 |
| 6 | worker creation failed | n=6, m=00 |

`l` must be the highest completed index, or sentinel 6 when the bitmap is zero.
`w=1` reports that the completion wait returned nonzero and requires terminal
stage 4, 5 or 6. It does not imply all six samples completed: stopped and worker
creation failure also signal completion. `w=0` reports a wait timeout and permits
any consistent stage, including terminal publication racing the timeout. These
facts remain separate from `worker_completed` (stage 4 only), receipt and normal
recovery. Missing/duplicate/malformed/truncated summaries stay unknown/error.

Capture uses fresh returned pump bytes, not the stale capped session buffer;
early records are retained only after fresh candidate identity/arguments match.
Record parsing normalizes CRLF pairs only, preserving embedded CR. A corrupted
namespace is recognized for error classification, never repaired or accepted.
Echoes, alternate grammar, inserted printk, inconsistent stage/index/mask/last,
unknown values and duplicates reject the summary. Numeric/Breadcrumbs/PostSample
worker output is invalid in selected Memory mode. A primary prompt followed by
only the exact summary/newlines in the same pump chunk can qualify readiness.

`memory_summary_valid`, recorded stage/index/bitmap/last, completion wait outcome,
worker completion, receipt and protected normal return are independent fields.
An incomplete valid or timed-out summary remains an observed fact, without
passing a completed diagnostic or claiming usable root. A terminal timeout race
can still record completed work. A completed diagnostic requires valid worker
completion and a matching receipt; the command returns success only with the
independent exact protected normal postflight. Even that is not ordinary root or
glass acceptance. Banners alone cannot establish recovery. Normal services,
identities, hashes, registration absence and fresh boot identity are checked by
the existing protected pre/post helper; host preparation is not that board check.

The summary describes consistent memory before its final firmware call. Presence
does not prove that call returned or identify a firmware/IRQ/scheduler fault.
Missing output cannot separate worker, observer, timeout, firmware or serial
progress. `observed_after_stimulus` is host arrival ordering, not measurement
causality. Unknown completion requires independent operator recovery with no
additional candidate input.

Narrow proof commands (all fixture scratch under `~/tmp`):

```sh
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_memory_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_post_sample_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_breadcrumbs_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_drm_initrd_shell_trial.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_shell_pid1_comparison.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_drm_system_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

Twenty new fixtures exercise all stages/masks and wait/terminal races; actual pump
splits, prompt-plus-summary batches, CRLF/embedded CR, stale/echo/duplicate/malformed
and truncated frames; qualification failure before serial/log creation; exact
five-load/CRC/literal command transport; one stimulus and passive unknown result;
protected return with incomplete/missing-receipt/bad-normal-identity negatives.
Existing 20 PostSample, 18 Breadcrumbs, 20 numeric, 100 minimal, 14 shell and 36
ordinary tests also pass. Counts/times and the actual old-artifact negative gate
are recorded in [host-results.json](host-results.json). Fixtures replace transport
and artifacts; they do not prove firmware execution, hardware RX or new recovery.

The realized previous fjmxf6 PostSample bundle passed common `prepare_trial` with
its protected existing manifest/report, then was rejected at the new Memory worker
hash before UART. This is an actual negative artifact gate, not a positive NEW
matching artifact or live normal preflight. Protected wrapper identity is anchored
to the guarded report and fixed CRC; no additional card readback was performed.

Remaining positive gate, after the NEW exact bundle/dev are already realized:

```python
prepared = trial.prepare_uart_progress(
    trial.prepare_trial(PRIVATE_MANIFEST, NEW_BUNDLE, PRIVATE_NORMAL),
    uart_progress_memory=True)
```

After review/integration, exact object/full artifact and actual controller gates,
and NEW verified protected normal recovery, only the root operator may reserve
board/UART and use fresh private outputs:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --bundle NEW_BUNDLE --manifest PRIVATE_MANIFEST \
  --normal-report PRIVATE_NORMAL --log PRIVATE_FRESH_LOG --result PRIVATE_FRESH_RESULT
```

No hardware acceptance, deployment or physical 5i.5–6 result is claimed here.
