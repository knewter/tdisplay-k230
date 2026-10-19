# Copy-only integrated trial — 2026-10-19

Exact source `08cf4516b396b3e7902827fabe7d4de891322de7` built successfully:

- Bundle `/nix/store/fwcpj27k366skrcm99r2hzg571ly5hjm-k230-coherent-shell-boot-files`.
- Trial system `/nix/store/ib5x4pwvjzb3d4ql2zjc6dbd07k6s4xb-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Baseline boot files and persistent profile stayed at the previous system.
  A600-second restoration timer bounded the temporary activation. No reboot.

The same six-gesture full/reduced workloads each produced216 complete trace
IDs and zero missing/unresolved stages. Actual session format remainsRGB565;
three cards and the same native resolution/transform/refresh. Source/system
identity was checked before collection; metadata and exact collection scripts
are preserved beside this file.

**Both modes FAIL the frozen timing budgets.** The pure analyzer command is:

```sh
python3 tools/shell-motion-trace.py --board \
  --log docs/evidence/panel-paint/candidate-copy-only/telemetry.log \
  --provenance injected --compare-motion \
  --output docs/evidence/panel-paint/candidate-copy-only/motion.json
```

It exits1; that is the measured result, not a host-test failure.

| Measurement | Full | Reduced |
| --- | ---: | ---: |
| Run ID | 86713382406222 | 86772136593032 |
| Input-to-present p95 | 119.212ms | 63.749ms |
| Frame interval p95 | 57.482ms | 38.324ms |
| Actual cadence | 26.095Hz | 26.096Hz |

Full mode's tail latency regressed. There is no claim that less CPU alone
improved end-to-end responsiveness. [cpu.json](cpu.json) uses the existing
correlated repaint/input cost analyzer and full mode's106 input-bearing frames:
mean build CPU16.506ms, p95 17.521ms; mean render17.119ms; total19.431ms.
The previous full run's build mean was22.760ms. These CPU subdivisions exclude
blocked presentation time and are not additive p95/optical measurements.
[costs.log](costs.log) is combined with the full run rows from[telemetry.log](telemetry.log)
when feeding `docs/evidence/card-shell/input-cost-probe/analyze.py`.

The remaining cadence is consistent with a separate scheduling boundary:
`nix/shell.nix` configures an8ms render window to avoid a physically observed
bottom-band flicker. Render CPU still exceeds that window. This is a lead,
not a measured claim that changing the window is safe. The8ms setting is
preserved; its actual flicker evidence must not be silently waived.

The camera had moved back to the picture tablet. A bounded recording from
that framing is rejected as K230 optical proof and is **not committed here**.
The operator was asked to re-aim it when that session is finished. Native
captures were inspected and retained in the session scratch directory; they
are not substituted for camera-visible movement.

After the failed trial, normal motion was restored, the trial restoration
timer stopped, and the exact baseline system was activated again.
[restored-baseline.json](restored-baseline.json) records active shell/UI,
default mode0, no test devices and successful Home navigation. Boot/profile
were never changed, and the board reservation was released. This candidate
was not selected as the persistent/default system and the change stays open.
