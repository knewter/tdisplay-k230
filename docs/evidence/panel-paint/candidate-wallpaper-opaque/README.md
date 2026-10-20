# Opaque wallpaper integrated trial — 2026-10-20 UTC

Source `ed45dc69ee60d5395362d159825138a42ba17907` built successfully and was
temporarily activated as system
`/nix/store/hr6xcp4kr9vlbw5r2nfldy9jw47lwdcb-nixos-system-nixos-26.11.20260919.20b1ddd`.
The build command/result and observed store identity are adjacent. Baseline
boot/profile stayed selected; no reboot. CI39345888563 succeeded.

The producer certificate works: after initialization, full-panel ARGB draw
rows use **SRCop1**, no mask or scaling. Initial OVERop3 rows remain recorded;
no assertion that every frame is opaque. Only actual all255 frames qualify.

Full-mode113 input-bearing frames now have build CPU **9.970ms mean,
10.817ms p95**, versus original22.760ms mean. The quiet six-gesture pair
still **FAILS** frozen timing budgets at26Hz. Each mode has216 complete trace
IDs and zero unresolved stages; no other board commands overlapped either
workload. The first reduced setup timed out on the Rust hide route before
injection; its bounded retry captured the recorded run.

| Mode | Run | p95 input-to-present | p99 input-to-present | p95 frame interval |
| --- | --- | ---: | ---: | ---: |
| Full | 90954276558073 | 65.167ms | 66.288ms | 38.326ms |
| Reduced | 91044873634786 | 64.523ms | 66.608ms | 38.325ms |

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-wallpaper-opaque/telemetry.log --provenance injected --compare-motion --output docs/evidence/panel-paint/candidate-wallpaper-opaque/motion.json
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-wallpaper-opaque/profile.log --workload docs/evidence/panel-paint/candidate-wallpaper-opaque/profile-workload.json --output docs/evidence/panel-paint/candidate-wallpaper-opaque/profile.json
```

The motion command exits1, as expected. The separate profile is PARTIAL,
with512/128 caps reached; retain its exact counts, timing window and observer
limits in profile.json. No camera proof was obtained. The candidate was not
persisted; own91/92 overrides and600s rollback timer were removed, baseline48af
restored, and normal/Home/services/no test devices verified before board release.

The next selected boundary is the remaining forced whole-frame work: retain
one logical image **per physical output buffer**, repaint the damage ring's
aged region, and rotate only actual painted pixels. Invalidate after failed/
interrupted/normal passes or geometry/format/transform changes. New native
three-buffer and allocation/image-failure fixtures must pass before board use.
Hardware timing/camera/default/archive tasks stay open.
