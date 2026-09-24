# Repaint CPU stages

This diagnostic separates the card compositor's already charged repaint CPU
into preparation, output-state construction, and output commit. It leaves the
existing budget producer and acceptance limits unchanged. Extra clock reads
and a log row have overhead; this is not a speedup claim.

Preparation covers Sway output scene configuration and card preparation.
Construction covers `wlr_scene_output_build_state`, including painting, and
any subsequent tearing test. It is not pure Pixman time. Commit covers output
commit CPU, not time until the panel emits light. Uncommitted attempts include
no-frame early returns as well as build/commit failures. Their costs carry
forward into the next successful frame exactly as in the existing producer.

The exporter accepts only the eight named unsigned numeric diagnostic fields.
`analyze.py` first requires the existing input/submit/frame-cost correlation,
then requires a repaint row for every submitted frame, matching render CPU,
an exact sum of stages, and one successful attempt after any unsuccessful
attempts. Missing, duplicate, malformed or inconsistent rows fail analysis.
Per-stage percentile values are not additive.

## Host proof

`build.json` identifies the actual cross-built package, source hashes and
private raw-log hash. `headless.json` records 17 native input-routing checks
and eight source-timing checks using the RISC-V compositor under QEMU user
emulation. The native host client supplied the application surfaces. This was
not a Linux guest, physical touch, or a panel/performance acceptance run.

The normalized `headless-telemetry.log` reconstructs `headless-profile.json`:
104 submitted frames have complete matching stage accounting. Host CPU shares
must not be interpreted as the board's bottleneck.

```sh
python3 -m unittest tests.test_card_shell_telemetry tests.test_card_shell_board_tools
TMPDIR=/mnt/MediaVolume/home/jadams nix build .#card-shell \
  --max-jobs 1 --cores 8 --no-link --print-out-paths
python3 tests/card_shell_runtime.py --native-touch --benchmark --delayed-touch \
  --sway /nix/store/374p33ril3p92i8d805fvzmsjqxhaxsv-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output NEW_HEADLESS_DIRECTORY
python3 docs/evidence/card-shell/repaint-stages/analyze.py \
  --input docs/evidence/card-shell/repaint-stages/headless-telemetry.log \
  --output NEW_PROFILE.json
```

The independent source review found no correctness issue and ran all 26 narrow
producer/exporter tests successfully, including corrupt diagnostic controls.
The unchanged budget parser's 18 self-tests also passed during development.

## Physical gate

`run-board.py` is a bounded one-run derivative of the committed throw-sampling
runner. It uses the same acceptance workload, normal kernel, Pixman policy,
configuration and RISC-V clients, changing only the instrumented compositor
and exporter. Stage it beside the three published session/acceptance/budget
tools and verify their hashes before launch. On the reserved board, run it
inside a root transient service with an outer 660-second deadline:

```sh
python3 /var/lib/k230/card-repaint-tools-REVISION/run-board.py \
  --board --revision FULL_PUBLISHED_REVISION \
  --output /var/lib/k230/card-repaint-stages-REVISION
```

The runner retains its independent restoration watchdog and 540-second session
limit. A completed collection does not mean performance acceptance. Restore
the normal shell and verify system identity, storage, Wi-Fi and HTTPS afterward.
Real-finger feel and default-image acceptance remain open.

## Physical profile on the normal kernel

The bounded run used published revision
`58461f518821cb2b7f1b9d2d80223677d24b3602`, the package in `build.json`, and the
unchanged acceptance workload. `board/result.json` records the actual running
Sway executable, tool hashes, UTC start/end times, boot ID, and restoration.
`board/transfer.json` verifies the nine exported public text files. Raw process
logs and pictures were excluded; no new visual or real-finger proof is claimed.

`board/profile.json` was reconstructed from
`board/run-1/public/telemetry.log`. All **268 submitted frames** have complete
matching stage accounting, including one uncommitted attempt. Construction and
painting dominate repaint CPU; this does not isolate individual Pixman calls.

| Cards | Frames | Prepare share | Build share | Commit share | Build CPU p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| One | 130 | 1.06% | 97.46% | 1.48% | 14.00 ms |
| Two | 138 | 0.86% | 97.77% | 1.37% | 19.79 ms |

Both workload budgets still **FAIL**. Total charged frame CPU p95/max was
16.55/48.98 ms with one card and 23.85/25.20 ms with two. Tracking interval
p95 was 57.48 ms for both, against 33.334 ms. Other declared input, release,
and incremental-memory metrics pass. The one-card 48.98 ms frame includes
33.45 ms of input handling and 15.41 ms of render CPU: repaint optimization
alone cannot be assumed to resolve that outlier.

The acceptance process exited 1: **12 of 13 injected checks were observed**,
but `upward-throw-close-request` failed again. Subsequent refusal, timeout,
accepted-close and normal-control routes were observed. The previous three
clean repeats remain valid historical observations, not proof of universal
throw reliability. The new failure remains in the reports. Its cause cannot
be assigned to the timing hooks merely because this run added instrumentation;
the acceptance setup and state-transition trace require separate analysis.

`board/verification.json` records exact reconstruction of the unchanged budget
report except its generated `created_at` timestamp. This is one diagnostic
run, not a paired performance comparison or an accepted optimized path.

`normal-restoration.json` and its serial log independently verify the normal
system, shell/seatd, Wi-Fi association and HTTPS, credential permissions, root
sentinel, storage boundaries, and protected boot/firmware hashes. Its boot ID
matches the workload: this session neither rebooted nor flashed the board.
The check's `repeat` mode compares the earlier storage baseline; it does not
claim a new reboot in this trial.

The next bounded rendering experiment is reusing bilinearly scaled pixels
only while source content and geometry are unchanged, while preserving live
surface callbacks, subsurfaces, privacy invalidation and the existing fallback.
Source-buffer identity alone cannot prove freshness. Measure actual cache
reuse and same-package enabled/disabled board results before claiming a gain.
Tasks 4.2, 5.1 and 5.3 remain open.
