# Full-precision cache eligibility trial — 2026-10-19

Source `f1c70977e4f445be9e8daad2b1d8485d9f2511a1` built and was activated
only as a temporary userspace trial. Bundle
`/nix/store/yk00wfvrm2nbjmhspxip59g53f0bwnnr-k230-coherent-shell-boot-files`,
system `/nix/store/r5whrj2vx7c7x4yhx4ba6bnv52b2m04c-nixos-system-nixos-26.11.20260919.20b1ddd`.
Baseline boot/profile remained unchanged; no reboot. The two same-workload
six-gesture runs each retain216 complete stage chains and zero unresolved.

| Mode | Run | p95 input-to-present | p95 frame interval | Cadence |
| --- | --- | ---: | ---: | ---: |
| Full | 87382623905193 | 82.101ms | 38.368ms | 26.095Hz |
| Reduced | 87470037599446 | 64.183ms | 38.326ms | 26.095Hz |

**Both still FAIL the frozen budgets.** Reproduce the pure trace report with:

```sh
python3 tools/shell-motion-trace.py --board \
  --log docs/evidence/panel-paint/candidate-cache-ineligible/telemetry.log \
  --provenance injected --compare-motion \
  --output docs/evidence/panel-paint/candidate-cache-ineligible/motion.json
```

Expected exit1. Full mode's108 input-bearing frames report mean build15.160ms,
p95 15.998ms in [full-cpu.json](full-cpu.json). Its small difference from the
copy-only trial is **not attributed to caching**: the cache never activated.
The bounded counter export reports **zero hits/misses/bytes**, all fallbacks.

The mirror format rows expose the eligibility mismatch: Foot uses
`34325241` (`DRM_FORMAT_ARGB8888`), rejected by the opaque-only SHM guard.
[cache-counters.log](cache-counters.log) and [source-formats.log](source-formats.log)
retain only fixed numeric payloads, selected from:

```text
journalctl -u shell.service --since '2026-10-19 23:12:15 UTC' --until '2026-10-19 23:13:00 UTC' --no-pager -o cat --grep='K230_CARD_SHELL scaled-cache' -n 30
journalctl -u shell.service --since '2026-10-19 23:12:15 UTC' --until '2026-10-19 23:13:00 UTC' --no-pager -o cat --grep='K230_CARD_SHELL mirror' -n 10
```

These counters have a wall-time window, not per-frame IDs. They show no
cache use, not an exact fallback-reason distribution. Source inspection of
pinned wlroots `/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source/types/buffer/client.c`
confirms the client-buffer wrapper forwards SHM/data-pointer access; no
wrapper bypass or lifetime change is needed.

The follow-up preserves ARGB alpha through a same-format pre-scaled cache.
It does not classify ARGB as opaque or drop its alpha. Native tests add
premultiplied-alpha gradients to the existing filter/crop/rounding/rotation
comparisons:96 cases, three changed source frames each, exact RGB565 output.
The normal-output RGB565 cache retains its prior eligibility behavior.

No camera proof is claimed; the camera question remains pending. After this
failed trial, the own600s restore timer was stopped, the exact baseline48af
system restored, mode0/Home verified, and the board released. See
[restored-baseline.json](restored-baseline.json). No default selection/archive.
