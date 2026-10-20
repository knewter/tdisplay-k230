# Exact label-ink candidate — 2026-10-20 UTC

Source `895e753df5d1d4e7b1db1fe3440733406b23f849` cross-builds successfully.
The exact command/log/result and bundle identity are adjacent. Running trial
system `/nix/store/3nz1860j3835279ldbmngqyxbr0c0qhm-nixos-system-nixos-26.11.20260919.20b1ddd`
was activated recoverably; baseline48af boot/profile stayed selected, no reboot.
The build invocation accidentally reused the previous host out-link name;
after success the new link was renamed to boot10 and the previous link restored.
The correction manifest preserves both store identities and the actual command.
CI39355329758 succeeds and source-published.json verifies the exact work revision.

**The candidate remains unqualified: full-motion latency still fails.**
The first pair12 reports full p95 latency43.830ms FAIL / reduced PASS, but its
reduced setup initial_app_count=0 exposes a second startup race: the default
Terminal maps after the owned terminals and becomes selected. That reduced
pass is not comparable qualification. Preserve the earlier-pair-12/ data.

The final collector waits for exactly the startup Terminal before launching
each owned terminal serially; it confirms focused app before arming, checks
exactly three expected apps, and verifies actual policy selected_app_id before
injecting. It never closes foreign apps to force setup. Pair13 satisfies all
checks in both modes. Full/reduced before PNGs are byte-identical, also matching
source37be9567's full starting capture. One shared PNG and the equality manifest
are committed; this is one settled setup frame, not every-frame/optical proof.
Neither fixture correction changes gestures, budgets, image quality or8ms guard.

| Pair13 motion | Trace run | p95 input→present | p99 input→present | p95 frame interval | Result |
| --- | --- | ---: | ---: | ---: | --- |
| Full | 97062212700956 | 51.738ms | 66.006ms | 38.320ms | FAIL latency |
| Reduced | 97113978476596 | 30.108ms | 47.665ms | 19.188ms | PASS software budgets |

The frozen p95 limit is38.32151753209427ms and p99 limit57.4822762981414ms.
All216 input IDs complete per mode, zero unresolved. Both pass frame/RSS
checks; RSS limits/sampling remain in motion.json. No other board commands
or copies overlap either qualifying capture. The known hide-route readiness
failure is retried once before injection; metadata records all attempts.
Mode restoration runs immediately after reduced capture. Earlier failures
are retained and no successful subset is a paired acceptance claim.

Pair13 full build CPU5.246ms mean/5.732ms p95, reduced5.192/5.617ms. Compared
with source37's ordered full mean6.243ms, the identical setup frame and native
oracles support the omitted work; this is not an optical speedup claim.
A separate capped profile observes49 complete gesture-window passes: texture
1.142ms mean and rotation3.015ms.50 damage rows average412,158 copied pixels.
The actual title is112×15, averaging0.059ms over34 selected draws, versus the
previous787×44 title's0.399ms. All actual glyph texels and layout remain exact.
Rotation is now the largest measured stage; rectangular tile experiments are
next, isolated from the compositor until pixels and board measurements justify
any implementation. Previously rejected square sizes remain rejected.

The independent live-content run advances both clients and desynchronized
children. Exit counts one:80 frames/79 callbacks/79 releases, child78/77/77;
two:139/138/137, child137/136/135. Initial visibility/setup gaps are not latency
acceptance, and in-flight buffers may remain. These counts do not prove absence
of leaks/every buffer release. Both compositor PNGs were inspected and counter
patterns change while rounded composition remains visible. Not a camera or
glass proof; the live run is not a qualifying timing workload.

Own91/92 overrides are absent after cleanup. Baseline48af is restored with
normal mode/Home, active shell/UI and no injected devices, as recorded in
restored-baseline.json. The rollback timer was stopped as restoration began.
Candidate not persisted. Current camera still needs separate K230 framing
confirmation; camera/default/archive gates remain open.

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-label-ink/telemetry.log --provenance injected --compare-motion --output /tmp/label-motion.json
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-label-ink/profile.log --workload docs/evidence/panel-paint/candidate-label-ink/profile-workload.json --output /tmp/label-profile.json
```

The motion command exits1 for the preserved latency failures. Profile caps,
receipt-time grouping and observer overhead remain explicit in the report.
