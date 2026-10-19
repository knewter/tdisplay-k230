# Concurrent K230 motion trace and camera proof — 2026-10-19

The camera was aimed at the K230 by the operator, then checked before these
**new** native-uinput full/reduced runs. The two original 21:52/21:53 runs
remain software-only evidence. These recordings close task 2.2's independent
camera-visible movement gate. They do **not** turn the failed timing budgets
into a performance pass, prove real-finger latency, or observe every refresh.

## Identity and source artifacts

- Worktree: `.claude/worktrees/agent-a576b48f3db2aa9c4`, branch
  `side-edge-back`, base `6620bf5c71840812800f293b1409dc5765c8b0c9`.
- Collection/analysis checkout: `501e96645ca903517aab4a619798db5d96147231`.
- Installed compositor source: `29fe458cc4044cb5095e6aeb5fc84b4fdfb3d931`;
  running system:
  `/nix/store/48afqvxz6i15rz9q4if3b1c08j6l3n37-nixos-system-nixos-26.11.20260919.20b1ddd`.
- DSI-1 landscape, transform 270, physical 568×1232, logical 1232×568,
  nominal 52.19 Hz, Pixman/RGB565. No new build, flash, or reboot.
- Same three-card workload as the preceding runs: existing Terminal plus
  two temporary labeled Foot clients. Six alternating left/right gestures,
  35 moves over 700 ms, 800 ms after release, baseline/tail 3.2 s. `grim` runs
  before/after the gesture loops. Input is injected through the native
  uinput/libinput path, not a real finger.

| Mode | Trace run | Board collection started (UTC) | Video launch (UTC) | Video |
| --- | --- | --- | --- | --- |
| Full | `84093776463236` | 2026-10-19T22:17:31Z | 2026-10-19T22:17:28.648Z | [full.mp4](full.mp4) |
| Reduced | `84157760180137` | 2026-10-19T22:18:35Z | 2026-10-19T22:18:32.559Z | [reduced.mp4](reduced.mp4) |

The original video bytes are preserved; both capture and workload processes
exited 0. Each video is 40 s, 1280×720, H.264, with 180-degree presentation rotation.
Video SHA-256:

```text
full: e38a564b4f0a002e510a319eb9c94ca4aed51172d53c9cbeaeb5f57a76d6d695
reduced: 62c08db87ee6b7110d7855ae14805c009c1c47be10804f3d528da4edbed2e9a2
```

[full-capture.json](full-capture.json) and
[reduced-capture.json](reduced-capture.json) retain exact FFmpeg commands,
progress receipt timestamps, camera launch/end bounds, UTC/monotonic stamps,
clock samples and original artifact paths. The workload-end host stamp is
when the already-exited child was reaped after video completion; it is not
the last gesture time. The board metadata records actual gesture times.
[full-metadata.json](full-metadata.json) and
[reduced-metadata.json](reduced-metadata.json) retain output/axis ranges,
source identity and every injected down/up time.

## Correlation and visible observations

[correlation.json](correlation.json) links each video hash, trace run,
gesture ID, accepted input ID range and conservative video PTS bounds.
For each mode, gesture IDs 1–6 map to input IDs 1–36,37–72,73–108,109–144,
145–180,181–216. Motion inputs and release each have all five observed
trace stages and no unresolved chain.

A board monotonic clock sample is bracketed by host stamps before and after
its SSH round trip. The first camera frame is conservatively bracketed by
FFmpeg launch and first progress receipt. Combining those intervals gives
alignment uncertainty widths **1.351 s full /1.173 s reduced**. These broad
bounds associate the repeated workload and trace IDs with visible movement;
they are not an optical input-to-photon measurement. No frame is claimed to
match an exact scanout solely from an inferred clock offset.

The clips and [full-contact.jpg](full-contact.jpg)/
[reduced-contact.jpg](reduced-contact.jpg) visibly show the Overview's card
separator moving back and forth with the six alternating scripted swipes,
then returning to its settled position. Contact sheets sample at 4 fps from
original video PTS 7–23 s; their displayed labels start at zero, so add 7 s to
read the original video PTS. Camera orientation makes logical horizontal
card movement appear mostly vertical in the image. The tilted/soft camera
view still distinguishes card boundaries and movement; it cannot establish
subtle text sharpness or tearing quality.

Each MP4 contains 1180 frames over 40 s: **29.5 encoded frames/s average**,
although the camera was requested at 30 fps. Both files have 20 PTS gaps above
50 ms, maximum 66.667 ms. These are camera/encoding sampling gaps, not inferred
missed panel frames. At 52.19 Hz the panel can refresh between camera frames;
a single panel-refresh blank or tear could be missed.

A separate all-decoded-frame brightness proxy checks the interior bright
header rectangle `(x=560, y=250, w=40, h=250)`. It flags a frame if under 2% of its
pixels exceed grayscale 120. Over conservative gesture-plus-settle windows:

