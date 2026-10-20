# Batched rotation integrated trials — 2026-10-20 UTC

Source `1bc9243f229e21214dd5f41f1c3da4409ac6c732` exact build11 succeeds.
Bundle `/nix/store/ia9s1q76nsmr91fklb9fg63nx4hhvzpf-k230-coherent-shell-boot-files`
temporarily activates system `/nix/store/8l41vpyaxd20zxdqv4ninmkchydqmv8a-nixos-system-nixos-26.11.20260919.20b1ddd`.
Baseline48af boot/profile stays selected; no reboot. CI39357307837 succeeds
and source-published.json verifies the exact published work revision.

**One paired run passes, but the stability repeat fails. The candidate
remains unqualified.** Each capture waits for the startup Terminal, serializes
owned maps, verifies exactly three apps, confirms focus and actual selected
card before injection. All four starting captures are byte-identical to the
committed shared static image; equality manifest/metadata are adjacent.

| Pair | Mode | Run | p95 input→present | p99 input→present | Result |
| --- | --- | --- | ---: | ---: | --- |
| 14 | Full | 98162845043248 | 28.626ms | 30.155ms | PASS |
| 14 | Reduced | 98213535971243 | 28.498ms | 32.069ms | PASS |
| 15 | Full | 98306953129927 | 39.326ms | 46.357ms | FAIL p95 |
| 15 | Reduced | 98356814937338 | 46.078ms | 65.078ms | FAIL p95/p99 |

The unchanged p95 budget38.32151753209427ms and p99 budget57.4822762981414ms
are applied without rounding a failure to a pass. Frame/RSS checks pass;
exact distributions, sampling limits and maxima stay in each motion.json.
Every mode has216 complete input IDs and zero unresolved. No other board
commands/copies/journal queries overlap a timed capture. All pre-injection
hide-route failures and the single bounded retry are recorded. Normal mode
is restored immediately after reduced capture, before analysis/cost queries.

| Pair | Mode | Build CPU mean | Build CPU p95 |
| --- | --- | ---: | ---: |
| 14 | Full | 4.832ms | 5.304ms |
| 14 | Reduced | 4.870ms | 5.353ms |
| 15 | Full | 4.879ms | 5.366ms |
| 15 | Reduced | 4.921ms | 5.348ms |

Build cost falls from source895's comparable full mean5.246ms, consistent
with the selected copy improvement. This is whole-build CPU, not a new
isolated rotation attribution or proof of reliable latency. Repeating avoids
mistaking one favorable phase for qualification. No new draw-profile, live
client or camera result is claimed for source1bc9243f; its copy pixel/lifetime
oracles pass, and those board gates remain open for the next candidate.

The unchanged per-input probe attributes scene synchronization at0.523ms
mean/0.706ms p95 for full repeat15, and0.537ms/0.732ms for reduced. Source
inspection shows handle_result synchronizing plain motion redraws, the16ms
timer calling prepare, and the render path calling prepare again. This
selects redundant moving-scene synchronization as the next userspace paint
boundary. A future correction must keep policy/ownership immediate, structural
changes synchronous, every presented frame fresh and the settled bilinear
filter restoration intact. No new content cap, quality loss or8ms change.

After the failed repeat, baseline48af/Home/normal is restored, shell/UI active,
own91/92 absent, no injected devices, timer stopped as activation begins,
and sole board reservation released. Restoration metadata is committed.
Camera framing independently inspected at02:12:34UTC still shows the other
larger Ladybird display; no video of that display was started or committed.
A user request to aim the camera at the K230 remains pending. Camera,
qualified-default and archive gates stay open; no persistent candidate selection.

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-rotation-batches/pair-14/telemetry.log --provenance injected --compare-motion --output /tmp/batch-pair14.json
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-rotation-batches/pair-15/telemetry.log --provenance injected --compare-motion --output /tmp/batch-pair15.json
```

Pair14 exits0; pair15 exits1 for the preserved latency failures. Neither
injected software timing nor native pixels claim camera/glass proof.
