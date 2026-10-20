# Retained output integrated trial — 2026-10-20 UTC

Source `2636ea7c4ee6feed71b8788c7a3b990f1e1baeaa` built successfully and was
temporarily activated as system
`/nix/store/6id8nsg94fqilv06svv4yhhvw3iclbgw-nixos-system-nixos-26.11.20260919.20b1ddd`
from bundle `/nix/store/qpw7xa1fqrs04hkhh9biaqj9ixwmz1pk-k230-coherent-shell-boot-files`.
Baseline boot/profile stayed selected; no reboot. CI39347432106 succeeded.

Retention lowers full-run build CPU to **7.804ms mean,8.705ms p95**, but the
quiet six-gesture full/reduced pair still **FAILS** frozen timing budgets.
Each mode has216 complete trace IDs, no unresolved stages. No other board
commands overlapped either timed workload. The first reduced setup timed out
on the hide route before injection; its retry captured the recorded run.
The owned180s mode watchdog had already removed its override when manual
mode cleanup ran; no later normal-mode events are relabeled as reduced.

| Mode | Run | p95 input-to-present | p99 input-to-present | p95 frame interval |
| --- | --- | ---: | ---: | ---: |
| Full | 91840342554215 | 64.130ms | 65.826ms | 38.325ms |
| Reduced | 91997481332386 | 65.146ms | 66.365ms | 38.329ms |

Full RSS growth16,736,256B (peak55,558,144B); reduced15,257,600B
(peak51,462,144B), below the frozen64MiB growth limit. Sampling limits remain
in motion.json. Active motion cadence stays about26Hz; the higher total
presentation count includes other intervals and is not claimed as52Hz motion.

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-retained-output/telemetry.log --provenance injected --compare-motion --output docs/evidence/panel-paint/candidate-retained-output/motion.json
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-retained-output/profile.log --workload docs/evidence/panel-paint/candidate-retained-output/profile-workload.json --output docs/evidence/panel-paint/candidate-retained-output/profile.json
```

The motion command exits1. Separate diagnostic profiling hits both512/128
caps;55 complete gesture-window passes have texture CPU3.200ms mean and
rotation3.227ms mean.56 selected damage rows all report preserved=1, with
mean432,779.6 copied logical pixels versus699,776 full pixels. Thus buffer
reuse and partial copies activate; they do not by themselves establish a
budget pass. The unchanged313,208-pixel XRGB card interior still averages
1.492ms conversion on50 selected rows, selecting that repeated work next.
Keep full precision for masked edges and all alpha/opacity/scale fallbacks.

A separate **live correctness run**, not a qualifying timing run, used the
existing source-built probe clients and three diagnostic gestures. Main and
child callbacks/releases advanced. At exit,one reports143 frames/142 callbacks/
141 releases and137 child frames/136 callbacks/135 releases;two reports217/
216/215 and214/213/212. In-flight buffers can remain at exit; these counts do
not claim every release or prove absence of leaks. The initial maximum gaps
include setup/invisibility and are not a responsiveness acceptance claim.

The committed live/ PNGs were inspected: main counter patterns change and
rounded composition remains visible. This is compositor-captured board
software evidence, **not camera/glass evidence** or proof of per-frame optical
continuity. The collector safely handles a hide-route setup failure before
its owned log directory exists. Its source, metadata and complete numeric
client logs are retained under live/.

After the measurements, own92 profile override was removed, own600s rollback
timer stopped, baseline48af restored, normal/Home/services/no91+92/no test
devices verified, and board released. Candidate not persisted. Camera at
00:25:12UTC still framed the other large display; no K230 optical proof.
Hardware timing/camera/default/archive tasks remain open.
