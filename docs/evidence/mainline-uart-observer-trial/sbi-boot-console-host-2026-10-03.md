# Retained SBI boot console: same-image host preparation

Evidence class: host controller tests and actual immutable artifact inspection.
Root worktree `/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`; this increment starts at `e38c9040`.
Owned paths are the observer controller, its focused tests, this note and the
mainline task checkpoint. No kernel rebuild, flash, persistent boot selector,
helper change or board operation is established by these host checks.

The [source plan](../../research/mainline-serial-only-boot-boundary-2026-10-03.md)
qualifies `earlycon=sbi keep_bootcon`: both previous physical captures contain
the kernel's detected SBI DBCN extension banner, and the installed kernel
enables the SBI early console. Retaining the boot console changes printk
delivery and timing. It can duplicate output and can itself block; it does
not guarantee return or identify a UART/clock/IRQ defect.

`--sbi-boot-console` requires `--serial-console-only`, rejects any original
`earlycon` or `keep_bootcon` token (including alternate values), and appends
exactly `earlycon=sbi keep_bootcon` to the existing qualified diagnostic
arguments. Default and serial-only argument values remain unchanged. The
original artifact, Image/hardware-DT/initrd/helper/source/closure checks,
fresh protected normal preflight, load/CRC checks and exact printed arguments
remain prerequisites. Nothing saves the volatile U-Boot environment.

The observer parser, reception gates and passive recovery deadlines are
unchanged. Duplicate/interleaved records are still failures, never collapsed
into acceptance. Duplicate readiness sends zero receipts. A protected normal
return may separately qualify recovery while the diagnostic remains failed;
better logging alone is not usable-root or receive-path proof.

## Host proof

```sh
python3 -B -m unittest discover -s tests -p test_mainline_drm_uart_observer_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

All **38 focused tests passed** (7.432 seconds). New checks cover the exact
two-token addition, rejection before artifact access without serial-only mode,
conflicting boot-console policy, retained source artifacts through actual
newc/ELF/unit/DT fixture preparation, result selectors/fresh arguments, both
comparison transports, no boot on printed-argument mismatch, and duplicate
readiness yielding zero receipts. Existing malformed-frame, unknown-state,
one-receipt and normal-return checks still pass.

Independent read-only controller review approved the increment without a
blocking correction and repeated all 38 focused tests successfully (7.408
seconds). The reviewer performed no edits, build or board action.

Actual host `prepare()` against the selected `16cpjji…` bundle passed with
both flags, the private manifest/normal report and the successful blkid
prerequisite below. It inspected the selected Zstandard archive, matching
RISC-V helper/unit/drop-in/marker, unchanged Image and normalized hardware
DT, closure and hashes. Outgoing command lengths were **28, 206, 413 bytes**,
all below the conservative 512-byte limit. No serial port was opened.

The exact operator invocation, using new private output paths:

```sh
python3 tools/mainline-drm-uart-observer-trial.py \
  --serial-console-only --sbi-boot-console \
  --bundle /nix/store/16cpjjiifxgwyb6bndhi39vfmlvcdw6h-k230-mainline-uart-observer-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-observer-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-observer-board/normal-report.json" \
  --blkid-result "$HOME/tmp/k230-mainline-blkid-board/trial-result.json" \
  --log "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-uart.log" \
  --result "$HOME/tmp/k230-mainline-uart-observer-board/sbi-boot-console-result.json"
```

Host Python 3.14 with compression.zstd, pyserial and DT tools is required.
The controller acquires the exclusive board lock itself. Root is the sole
operator after review/landing and a fresh protected normal preflight.
Record actual early-console enable/retention, later init progress, observer
frames and automatic return separately. Keep raw logs, boot identities and
volatile nonces private; commit an explicitly sanitized physical packet.

<!-- UNVERIFIED --> No physical SBI comparison follows from this host proof.
If passive recovery is unknown, stop candidate input and request operator
reset before any protected postflight. If the output still cannot identify
the boundary, the separately reviewed opt-in kernel markers in the source
plan remain the next diagnostic. Ordinary root/panel/glass task 5b.5 stays
unchecked.
