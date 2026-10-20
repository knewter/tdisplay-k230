# Current-source portrait scene confirmation — 2026-10-20 UTC

All three real-compositor headless runs PASS against the current compiled
source `221bbcf34a276a939356e5a6af9bfb124af9896a`:90-degree sampler control,
90-degree opt-in quarter-turn, and180-degree sampler fallback. The same
source is installed as qualified systemj30; this run uses its exact unwrapped
RISC-V Sway under QEMU and the existing native animated Wayland probe client.
`command.json` and `result.json` preserve executable hashes, the tested
fixture hash, invocation, output geometry and runtime opt-in settings.

Each case now requires ordinary and Overview snapshots to change, and all
main/child frame, callback and release counters to advance across each pair.
The exact bottom-endpoint contact is injected and accepted. This confirms
software routing only. The180-degree case also requires successful Overview
entry; its transform2 draw trace still contains only the sampler path.

| Case | Matching transform paths | Ordinary main; child deltas | Overview main; child deltas |
| --- | --- | --- | --- |
| turn90-sampler | sampler | 33/33/33; 33/33/33 | 25/25/25; 25/25/25 |
| turn90-quarter-turn | sampler, tiled | 16/16/16; 16/16/16 | 25/25/25; 25/25/25 |
| turn180-sampler-fallback | sampler | 39/39/39; 39/39/39 | 31/31/31; 31/31/31 |

Counter triplets are frames/callbacks/releases. They show progress over a
bounded observation, not every buffer released or an absence of leaks.
All12 PNGs are committed. Overview-after captures from all three modes were
visually inspected: the main blue pattern, child gold pattern, changing white
counter bits and rounded cards are visible. The fixture compares both images
in each ordinary/Overview pair and rejects static pixels. These are headless
software captures, not camera views of a physical display or a new exhaustive
pixel oracle. The named native pixel/crop/alpha/transform proof remains a
separate gate from this liveness integration.

The first attempt passed both90-degree runs, then failed because the old
fixture expected Overview to be rejected at180 degrees. The current
compositor accepts it. `first-attempt/failure.log`, the original fixture hash,
command and completed90-degree result files preserve that failure. The fixed
fixture requires the newly supported Overview path and live counters at180
rather than skipping it; the sampler-fallback assertion is unchanged.

The original raw debug logs remain at the recorded source-artifact paths.
`original-artifacts.json` preserves their exact bytes/hashes. Committed
`draw-diagnostics.log` files contain only the existing bounded Pixman
rows, with prefix/source-location text removed; raw debug noise is not
performance evidence. Draw counters here are from an emulated headless
compositor. Their CPU values establish no board frame or latency budget.

```sh
python3 tools/hdmi-shell-performance.py --check-scene --variant candidate \
  --sway /nix/store/3vk3p0ps0dng1qmqsrj7w2gfjq024zv8-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/yjb89ap4bq5vb29szdzkr5sv9lpw1sz6-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/portrait-current-scene
```

The executed output directory is recorded in command.json. Result:exit0,
three PASS cases. This refreshes the source identity behind the already
checked task2.3; progress remains3/12. The connected-monitor baseline/profile,
physical gestures, measured budgets, default selection, panel reboot and
archive gates remain open. The native panel's qualified default is unchanged.
