# Integrated opaque conversion — 2026-10-19

Source `748545c08c518aa0a0dfa2da5da7fb4b7bcd63b0` built successfully and
was temporarily activated as system
`/nix/store/xbyin8zwhvgj5pafnv548bg4qizh4crn-nixos-system-nixos-26.11.20260919.20b1ddd`
from `/nix/store/idwwarz25dxkj2vxx9ryzlmxlkbv8nsc-k230-coherent-shell-boot-files`.
Baseline boot/profile stayed selected; no reboot. CI39343768040 succeeded;
the exact source revision and active change were verified at the public work
page (published-check.json).

The integrated conversion **does reduce CPU**:114 input-bearing full-mode
frames have mean build11.210ms, p95 11.828ms, versus the original installed
full-mode mean22.760ms. This meets the paint-only19.161ms target but does
**not** meet the unchanged motion gates or qualify persistent selection.
The quiet six-gesture pair has216 complete trace IDs/mode and zero unresolved
stages. No other board work overlapped either timed workload.

| Mode | Run | p95 input-to-present | p99 input-to-present | p95 frame interval | Cadence |
| --- | --- | ---: | ---: | ---: | ---: |
| Full | 89663995616338 | 65.500ms | 66.506ms | 38.325ms | 26.095Hz |
| Reduced | 89727142360887 | 64.993ms | 66.340ms | 38.325ms | 26.095Hz |

Both **FAIL** frozen38.3215175/57.4822763ms budgets. Reproduce (exit1):

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-conversion/telemetry.log --provenance injected --compare-motion --output docs/evidence/panel-paint/candidate-conversion/motion.json
```

The first reduced-mode and first profile setup each timed out waiting for the
Rust hide route after a service restart, before benchmark/input injection.
Each bounded retry succeeded. No failed setup is counted as a captured run.

Separate diagnostic profiling reaches both512/128 caps and observes only8
complete gesture-window passes: texture mean7.290ms, rotation4.244ms.
The313,208-pixel card draw averages1.508ms (previous4.838ms). A699,776-pixel
draw still averages2.323ms; the current trace lacks its format/mask/scaling
identity, so geometry alone cannot justify changing it. Reproduce:

```sh
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-conversion/profile.log --workload docs/evidence/panel-paint/candidate-conversion/profile-workload.json --output docs/evidence/panel-paint/candidate-conversion/profile.json
```

The short profile is PARTIAL and includes logging overhead. Exact CPU stages
and their limits are in full-cpu.json. Rotation remains unchanged and costly;
separate block/tile experiments were slower and rejected, as documented in
../rejected-rotation/README.md. The next diagnostic adds bounded numeric
format/mask/scaling identity to the existing512 draw rows; it does not alter
compositing, thresholds or the8ms anti-flicker render window.

No K230 camera proof was obtained; separately viewed23:48:18UTC framing
showed the picture tablet. Candidate was not persisted. Own92 profile and91
mode overrides were removed, own600s rollback timer stopped, baseline48af
restored, and normal motion/Home/services/no test devices verified. Hardware
acceptance/default/archive tasks remain open.
