# Paired RVV card workload

The physical context and 192-case pixel comparisons pass; see
[the vector trial](../board-trial/README.md) and
[pixel/package evidence](../../pixman-rvv/pixel-trial/README.md).
The remaining question is the cost of the same live-card interactions with
Pixman's runtime RVV selection enabled and disabled. No result is claimed by
this harness preparation.

## Controlled workload

`tools/card-shell-rvv-benchmark.py` runs **on the reserved physical board**.
Its sibling session, acceptance and budget scripts must be staged alongside it.
It requires the exact matching trial system, physical model and a fresh PASS
from the bounded vector context probe. It then runs three matched pairs in
this order: disabled/automatic, automatic/disabled, disabled/automatic.

Both modes use the same optional `lgpv6h…` card package, kernel, client,
configuration, 568×1232 RGB565 output, producer and budget parser. The unchanged
acceptance script drives one- and two-card workloads with 24 drags apiece,
collects native captures, and records thirteen interaction checks. These are
injected inputs, not physical-finger acceptance.

The session harness sets `PIXMAN_DISABLE=rvv` or an explicit empty disable list
only on its transient compositor service. Automatic selection retains the
library's runtime kernel gate; it does not force instructions. The driver
checks the actual Sway executable, cgroup, process environment and mapped
Pixman library before the workload. The uninstrumented compositor has no
pixel-test callback wrappers. Mapping and policy observations are distinct
from the earlier pixel test's counted RVV callbacks.

Each run uses the existing independently armed root watchdog and restores
shell/seatd afterward. Failure to restore leaves the watchdog armed and aborts
the remaining pairs. Missing frame coverage or changed comparison identities
also prevent a complete measurement. A complete measurement may still fail all
card budgets or record failed interaction checks; those outcomes remain in the
result rather than being relabeled as successful product acceptance.

The output includes per-run full budget reports, normalized telemetry,
interaction observations, runtime identity and thermal/frequency readings where
available. Private process logs and native captures remain on the board until
reviewed. Only each run's `public/` files and the fixed-schema result/plan/progress
records are eligible for direct collection; a public capture hash is not a
claim that its picture has been visually reviewed.

## Commands and limits

Host preparation touches no device:

```sh
python3 tools/card-shell-rvv-benchmark.py --prepare --repeats 3 \
  --revision BENCHMARK_SOURCE_REV --output NEW_PLAN_DIRECTORY
python3 tests/test_card_shell_board_tools.py
python3 tests/test_card_shell_rvv_benchmark.py
python3 tools/card-shell-benchmark.py --self-test
```

The 24 session-control tests, six paired-evidence tests and 18 unchanged budget
parser tests pass. These are host checks, not a physical performance result.

After staging the published scripts/package and booting the recoverable trial,
run on the board:

```sh
python3 tools/card-shell-rvv-benchmark.py --board --repeats 3 \
  --revision BENCHMARK_SOURCE_REV \
  --output /var/lib/k230/rvv-benchmark-NEW_NAME
```

Use a new output directory; previous failed or successful evidence is retained.
The driver bounds each session with the existing 540-second service deadline
and 480-second acceptance subprocess timeout. Its ordinary-session restoration
is on the trial kernel. After collection the operator must reboot to the
persistent normal system and run `tools/check-root-growth.py --board --phase repeat`
with the normal baseline, as specified in the proposal's recovery task.

The default image remains unchanged. Three serial pairs are a small comparison,
not a confidence interval. Presentation feedback is not optical light-output
timing. Passing this experiment alone does not close the independent card UI,
image-integration or real-finger acceptance gates.
