# PostSample controller preparation (host only)

Prepared on 2026-10-04 UTC in branch
`mainline-uart-progress-post-sample-controller`, based on `9248ffa4`, for task
5h.4. Source and fixtures are implemented; the task remains **UNVERIFIED** and
unchecked pending positive preparation against the actual new matching bundle,
linked Image, realized kernel.dev config and immutable source. No build, UART,
board command, candidate reboot or protected physical check was performed here.

The explicit `--uart-progress-post-sample` selector requires `--mode minimal`,
`--same-image-shell-pid1`, `--uart-progress` and `--uart-progress-breadcrumbs`.
It appends exactly `k230.uart_progress_post_sample=1` to the inherited qualified
volatile arguments. The original artifact is qualified first; the two boot-trace
enabling tokens remain removed only from volatile arguments. The controller
reconstructs a safe full literal `setenv bootargs` below 512 bytes, verifies the
printed arguments and requires exactly one fresh matching kernel command-line
record before the single builtin receipt stimulus. It never sends a second
stimulus, a proc/root guard or a candidate reboot. Default selectors are unchanged.

Before UART access, read-only Nix queries must tie the selected kernel output
and an already-realized dev config to the same derivation. The immutable `src`
from that derivation must contain the reviewed PostSample worker SHA256
`aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b`.
The linked selected Image must contain each complete NUL-terminated fixed
breadcrumb/PostSample string exactly once and each of the two setup keys exactly
once. The old Breadcrumbs selector still requires its original worker hash
`7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22`.
No implicit build is allowed. Common preparation continues to inspect the actual
archived RISC-V Bash, original systemd, shared ELF interpreter, initrd wrapper,
manifest hashes, protected wrapper identity and load ranges. Host Python must
support the selected initrd compression (the actual selected archive uses native
Python 3.14 Zstd support); fixtures do not establish actual new archive presence.

The new fixed public records are exactly these producer byte sequences:

```text
\nK230_UPP1 point=after-n1-write\n
\nK230_UPP1 point=third-post-sleep\n
```

Complete record parsing normalizes conventional CRLF pairs only. Embedded CR,
unknown versions/points, echoes, inserted printk text, extra fields, duplicates,
reverse order and truncation are rejected. Capture begins at bootm, independent
of the capped session buffer, retaining early records once fresh candidate identity
is qualified. Missing first point with a valid third point remains an independent
observed fact and incomplete coverage, without an error or invented causal
sequence. Missing numeric n1 output does not invalidate an observed after-write
point. These markers never authorize input; fresh Linux/Run-bin-sh/primary-prompt
and matching received arguments still gate the sole receipt attempt.

An observed `after-n1-write` point establishes that sample1's preceding numeric
SBI call returned; it does not establish that all numeric bytes were transmitted.
An observed `third-post-sleep` point establishes reaching the point after the
third sleep and stop check, before snapshot. Visibility of either record does not
establish its own SBI call returned. Silence does not locate the stop. Presence
of both points is recorded separately from numeric coverage and the fresh receipt.
`observed_after_stimulus` describes host arrival, not counter measurement causality.
Capture remains bounded to 180 seconds, with measured monotonic elapsed time.
Natural ordered SPL/vendor/login/prompt is independently qualified using the
protected normal postflight; banners alone do not establish recovery. Missing
points or failed normal guards cannot become a passed diagnostic. Unknown
completion means passive observation and independent operator recovery, with no
additional candidate input.

Host commands, all with fixture scratch under `~/tmp`:

```sh
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_post_sample_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_breadcrumbs_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_uart_progress_controller.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_drm_initrd_shell_trial.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_shell_pid1_comparison.py
TMPDIR=$HOME/tmp python3 tests/test_mainline_drm_system_trial.py
openspec validate the-board-runs-a-mainline-kernel --strict
git diff --check
```

The new 20 tests exercise actual pump chunks, split and same-chunk prompt/records,
strict bytes, independent missing-point facts, before-UART qualification failure,
legacy selector compatibility, actual generated five loads/CRCs/literal transport,
one stimulus, saved unknown disposition and successful/failed protected normal
postflight fixtures. Fixtures replace artifacts and transport; they do not prove
hardware scheduling, RX delivery or a physical normal return. Test counts and the
actual legacy artifact rejection are in [host-results.json](host-results.json).

The realized old bundle
`/nix/store/mhq10143lsmgr6wlll431a8s3ggb8q6m-k230-mainline-drm-trial-boot-files`
passed common `prepare_trial` with its existing protected private manifest/report,
then failed PostSample qualification at the reviewed worker hash. This is a real
negative host artifact gate, not a positive NEW artifact gate or live preflight.
Protected wrapper evidence is anchored to the prior normal report and controller
CRC guards; this preparation did not perform a new card readback.

Remaining positive host command, with the NEW exact bundle/dev already realized:

```python
prepared = trial.prepare_uart_progress(
    trial.prepare_trial(PRIVATE_MANIFEST, NEW_BUNDLE, PRIVATE_NORMAL),
    uart_progress_breadcrumbs=True, uart_progress_post_sample=True)
```

After review, integration, this positive gate and independently verified protected
normal recovery, only the root operator may reserve board/UART and run:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs \
  --uart-progress-post-sample --bundle NEW_BUNDLE \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_FRESH_LOG --result PRIVATE_FRESH_RESULT
```

Use new private output paths. A protected normal return must be independently
verified, or operator recovery must remain explicitly pending. Ordinary root,
touch and task 5b.5 remain **UNVERIFIED**; this diagnostic does not close them.
