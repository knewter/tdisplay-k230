# Board measurement commands (for the coordinator)

Not run here -- this task did not touch the board or `/dev/ttyACM0`, per
its own instructions. These are the exact commands, and the pass criterion,
for whoever holds the board next.

## Pass criterion

Per this change's own requirement text (`specs/runtime/card-shell/spec.md`):
tracking-presentation p95 at or below **2 vblank periods (38.3 ms)** during a
deck drag, ideally 1 period (19.16 ms). `docs/evidence/card-shell/
frame-budget/board-result-2026-09-28.md` already measured hardware vblank
itself is a clean 19.16 ms grid even while the deck animates, so this
criterion is entirely about the compositor's own presentation cadence, not
the panel.

## 1. Existing card-bench telemetry (frame/CPU cost, unchanged by this task)

```sh
nix build .#card-shell --max-jobs 1 --cores 1 --no-link --print-out-paths
# push the resulting sway/card-shell binaries and run the acceptance workload
# exactly as docs/evidence/card-shell/board-cost/long-trace/README.md and
# docs/evidence/card-shell/scaled-cache-board/README.md already do, then:
python3 tools/card-shell-benchmark.py --board \
  --input <telemetry from the board run> \
  --output docs/evidence/card-shell/frame-budget/pixman-<date>.json
```

This still reports `frame_update_cpu_ms` and `tracking_present_interval_ms`
against `tools/card-shell-benchmark.py`'s frozen `BUDGETS`
(`frame_update_cpu_ms` p95 16.667/max 33.334 ms;
`tracking_present_interval_ms` p95 33.334/max 100 ms -- the stricter of the
two numbers `card-shell-benchmark.py` enforces versus this task's own 2x/1x
framing above; both must be read together).

## 2. New: `tools/measure-panel-refresh.sh` (from master, read-only vblank probe)

Already run once, 2026-09-28 (`board-result-2026-09-28.md`). Re-run
identically after any render/commit-path change to confirm raw hardware
vblank is unaffected (it should be -- this probe measures the panel/VO, not
card-shell):

```sh
nix build .#panel-refresh-probe
python3 tools/push-file.py --src result/bin/panel-refresh-probe \
  --dest /tmp/panel-refresh-probe
python3 tools/capture-boot.py --out /tmp/chmod.txt --seconds 10 --kick \
  --expect 'root@nixos' --send 'chmod +x /tmp/panel-refresh-probe'
python3 tools/push-file.py --src tools/measure-panel-refresh.sh \
  --dest /tmp/measure-panel-refresh.sh

# Idle baseline:
python3 tools/capture-boot.py \
  --out docs/evidence/card-shell/frame-budget/idle-capture-<date>.txt \
  --seconds 30 --kick --expect 'root@nixos' \
  --send 'sh /tmp/measure-panel-refresh.sh'
python3 tools/parse-panel-refresh.py \
  --input docs/evidence/card-shell/frame-budget/idle-capture-<date>.txt

# Drag window, run immediately after the card-shell-benchmark drag capture
# above so both describe the same general system state:
python3 tools/capture-boot.py \
  --out docs/evidence/card-shell/frame-budget/drag-capture-<date>.txt \
  --seconds 30 --kick --expect 'root@nixos' \
  --send 'sh /tmp/measure-panel-refresh.sh'
python3 tools/parse-panel-refresh.py \
  --input docs/evidence/card-shell/frame-budget/drag-capture-<date>.txt
```

## 3. Decision after both captures

- Vblank stays clean (~19.16 ms) and `tracking_present_interval_ms` is now
  at or below 38.3 ms p95 (ideally 19.16 ms): task 4.2 passes; proceed to
  task 5.1's non-fixture QEMU smoke and archive-readiness.
- Vblank stays clean but `tracking_present_interval_ms` is still above
  38.3 ms p95: this host investigation (`host-cost-table.md`,
  `commit-pipelining-assessment.md`) found no further safe CPU/damage-side
  lever within this task's scope; record the coordinator's decision --
  accept the measured, understood overrun-rate cost (option b, with the
  distinction from `analysis.md`'s decision table stated explicitly in the
  acceptance record), or open a separately-gated kernel change to attempt
  commit pipelining (option c, with the boot-panic risk priced in per
  `commit-pipelining-assessment.md`).
- Vblank itself is no longer clean: something regressed between
  `board-result-2026-09-28.md` and this run; do not attribute it to this
  task's userspace-only changes without first re-running
  `board-result-2026-09-28.md`'s exact idle capture to isolate whether the
  regression is present even with card-shell untouched.
