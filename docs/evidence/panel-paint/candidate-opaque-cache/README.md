# Opaque cache trial — 2026-10-19

Source `2ff6b096a40f95b2895fcc05e8927174969e027d` built successfully and was
temporarily activated as system
`/nix/store/i3z01vf5igqm2126sglwifvns7n5k1cp-nixos-system-nixos-26.11.20260919.20b1ddd`
from bundle `/nix/store/3mwh6hd2c0chwynjih4jx9aya12j29xw-k230-coherent-shell-boot-files`.
Baseline boot files and persistent profile were preserved; no reboot.

The immutable cached Foot pixels all passed the opaque certificate:85 opaque,
zero alpha-retained cache generations,9,540 hits,85 misses,zero fallbacks,
peak3,785,152 cached bytes. This proves classification/use, not a timing gain.

The first full run88367284569975 overlapped a probe-client closure copy and
was rejected for acceptance. The quiet replacement pair below ran without
other board commands, journal scans or copies during each workload. Each
mode has216 complete trace IDs and zero unresolved stages. Both **FAIL**:

| Mode | Run | p95 input-to-present | p99 input-to-present | p95 frame interval | Cadence |
| --- | --- | ---: | ---: | ---: | ---: |
| Full | 88434628263562 | 65.410ms | 70.444ms | 38.329ms | 26.095Hz |
| Reduced | 88535156244776 | 65.625ms | 66.509ms | 38.327ms | 26.095Hz |

Frozen p95/p99 budgets remain38.3215175/57.4822763ms. No rounding waiver.
Reproduce motion.json (expected exit1):

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-opaque-cache/telemetry.log --provenance injected --compare-motion --output docs/evidence/panel-paint/candidate-opaque-cache/motion.json
```

A separate bounded three-gesture profile enabled draw tracing. Both caps were
reached (512 draws/128 rotations); only11 complete observed passes can be
grouped. Their texture CPU mean12.341ms plus rotation4.226ms remains too slow
for the existing8ms render window. Among selected draws,833×376 geometry
averaged4.838ms. Geometry and code inspection select unscaled opaque
XRGB8888→RGB565 conversion for an isolated next experiment; the profile does
not uniquely identify an internal Pixman symbol. See profile.json and its
explicit PARTIAL limits. Visibility remained enabled. Reproduce:

```sh
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-opaque-cache/profile.log --workload docs/evidence/panel-paint/candidate-opaque-cache/profile-workload.json --output docs/evidence/panel-paint/candidate-opaque-cache/profile.json
```

No camera acceptance was obtained: the separately inspected23:28:12UTC still
showed the picture tablet. Candidate was not persisted. All owned overrides
were removed and baseline48af restored; normal motion/Home/services/no test
devices were verified in restored-baseline.json. Hardware acceptance remains open.
