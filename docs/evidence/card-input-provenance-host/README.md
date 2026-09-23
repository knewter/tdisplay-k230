# Per-event card input provenance

Recorded 2026-09-23T07:40:15Z; branch `fix/card-input-provenance`, base
`3a296b598940a4b794a10034c402621026ae99a3`. No board access or deployment.

Native Sway seat hooks now pass the event's `wlr_touch` device to the card
adapter. Exact device name `K230 injected touchscreen` produces
`source=injected`; the existing headless fixture name does likewise. Other
native device names retain `source=physical`. Direct card IPC injection remains
injected. `card_shell benchmark physical|injected` declares the expected run
provenance without rewriting any event's observed source.

This label is deliberately not authentication of a real finger. For a board
injected run, the operator harness must verify both the exact device name and
its resolved sysfs location under `/sys/devices/virtual/input`, rejecting the
physical input event. Historical evemu descriptors copied the real Goodix
name; this change does not relabel or retrospectively validate those records.
Real-finger evidence still requires operator attestation and the applicable
physical/optical acceptance procedure.

## Compiled runtime check

```sh
nix build .#card-shell --no-link --print-out-paths --max-jobs 1 --cores 8
python3 tests/test_card_touch_routing.py --provenance \
  --sway /nix/store/fwyx51499i8blppf5rghziaiwm1q3i2i-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --output /tmp/card-input-provenance-01
```

PASS cross-build: `/nix/store/ii5g7635wldnk7jsrfp18ism634w5y70-k230-card-shell`.
Unwrapped executable SHA-256:
`664efd536830d23be850ff7365a09125bd797f6dc93aa3849826c81266eddbdf`.
The runtime uses that actual RISC-V Sway under QEMU, native compiled Wayland
receivers and the registered headless `wlr_touch` device. Seven existing touch
pairing/recovery cases and five additional provenance cases pass. Every receiver
and Sway exits 0.

| Run | Declaration | Observed motion/release labels | Parser result |
| --- | --- | --- | --- |
| Exact injected device name | injected | injected, injected | Schema accepted |
| Simulated physical device name | physical | physical, physical | Schema accepted |
| Physical-name fixture armed as injected | injected | physical, physical | Rejected: mixed input provenance |
| Physical-name then injected-name device in one run | physical | physical, physical, injected, injected | Rejected: mixed input provenance |
| Direct IPC with physical-name device present | injected | injected, injected | Schema accepted |

The guarded fixture adds `test-touch init injected-device` and
`test-touch init physical-label-fixture`; both require
`SWAY_K230_CARD_TEST_INPUT=1` and an actual headless output. The latter deliberately
simulates the physical-label branch; none of these events came from hardware.
The test removes/reinitializes the device and awaits actual Wayland capability
rebinding before each source change. It asserts both motion and release sources
and uses the production benchmark parser to verify mixed/mismatched rejection.

`telemetry.log` preserves the actual constant-prefixed telemetry rows with debug
paths removed. `result.json` records the assertions. These short runs test
provenance and schema only; they do not satisfy sampling, resource, motion or
latency budgets. **Board native-uinput classification, real finger interaction,
optical latency, and normal product acceptance remain UNVERIFIED.**
