# Active alpha cache trial — 2026-10-19

Source `24b2a03dc1d14ef21b8f53dd1b7b26180abf1580` built successfully and
was temporarily activated as system
`/nix/store/z36raypy8wjp1p2y693pld9ckmvwfkqi-nixos-system-nixos-26.11.20260919.20b1ddd`
from bundle `/nix/store/rp3f6f4sndq5hwblbrr3p1kq6m97vb8n-k230-coherent-shell-boot-files`.
Baseline boot/persistent profile stayed unchanged. No reboot.

The cache now activates: full-run counters include **4,736 hits,42 misses,
zero fallbacks**, peak cached bytes3,785,152. The final zero bytes follows
test-client cleanup; hit/miss counters are cumulative. The fixed numeric
payloads in [cache-counters.log](cache-counters.log) were selected from
23:20:30–23:21:05UTC journal rows. This is cache-use proof, not timing acceptance.

Both unchanged six-gesture modes capture216 complete trace IDs with no
unresolved stages and still **FAIL the frozen timing budgets**:

| Mode | Run | p95 input-to-present | p95 frame interval | Cadence |
| --- | --- | ---: | ---: | ---: |
| Full | 87880865744706 | 63.505ms | 38.325ms | 26.095Hz |
| Reduced | 87955988771643 | 64.622ms | 38.325ms | 26.095Hz |

The full run's113 input-bearing frames report mean build16.686ms,
p95 17.390ms. Thus the active ARGB cache alone has **not** demonstrated a
CPU or cadence gain over copy-only; this outcome selects further opaque-
compositing investigation rather than treating cache hits as success.
[full-cpu.json](full-cpu.json) retains the whole subdivision and limits.

Reproduce [motion.json](motion.json), expected exit1:

```sh
python3 tools/shell-motion-trace.py --board \
  --log docs/evidence/panel-paint/candidate-alpha-cache/telemetry.log \
  --provenance injected --compare-motion \
  --output docs/evidence/panel-paint/candidate-alpha-cache/motion.json
```

No K230 camera evidence was obtained in this trial; framing/question remains
as previously recorded. The candidate was not selected as persistent/default.
After measurements, reduced mode was removed, the own600s restore timer
stopped, baseline48af activated again, mode0/Home/services/no test devices
verified, and the board released. [restored-baseline.json](restored-baseline.json).

## Next bounded correction

A fresh cached ARGB image can be certified opaque only if **every actual
cached texel** has alpha255. A same-format pixel scan, excluding padding,
permits exposing that immutable image as XRGB without modifying any color
or alpha values. New source generations rebuild and recheck the certificate;
any non-255 alpha retains ARGB. This enables wlroots' existing opaque-region
culling/SRC path while keeping rounded-corner masking and transparency.
Native tests cover160 cases and three changed frames each, including
opaque→transparent→opaque transitions, partial clips, rotations, filtering,
row padding and invalid scan geometry. This correction still needs a new
build and integrated trial; no gain is claimed here.
