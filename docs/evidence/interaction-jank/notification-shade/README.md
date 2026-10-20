# Landscape notification-shade pull: settings refresh competes with rendering

On 2026-10-20 the operator confirmed panel return and bottom-edge Overview on the one-time cached-EDID kernel candidate, then reported: “when i drag down the top drawer it's a bit stuttery, perhaps worth figuring out why”. The route is the **notification shade**, distinct from the bottom app drawer and the existing sustained app-drawer scrolling task.

The bounded investigation identifies a major contributor: opening the shade starts a fresh Python settings-status process on the sole online CPU. In an isolated, read-only installed `k230-settings status` call, that helper used 678.051ms user CPU plus 142.701ms system CPU over 895.258ms elapsed, exit 0. Output values were discarded. This is process cost, not touch acknowledgement timing. See [settings-cost.json](settings-cost.json).

## Installed identities and source path

All qualified captures retained boot `c17ee483-0191-48ea-986a-9738a274393e`, running system `/nix/store/hpmzja32mncizz7s49ylr8pj9cy5npvg-nixos-system-nixos-26.11.20260919.20b1ddd`, GNU kernel build ID `7a61d8cea3e26df94695189b766de3fd66fa6860`, Sway PID 1076 and the unchanged installed Sway/config. The persistent fallback remained`/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`; all five normal boot-file hashes stayed unchanged. The panel remained logical 1232×568, physical 568×1232, transform 270, scale 1, refresh 52.19Hz. `max_render_time 8` was retained. Only CPU 0 was online.

The installed Rust executable is`/nix/store/fj1v8k4sl1v48qx1v7qafzd9c1g3i259-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`, SHA256 `32c8c445eb0e9467114880d0084762aa6649e69b1274ba7f87d24e300bee9148`. Each capture records exact before/during/after PIDs, SHA256s and outputs; the UI client was restarted to enable its existing opt-in recorder, then restarted normally after capture. The compositor and applications were not restarted.

[Source identity](source-identity.json) ties the actual installed Rust derivation/source to byte-identical reviewed `main.rs`, `render.rs`, `protocol.rs`, `runtime_trace.rs` and `service_data.rs`. The installed settings wrapper executes`/nix/store/qc4fg0nvm8i3lpclnyji2ms68axr0vf3-device_settings.py`, SHA256 `130bd6a560176f112d9c3a677c76bafa591a40aec97c744cd362d6c5485f4106`, identical to `tools/device_settings.py`.

The source sequence is `reveal_message(Begin)` → `refresh_route(Shade)` → queued `RefreshSettings` → `settings_command(settings,["status"])`. The worker runs asynchronously, but its process still competes for CPU while the finger-tracking animation runs. `RefreshNotifications` also runs; this experiment changes only the identified settings-status child. Rendering caches shade artwork, then copies the translated full-screen buffer and applies a stationary backdrop per frame. In trial C,104 frames without scene rebuild took median 2.922 ms CPU (p95 3.064 ms), versus median 9.3435 ms elapsed. Additional runnable waiting was observed for both UI and compositor. This does not establish that buffer copying is the dominant cost.

## Workload and exact capture commands

Each capture has three synthetic compositor-to-client reveal streams: `begin`, 60 updates across progress 0..1000 at nominal 60 Hz over about 1.04 s, then `finish` closed, 0.5 s settle and 0.5 s inter-gesture pause. The stream uses the actual private shell route socket as the shell user. It bypasses physical touch and compositor gesture recognition. The installed recorder retains numeric nested spans and actual presentation feedback in RAM; serialization happens after its 20 s deadline. The recorder does not log notification contents, addresses or settings values. SSH follows the operator's explicit preference; UART evidence was not collected.

The exact F/G capture source is [priority-driver.py.txt](priority-driver.py.txt), SHA256 `203d542c89e53481957f23dd73f8436d5400eb02aa00dce6c59e9128b41f13eb`. The commands used the protected configuration pathname supplied outside Git:

```sh
scp -q -F "$PROTECTED_SSH_CONFIG" docs/evidence/interaction-jank/notification-shade/priority-driver.py.txt k230:/var/tmp/k230-shade-priority.py
ssh -F "$PROTECTED_SSH_CONFIG" k230 '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /var/tmp/k230-shade-priority.py'
ssh -F "$PROTECTED_SSH_CONFIG" k230 '/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 /var/tmp/k230-shade-priority.py --nice-status'
```

Both exited0. The source guards this exact boot/system/profile/output and refuses to reuse a capture directory. Trial F ran 19:28:19.514–19:28:53.136 UTC; G ran 19:29:14.297–19:29:48.014 UTC. The test sampled only the compositor, Rust client, observer and the exact known settings-status children. Identifying the Python script rather than its brief shell wrapper matters.

## Controlled diagnostic comparison