| Mode | Original video PTS window | Decoded frames checked | Dark candidates | Minimum bright fraction |
| --- | --- | ---: | ---: | ---: |
| Full | 8.574–18.832 s | 307 | 0 | 1.000 |
| Reduced | 8.817–18.898 s | 302 | 0 | 1.000 |

No whole-panel blackout is visible in the contact-sheet gesture sequences,
and the proxy found no sampled loss of the bright header. This is bounded
camera evidence, not a calibrated black-level test or a zero-blank proof at
panel cadence. Full-frame review measurements and PTS are in
[full-frame-review.csv](full-frame-review.csv) and
[reduced-frame-review.csv](reduced-frame-review.csv). The brightest separator
row is a coarse motion aid, not a validated card-position estimator: it can
select a screen border when the separator leaves its ROI.

The complete 40 s clips include setup and cleanup. Only the named gesture
windows qualify for the blanking observation. The full clip's late tail may
include the deliberately requested shell restart when enabling reduced
motion after the full workload had finished; this is outside its review
window and is not silently counted as gesture blanking.

## Trace results and failed budgets

[motion.json](motion.json) is unchanged machine output from the trace parser;
its generic camera fields remain `UNVERIFIED` because that parser does not
read videos. The independent camera proof is this file plus correlation,
recordings and frame review. Neither report substitutes for the other.

| Measurement | Full | Reduced |
| --- | ---: | ---: |
| Accepted trace IDs / incomplete / unresolved | 216 / 0 / 0 | 216 / 0 / 0 |
| Input-to-present p95 | **74.634 ms — FAIL** | **74.115 ms — FAIL** |
| Input-to-present p99 | **84.555 ms — FAIL** | **82.147 ms — FAIL** |
| Frame interval p95 | **57.481 ms — FAIL** | **57.481 ms — FAIL** |
| Frame interval p99 | **57.497 ms — FAIL** | **57.484 ms — FAIL** |
| Actual presentation cadence | 26.095 Hz | 26.095 Hz |
| Inferred extra nominal refresh intervals | 154 | 135 |
| Unpresented output events | 0 | 0 |
| Release-to-settled-present p50 (parser quantile) | 278.527 ms | 149.244 ms |
| CPU, one core = 100% | 28.125% | 28.483% |
| Peak RSS | 51,064,832 bytes | 45,207,552 bytes |
| RSS growth | 5,263,360 bytes | 10,924,032 bytes |

Budgets remain p95 ≤ 38.3215 ms, p99 ≤ 57.4823 ms and RSS growth ≤ 64 MiB.
Both modes fail latency/frame budgets; memory growth passes. Reduced-motion
trace parity passes and settling is shorter. CPU has no declared budget.
The console `blank_frames` field counts unpresented output events; it does
not replace the bounded camera observation. Inferred refresh gaps do not
count physically observed dropped frames.

## Commands and restoration

Collection used the original workload in
[../sources/collect-motion-board.py.txt](../sources/collect-motion-board.py.txt)
and original host runner, wrapped by
[run-camera-motion.py.txt](run-camera-motion.py.txt). The wrapper uses
`tools/capture-feature.py`'s command builder with 40 s capture plus FFmpeg
progress timestamps; its exact command is retained in each capture manifest.
Original per-session host invocation:

```sh
python3 /home/jadams/tmp/codex-claude-handoff-20261019/3/run-camera-motion.py full
python3 /home/jadams/tmp/codex-claude-handoff-20261019/3/set-motion-mode-host.py on
python3 /home/jadams/tmp/codex-claude-handoff-20261019/3/run-camera-motion.py reduced
python3 /home/jadams/tmp/codex-claude-handoff-20261019/3/set-motion-mode-host.py off
python3 /home/jadams/tmp/codex-claude-handoff-20261019/3/motion-restore-check.py
```

The source copies preserve historical scratch/store paths. They are records
of the executed commands, not a portable installed test command. Correlation
source: [analyze-camera-motion.py.txt](analyze-camera-motion.py.txt), using
FFprobe frame PTS and FFmpeg grayscale decode with passthrough frame timing.
The pure trace report is reproducible from the repo:

```sh
python3 tools/shell-motion-trace.py --board \
  --log docs/evidence/coherent-shell/motion-2026-10-19/camera/telemetry.log \
  --provenance injected --compare-motion \
  --output docs/evidence/coherent-shell/motion-2026-10-19/camera/motion.json
```

Result: **exit 1**, expected for measured budget failures; all stage chains
complete and reduced-motion parity succeeds. [telemetry.log](telemetry.log)
preserves the two bounded normalized journals.

The reduced-mode override had its independent 180 s restoration watchdog.
After collection it was removed and normal shell/UI restarted. The first
restoration-check attempt failed transiently after restart; its immediate
repeat succeeded. [restored.json](restored.json) confirms default environment 0,
owned override absent, active shell/UI, zero injected devices and successful
Home navigation. Board and camera reservations are released. No performance
optimization, new reboot or image deployment is claimed by this proof.
