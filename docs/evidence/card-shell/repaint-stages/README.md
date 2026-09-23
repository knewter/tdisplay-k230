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
Physical results, real-finger feel, and default-image acceptance remain open.