[Comparison](comparison.json), [F replay](analysis-f.json), [G replay](analysis-g.json) and the committed trial directories preserve every presentation outcome and all tails. The same capture source/workload/installed binaries/config/kernel/output/tracer/sampler ran in both conditions. F left priorities unchanged. G changed only exact-source, read-only `device_settings.py status` children from nice 0 to nice 19, after verifying their command/source and start identity. The two treated children exited before cleanup; no persistent priority or product change was made. Pending refresh requests can coalesce: F observed three status processes, G two. Fresh-state timing is not qualified by this diagnostic.

| Pull | F median presentation gap | G median presentation gap | F maximum | G maximum | F/G presented frames during pull |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 76.641ms | 38.338ms | 114.972ms | 76.621ms | 14 / 20 |
| 2 | 76.6395ms | 38.324ms | 114.967ms | 57.486ms | 15 / 24 |
| 3 | 76.6175ms | 38.327ms | 114.964ms | 95.809ms | 15 / 22 |

These gaps use the actual `CLOCK_MONOTONIC` presentation timestamps for frames committed within each pull. They exclude idle boundaries; delayed callback delivery is not mistaken for presentation time. F/G have 2351/3260 events and zero recorder/phase losses, no unavailable/overflowed presentation requests, and every committed frame ends in either a recorded presentation or discard. The replay retains discards. Coarse 10 Hz resource collection itself used about 10.93%/10.59% CPU over the full F/G sample intervals, so these are instrumented diagnostic figures, **not native or optical frame-rate acceptance**. Trial C's lighter initial trace had roughly57.5ms median gaps; the more intrusive broad sampler in D was rejected.

The comparison supports CPU competition from cold settings refresh as a major cause of the reported shade stutter. It does not establish that it is the only cause: G still has roughly 38 ms median gaps and a 95.809 ms maximum. There is no claim of 60 fps, a touch-acknowledgement pass, or a shipped performance fix.

## Decision and remaining work

A follow-up should keep Python interpreter startup out of the active reveal, while retaining correct external-state freshness, first-open behavior, errors, and real brightness/network/power controls. Candidates include a prewarmed/cached status snapshot with bounded refresh after gesture settlement, or a persistent/native status read path. A blanket nice 19 setting is not shipped: it can defer status work and interact with the existing 4 s service deadline. The next implementation needs its own bounded proposal, matching candidate, before/after proof and ordinary deployment; this report does not authorize dropping fresh-state behavior.

Task 1.1 is complete for the reported route. App-drawer sustained scrolling, keyboard budgets, ordinary-card/video measurements and their conditional follow-ups remain untouched and unchecked. No main spec is synced or archived. The earlier kernel fix still awaits explicit HDMI replug/trackpad physical acceptance and persistent promotion; these shade measurements do not complete those gates.

## Failed and supplementary captures

- A: capture driver incomplete because the shell user could not serialize its trace to the full root filesystem (`ENOSPC`). The empty trace is not timing evidence. Numeric capacity checks showed root had zero unprivileged available bytes, while RAM had ample space. This is a real storage issue, recorded separately for coordination; no image/closure or unrelated file was deleted, and it is not established as the shade's cause.
- B: the driver parsed the JSON file before serialization finished. It cleaned up normally; a full trace later existed, but that driver outcome remains incomplete and does not qualify acceptance. C corrected completion detection by waiting for the final newline.
- C: first complete trace and narrow resource capture; its full data and replay are committed as the initial diagnostic. It did not identify the remaining CPU consumers.
- D: broad whole-process sampling imposed substantial observer load and sampled too slowly for the per-pull resource coverage gate. No performance comparison uses D. Its raw trace/resources are preserved privately with committed hashes and disposition.
- E: trace completed, but the first helper detector followed the transient wrapper rather than the real Python script. It cannot establish zero settings CPU; F/G correct that detector. Its raw trace/resources remain private with committed hashes and disposition.

## Replay and restored state

```sh
python3 docs/evidence/interaction-jank/notification-shade/analyze.py.txt docs/evidence/interaction-jank/notification-shade/trial-c
python3 docs/evidence/interaction-jank/notification-shade/analyze.py.txt docs/evidence/interaction-jank/notification-shade/trial-f
python3 docs/evidence/interaction-jank/notification-shade/analyze.py.txt docs/evidence/interaction-jank/notification-shade/trial-g
openspec validate the-shell-profiles-reported-interaction-jank --strict
python3 tools/blob-scan.py --no-vendor
```

The immutable manifests pin each trace hash and source hash. [Final control](final-control.json) verifies the original boot files, root tracing controls, compositor/config hashes, kernel build ID, system/profile and landscape output; normal services are active, tracing environment/override absent, no trace instances remain. Only hash-verified, copied files owned by these shade attempts were removed from the board. All raw captures remain in the protected host scratch directory. The board reservation was released after this query; no build slot was used. Reacquire it and recheck identities before any further board action.

Worktree `.claude/worktrees/interaction-jank`, branch `measure/interaction-jank`, base `916799fbf5b5fe328d43819acb0264c25915e5e3`; owned paths are `docs/evidence/interaction-jank/`, this change's task note, and only its reviewed row in `docs/work-board-status.json`. No product source or persistent image setting changed.
