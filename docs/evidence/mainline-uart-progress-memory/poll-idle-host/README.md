# Existing Memory image with volatile idle polling

Group 5k.1 is a host-only controller increment. Typed
`--uart-progress-memory-poll-idle` requires minimal mode and all previous
same-image shell, progress, Memory and no-stimulus selectors. It reuses existing
Memory qualification and checks the same dev/config and linked Image hashes,
exactly one `CONFIG_GENERIC_IDLE_POLL_SETUP=y` and one NUL-terminated `nohlt`
setup. It then reconstructs the qualified literal command with only trailing
bare `nohlt`; `hlt`, value forms, duplicates, arbitrary additions and unsafe
transport fail closed before UART access. Defaults are unchanged. No kernel,
DT, initrd, card, profile or firmware changes are made.

The strict fresh arguments/summary parser and zero-candidate-input capture are
unchanged. The policy retains NOT_REQUESTED receipt, zero attempts and RX
NOT_TESTED, 180-second passive capture, no retry/reboot on unknown, and independent
ordered normal-return/protected identity checks. An observed summary would
support dependence on the changed idle/tick policy without isolating WFI, timer,
IRQ, firmware or scheduler causation. Missing output remains inconclusive,
including whether the final DBCN output returned. Polling is a temporary
comparison, not a production power policy or ordinary-root/glass acceptance.
The [exact source audit](../../../research/mainline-memory-idle-polling-comparison-2026-10-04.md)
identifies IRQ-enabled forced polling and tick restart in the selected source.

Host tests on 2026-10-04 UTC used Python 3.14 and `TMPDIR=$HOME/tmp`:

- `python3 tests/test_mainline_uart_progress_memory_poll_idle_controller.py`:
  14 focused tests passed. Real config/Image fixtures check hash mismatches,
  missing/duplicate/unsupported setup, literal one-token transform, default
  transport equality and typed conflicts before port/log creation. Real pump
  fixtures check split, stale, malformed, duplicate and truncated summaries,
  wrong received arguments, absent prompt, overflow/read error/timeout and zero
  candidate writes. A full mocked boot exercises the real polling qualifier,
  five loads/CRCs, printed exact arguments and zero writes after `bootm`.
- Progress-controller discovery: 107 passed (14 new plus 93 previous).
- Existing minimal, Bash-PID1 and ordinary controllers: 100, 14 and 36 passed.
  Total across these commands: 257 tests.
- Independent read-only review by `mainline_boot_path`: PASS; reviewer repeated
  all 14 focused tests, checked scope/defaults and found no correction.

Fixture proofs are distinct from actual artifact preparation. Actual group
5k.2 preparation PASSED on controller `d10b8fa0` with
`TMPDIR=$HOME/tmp python3 "$HOME/tmp/k230-mainline-uart-memory-poll-idle-host-qualification/qualify.py"`.
The [safe receipt](result.json) preserves UTC times, command/source hashes and
exact artifacts. The [executed qualifier](qualification-command.py) preserves
same-derivation dev/config, source/Image, archive and manifest checks; its private
expected-root-revision.txt selected the actual successful original full build
`7af8f7b8b5849c75df61d39ee772c2cc8f38542c`. No output was built implicitly.

The same lznjjfx1 bundle, 1pvqbm4 dev, worker SHA256
`307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`,
Image SHA256 `dd4466aae08927dd3eb7e2bcbc28c81d7279c341c52bd002ae67fcc04dde42af`
and config SHA256 `52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`
matched the prior actual Memory proof. The same protected manifest, hardware DT,
wrapped initrd and archived Bash/systemd/common loader were requalified. Exact
Memory arguments gained only trailing bare `nohlt`, changing literal transport
381→387 bytes. The qualified Image contains the unique linked setup at byte
19425483. String/config evidence alone is not runtime selection proof; the
operator controller still requires exact received candidate arguments.

The historical shared preparation functions/constants are AST-identical to
original build source `7af8f7b8`; unchanged preparation/parser functions are
AST-identical to reviewed 5k base `691279d0`. Because the transport function was
extended, the qualifier compares the five previous shell/progress/breadcrumb/
post-sample/Memory outputs explicitly instead of claiming unchanged transport
AST. Every old output matched. The passive observer is unchanged.

An [initial harness failure](initial-qualifier-failure.json) is preserved:
the first invocation asked the older original build controller to contain the
later no-stimulus helper/parser. It failed before artifact preparation or output
creation. The corrected qualifier separates historical shared preparations from
unchanged reviewed-base parsing, then passed. This was a host script error,
not an artifact/build/hardware failure.

The protected historical normal report and wrapper CRC anchor host preparation;
no new live preflight, recovery or wrapper readback was performed. Registration
absence remains an assertion in the future pre/post helper. Baseline/prepared
material stays private. Actual archive inspection used Python 3.14 native Zstd.
No build/UART/physical action occurred in this host task. The subsequent NEW
operator reset passed [protected normal recovery](../no-stimulus-physical-2026-10-04/operator-reset-recovery.json).
Physical polling observation/recovery and ordinary acceptance 5b.5 remain
UNVERIFIED.

After fresh protected recovery and actual artifact preparation, the sole board
operator may use fresh private output paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-poll-idle \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-uart-memory-poll-idle-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-uart-memory-poll-idle-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-uart-memory-poll-idle-board/trial.private.log" \
  --result "$HOME/tmp/k230-mainline-uart-memory-poll-idle-board/result.private.json"
```

A historical protected report used by a host qualifier is not the new physical
recovery/preflight required by this command.
