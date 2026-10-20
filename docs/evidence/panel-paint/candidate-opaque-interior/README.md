# Opaque-interior integrated trials — 2026-10-20 UTC

Exact source `37be9567fdd1198aa1ba7d7e377060999e37b44b` built successfully
as bundle `/nix/store/m8m8gkwp3zmd00ma199b8b6bw487prn1-k230-coherent-shell-boot-files`
and temporary system `/nix/store/ysfxir8hgbvh2xk8n68qjls94rdbx76g-nixos-system-nixos-26.11.20260919.20b1ddd`.
Build command, complete log, result and bundle identity are adjacent. CI run
39352792248 succeeded and the exact revision appeared at the published work URL.
The persistent boot/profile stayed at baseline48af; no reboot is claimed.

The first two quiet six-gesture pairs report full PASS / reduced FAIL.
Reviewing the compositor screenshots revealed asynchronous test-terminal
mapping: Motion-one was the last card in full mode, with only one visible
neighbor, but the middle card in reduced mode, with two visible neighbors.
Those passing full runs **do not qualify a comparable paired workload**.
All runs and failures are retained below. Serializing one terminal's mapping
before launching the next preserves the same three-card/native-input workload
and gives the same middle-card starting layout in both modes. The corrected
pair11 fails both modes. No threshold, image quality or8ms render guard changed.

| Pair | Motion | Trace run | p95 input→present | p99 input→present | p95 frame interval | Parser result |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 9 | full | 95227536604337 | 28.533ms | 43.516ms | 19.178ms | PASS |
| 9 | reduced | 95279710732721 | 48.403ms | 59.567ms | 38.323ms | FAIL |
| 10 | full | 95975032200777 | 29.534ms | 44.106ms | 38.318ms | PASS |
| 10 | reduced | 96023690298213 | 61.062ms | 64.425ms | 38.326ms | FAIL |
| 11 | full | 96114516480484 | 47.547ms | 64.188ms | 38.323ms | FAIL |
| 11 | reduced | 96164781283531 | 57.316ms | 64.884ms | 38.325ms | FAIL |

Frozen p95 input/frame budget38.32151753209427ms and p99 budget57.4822762981414ms
remain unchanged. Every mode has216 complete input IDs, no unresolved traces;
all RSS growth measurements remain below64MiB. Commands/metadata preserve
quantiles, observer limits and every missed budget, without rounding a failure
to a pass. No other board queries/copies/journal scans overlapped timed workloads.
The known Rust hide-route startup failure happened before injection; capture
metadata records its single bounded retry. Mode restoration ran immediately
after reduced capture. No later normal-mode events are relabeled as reduced.

Corrected pair11 build CPU is6.243ms mean/6.722ms p95 (full,184 input-bearing
frames), and6.178ms mean/6.861ms p95 (reduced,168 frames). Earlier pair9 full
5.035ms/reduced6.140ms means compare different starting arrangements, not an
intrinsic reduced-motion rendering penalty. Pair10 and11 costs, complete
numeric logs and analysis are preserved in repeat-costs.log/repeat-cpu.json.

Separate three-gesture profiles hit512 draw/128 rotation caps. Full has55
complete grouped passes: texture1.651ms mean and rotation3.314ms mean. Reduced
has50: texture1.405ms and rotation2.896ms. All56/51 selected output-damage rows
report preserved=1; mean copied logical pixels438,795/385,770 respectively.
Actual interior=1 appears for immutable opaque card draws. Numeric source
formats, geometry and selected path are adjacent. Diagnostic timing is not
acceptance timing. Full profile messages were recovered from their unique
historical PID after the independent profile watchdog restarted the shell;
its metadata explicitly distinguishes workload system from system at collection
and marks the unavailable old environment. No current environment was inferred.

The main833×376 card draw averages0.475ms in the full diagnostic. A787×44
ARGB OVER title averages0.399ms over32 selected rows, despite mostly transparent
margins. This selects exact transparent-margin omission at the immutable title
producer as the next boundary. All actual ink/ellipsis/alpha and coordinates
must remain unchanged; no quality reduction or content cap is authorized.

The separate live correctness run records advancing main and desynchronized
child counters. At exit, one has98 frames/97 callbacks/96 releases and96/95/94
child counts; two has149/148/147 main and148/147/146 child counts. In-flight
buffers may remain at exit; initial invisibility/setup gaps are not latency
acceptance or absence-of-leak proof. Both compositor PNGs were inspected:
counter patterns change while rounded composition remains visible. These are
board software captures, not camera or real-glass evidence. The live run is
not a qualifying timing run. No concurrent K230 camera proof exists yet.

The baseline was restored after trials; restored-baseline.json records active
shell/UI, normal mode, own91 absent, Home and no injected devices. A separate
check confirms own92 absent. Temporary rollback timers were stopped only as
baseline activation began. The board reservation is released after checks.
Candidate not persisted. Build proof alone does not close board timing,
camera, default-selection or archive gates.

Reproduce each motion report (exit1 is the recorded budget failure):

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-opaque-interior/repeat-11/telemetry.log --provenance injected --compare-motion --output /tmp/ordered-motion.json
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-opaque-interior/full-profile.log --workload docs/evidence/panel-paint/candidate-opaque-interior/full-profile-workload.json --output /tmp/full-profile.json
```
