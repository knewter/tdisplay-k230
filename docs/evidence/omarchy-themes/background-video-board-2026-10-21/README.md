# Background video trial on the landscape panel — 2026-10-21

The installed wallpaper client plays the selected H264 fixture, and the
coverage correction now stops its decoder under a real opaque app. This change
remains open because tracking cadence misses its declared target in both still
and video arms. Those misses are not accepted as passing performance gates.
The current default remains the original still.

Evidence classes: physical board over SSH, injected native uinput, native
`grim` captures, and a separate camera recording of the panel. No real finger
contact or contact-to-photon timing was measured. The unchanged board boot ID
was `fbfdd9d3-7f95-4aec-978f-1a19b2a220f9`; logical output was 1232×568,
transform 270, on DSI-1. Host callback tests and cross-builds are separate proof.

## Reproducible workload and installed identities

- Original system/current/booted/persistent profile:
  `/nix/store/p501mchy0dq9lyjnaxwkx5s2pdm4i2yj-nixos-system-nixos-26.11.20260919.20b1ddd`.
- Original compositor executable SHA-256:
  `9464072ac100e77500c7b6113920d2c2ed14e022612eddbc38a037ce9b006670`.
- Rust wallpaper executable SHA-256:
  `32c8c445eb0e9467114880d0084762aa6649e69b1274ba7f87d24e300bee9148`.
- Trial source: `7938986ad13fdfc624756f3ba7d318eefc1279cd`.
  [Staged file hashes](staged-files.json), [fixture generation and hashes](fixture.json).
- A temporary `source3-background-trial` user theme copies the packaged
  Catppuccin Latte configuration and contains an eight-second 640×360/30fps
  H264 `testsrc2` movie and its decoded first still. The wallpaper decoder
  requests eight frames/s at the current output size. This single synthetic
  fixture does not characterize every asset, codec, resolution, or frame rate.
- The pinned [interaction checklist](../trial-workload-v1.json) identifies the
  broader route sequence; the basic sampler does **not** execute that checklist.
  The additional card runs below execute six persistent-uinput drags each,
  with one and three real Foot cards. They do not claim the entire real-finger
  checklist was performed.

Exact narrow trial invocation, as `shell` with its installed Wayland environment
and a held `/tmp/k230-board.lock` reservation:

```sh
python3 /run/shell/source3-background-trial-20261021/tools/handheld-theme-trial.py \
  --candidate-manifest /run/shell/source3-background-trial-20261021/candidate.json \
  --workload backgrounds \
  --output /run/shell/source3-background-trial-20261021/basic-result \
  --raw-private-dir /run/shell/source3-background-trial-20261021/raw-basic
```

The unchanged harness completed both arms and restored the original generation
`2e583fb7dc1947e9d444c171` and saved preferences. Its raw
[public result](baseline-theme-trial.json) retains `physical_observation:
UNVERIFIED`; the separate camera review is not a rewrite of that field.
The installed helper returns deferred app synchronization, represented as
`unknown` by this harness. No synchronous app-style acceptance is inferred.

| Idle Home arm | Combined CPU, mean cores | Peak sampled process RSS | Sampled cgroup memory peak |
| --- | ---: | ---: | ---: |
| Original still | 0.0201 | 164,028,416 B | 135,782,400 B |
| Matching fixture still | 0.0158 | 164,810,752 B | 133,484,544 B |
| Fixture video | 0.8728 | 201,732,096 B | 168,763,392 B |

Both `shell.service` and `shell-ui.service`, including the decoder child, are
included. These are separate 12-second sequential samples, not a paired
statistical estimate. Peaks can miss shorter spikes and cgroup memory includes
caches. The video status advanced decoded/submitted/callback counters by 74
in 12.019943s. Those counters and distinct native images establish client
progress; they are not optical presentation timestamps.

[Static native frame](baseline-static.png), [first video frame](baseline-video.png),
[second video frame](baseline-video-second.png), and
[30-second panel-camera excerpt](baseline-panel-video.mp4).
The camera excerpt is a scaled export of seconds 170–200 of the complete
200-second recording retained privately with its manifest. Camera acquisition
latency was not qualified for this trial. Images and video were visually
reviewed; changing test-pattern content is visible on the physical panel.

## Original card comparison and the failing cover probe

[Collector](background-collect-cards.py), [first pair driver](background-run-cards.py),
[continued video driver](background-run-video-cards.py),
[first run](first-card-trial.json), and [video run](video-card-trial.json)
preserve the actual commands and observations. Each collector releases its
uinput device, closes only its two named temporary applications, disarms the
benchmark, and returns Home. The first pair stopped on the cover failure;
the separate video run records that failure and continues the comparison.

| Original compositor | Update CPU p95 | Input→present p95 | Tracking interval p95 |
| --- | ---: | ---: | ---: |
| Still, one card | 4.523 ms | 26.105 ms | 38.325 ms |
| Video, one card | 4.577 ms | 45.772 ms | 38.324 ms |
| Still, three cards | 7.486 ms | 36.330 ms | 38.325 ms |
| Video, three cards | 7.274 ms | 38.948 ms | 38.325 ms |

Frozen targets remain 16.667ms CPU p95, 66.667ms input→present p95, and
33.334ms tracking p95, with their original maximum thresholds also retained
in every per-run `budget-analysis.json`. Tracking fails in all four arms.
This ordered pair does not establish a regression rate or repeatability.
The original runs lack session memory phases and keep that metric
`INCOMPLETE`. The 60-second video RSS sampler also failed on an exiting
process; that sample is not reported as a complete RSS measurement.

A borderless fullscreen Foot app was independently checked too. Its protocol
trace declares a fully opaque region and a 1232×568 viewport. The compositor
still published `covered:false`; status remained `playing`. In the recorded
covered two-second interval the decoder counter advanced from 110 to 131
while submitted/callback counters stayed at 18. The
[native covered image](baseline-covered.png) and
[allowlisted protocol observations](coverage-protocol-borderless.json)
are retained. Returning Home resumed visible submissions. Every driver then
restored the original theme; none of these results passes covered pause.

## Coverage correction and first rejected candidate

[Source audit](coverage-source-audit.json) grounds two independent exclusions:
wlroots supplies full source boxes for normal client surfaces, and Sway puts
floating apps directly in its global floating scene tree. The filter rejected
all nonempty source boxes and recognized only per-output app-layer ancestors.
It therefore discarded eligible opaque app buffers before region accumulation.

The correction accepts an explicit full-buffer source like the implicit full
source and counts global floating/fullscreen app layers above the wallpaper.
Actual crops, offsets, transformed buffers, translucent pixels, rounded corners,
and lower wallpaper/Home layers remain conservative exclusions. No viewport
geometry alone certifies transparency as opaque.

`python3 tests/test_wallpaper_cover.py` compiles the real callback with actual
Pixman regions and scene data. The original callback fails the full-viewport
assertion. First candidate `8dfcfc7a` fixes that case but fails the added global
floating-layer case. The corrected callback passes both plus the exclusion
cases. [Original failure](cover-regression-original.log),
[first-candidate regression](cover-regression-floating-before.log),
[passing test](cover-regression-after.log).

The first candidate's board test **also failed covered pause**; it is not an
accepted fix. [Its complete driver result](first-candidate/metadata.json) and
[frozen budget replay](first-candidate/budget-analysis.json) retain that failure.
Its separate session resource samples include both shell service cgroups:
measured incremental memory was 6,787,072 B with one card and 10,240,000 B with
three, below the unchanged 64MiB bound. These are still-only samples on the
first candidate, not video memory proof for the final correction.

[Memory collector](collect-cards.py) and [replay script](analyze-card-costs.py)
keep raw compositor telemetry separate from the derived trace containing the
external cgroup samples. Entry/back IPC boundaries assign stable resource
phases; samples in the explicit back-request/ack transition are counted
separately. The unchanged board parser's portrait geometry warning remains
visible for this landscape run. No numerical target is relaxed.

## Final corrected candidate: physical pause and resource comparison

Source `88f04401dc941fce488423de927caab312e088cd` built as
`nix build .#kernelMainlineDrmShellLandscapeHdmiBootFiles --max-jobs 1 --cores 6`,
under the shared heavy/Nix build locks. [Build and boot-file comparison](candidate2/build-receipt.json)
shows unchanged Image/initrd/logo, and exactly one `init=` path replacement in
both the generated DTB and bootargs. No hardware DT property changes.

Installed compositor:
`/nix/store/hy37k7zpyzawlnbmf5jd7cg2zdgybl3f-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`,
SHA-256 `4fc7bf3a0c0818c9eb3d286de4579999b3fbbaf9abe0e4317c017bca1dc663ba`.
The initial test used an owned runtime override on p501 with a timed fallback.
The original still and normal compositor were restored while its second build
waited for the shared slot. The original and first-candidate board failures remain preserved.

The [second-candidate driver and complete observations](candidate2/metadata.json)
now record `covered:true`, `paused-covered`, no decoder PID, and counters fixed
at decoded 62/submitted 17/callback 17 across the covered two-second interval
(after a one-second settling period). Returning Home starts a new decoder;
decoded/submitted/callback counters each advance by seven in the observed
uncovered sample. Counters are per decoder lifetime and can reset on restart;
we do not compare their absolute values across different decoder PIDs.
[Actual app protocol and coverage](coverage-protocol-candidate2.json), and
[separate panel-camera excerpt](candidate2/panel-pause-resume.mp4).

| Corrected compositor | Update CPU p95 | Input→present p95 | Tracking p95 | Session growth |
| --- | ---: | ---: | ---: | ---: |
| Still, one card | 4.543 ms | 36.986 ms | 38.323 ms | 7,090,176 B |
| Video, one card | 4.341 ms | 30.264 ms | 38.321 ms | 4,042,752 B |
| Still, three cards | 7.538 ms | 36.750 ms | 38.322 ms | 10,330,112 B |
| Video, three cards | 7.166 ms | 40.039 ms | 38.323 ms | 8,904,704 B |

[Still frozen-budget replay](candidate2/static/budget-analysis.json) and
[video frozen-budget replay](candidate2/video/budget-analysis.json) retain every
original p95/maximum criterion. **Only tracking fails** among the numerical
metrics; CPU, input/submit/present, release, and sampled memory pass in these
runs. The unchanged parser separately records its portrait geometry warning
because these are the operator-requested landscape runs. We do not relabel
landscape as portrait or declare the whole board gate passed.

The video arm is the normal opaque-app/deck workflow, with legitimate visibility
pause when covered; it is not a stress test of continuously decoding video
behind translucent apps. The separate idle-Home sample above keeps the large
visible-video cost explicit. Corrected video workload sampling over 60 s reports
0.4168 mean CPU cores and 279,101,440 B peak sampled process RSS, including the
same two services. This mixed active/covered workload cannot be compared as
if it were the earlier idle-Home sample. The repeated static RSS sampler failed
on a process exit; its result remains a failure, while its separate cgroup
phase samples remain available and pass their recorded memory check.

Reduced-motion startup also has [board observations](candidate2/reduced-motion/result.json):
the same installed Rust executable, with only its wrapper's session flag `0`→`1`,
reports `paused-reduced-motion`, no decoder PID, and decoded/submitted counters
remaining zero. The visible still receives seven Wayland callbacks, so the
raw all-counter-stopped field is **false**; [review](candidate2/reduced-motion/review.json)
explains why callback activity is not decoding. Flag `0` restores playback,
then the original still is restored and the owned override removed.
[Native fallback frame](candidate2/reduced-motion/paused.png).
This tests the configured startup preference, not a live writable Settings toggle.

The full system
`/nix/store/2igpibpw4nn0clbda7p35dp5bhg28n35-nixos-system-nixos-26.11.20260919.20b1ddd`
was then activated through its normal units, with both overrides absent,
unchanged Rust bytes, original theme, reduced-motion `0`, and landscape verified.
[Actual normal-system activation](candidate2/system-test-activation.json).
[Persistent selection](candidate2/promotion-receipt.json) backs up both mutable
boot payloads, protects old/new closures with GC roots, verifies every other
boot payload/selector unchanged, and changes only the two checked `init=`
paths before selecting the new profile. The receipt intentionally precedes
ordinary reboot proof and retains `ordinary_boot_verified:false`.
The [owned test theme was removed](candidate2/fixture-cleanup.json) only after
checking every file against its source; existing theme generations stay intact.
The [ordinary warm boot](candidate2/ordinary-boot.json) then returned with new
boot ID `9e664e59-dfd6-49ed-976a-2e38416c0a7f`, current/booted/persistent
profiles all `2igp…`, exact corrected compositor and unchanged Rust/kernel notes,
original still and landscape. The earlier promotion receipt is intentionally
not rewritten into a boot observation. No cold-boot or second-card claim.
[Postboot controls](candidate2/postboot-normal-controls.json) show normal
services, Settings status, original still, no owned trace environment,
no test input device/theme/overrides/timers, and protected boot hashes.
The ordinary startup terminal initially covers the wallpaper; the explicit
Home command gives `covered:false` and the [native Home image](candidate2/postboot-home.png).
This is a normal startup route, not a claim that Home was the first boot frame.

## Gallery and compatibility matrix

Earlier [HDMI fit-mode and overlay evidence](../background-fit-modes-board/README.md)
is retained as HDMI/injected-input proof; these links do not turn it into a
new panel or real-finger test.

| Mode | Dark theme | Light theme |
| --- | --- | --- |
| crop | [Dark](../background-fit-modes-board/dark-retro-82-crop-1280x720.png) | [Light](../background-fit-modes-board/light-catppuccin-latte-crop-1280x800.png) |
| fit | [Dark](../background-fit-modes-board/dark-retro-82-fit-1280x720.png) | [Light](../background-fit-modes-board/light-catppuccin-latte-fit-1280x800.png) |
| center | [Dark](../background-fit-modes-board/dark-retro-82-center-1280x720.png) | [Light](../background-fit-modes-board/light-catppuccin-latte-center-1280x800.png) |
| fill | [Dark](../background-fit-modes-board/dark-retro-82-fill-1280x720.png) | [Light](../background-fit-modes-board/light-catppuccin-latte-fill-1280x800.png) |
| solid | [Dark](../background-fit-modes-board/dark-retro-82-solid-1280x720.png) | [Light](../background-fit-modes-board/light-catppuccin-latte-solid-1280x800.png) |

| Input/behavior | Disposition |
| --- | --- |
| Crop/fit/center/fill/solid selection | Implemented; earlier dark/light HDMI images and restart persistence. Fill stretches; crop preserves aspect ratio. Solid uses the active palette background. |
| User overlay | Bounded staging/selection/restart shown in the earlier [overlay capture](../background-fit-modes-board/overlay-home-after-restart-1280x800.png). Oversized rejection is host-only. |
| Supported H264 | Selected synthetic fixture plays in the installed wallpaper client and on the panel; costs above. |
| Unsupported suffix/container/codec | Named diagnostics and still fallback have prior host proof in the [video audit](../background-video-audit.md). No new physical fault injection is claimed. |
| Fully covered video | Corrected source has actual opaque-app pause, counter freeze, new-decoder resume and original-theme restoration. Original failing results remain above. |
| Reduced motion | Configured startup flag tested on the board: no decoder, no decoded/submitted frames, visible still callbacks allowed; normal flag/theme restored. No live writable-toggle claim. |
| CPU/frame/memory acceptance | Numerical CPU/input/release/memory checks pass in the named landscape runs; tracking 38.3 ms exceeds 33.334 ms. Visible-video cost remains high; the feature gate stays open and default remains a still. |

## Validation and remaining gate

Worktree `.claude/worktrees/bg31`, branch `bg-31-closure`, base
`7938986ad13fdfc624756f3ba7d318eefc1279cd`. Runtime source checkpoint
`88f04401dc941fce488423de927caab312e088cd` is the tested coverage correction;
subsequent evidence and CI-hook changes do not alter its Nix/runtime inputs.

- `python3 tests/test_wallpaper_cover.py`: passes the actual callback/region
  regression and conservative exclusions; original/first-candidate failures
  are retained above. The test is wired into the existing site CI host checks.
- The selected compositor/full landscape boot-file cross-builds passed. The
  final source `88f` build and actual board executable hashes are recorded above.
- `openspec validate --all --strict`: 49 passed, 0 failed.
- `python3 scripts/build_site.py`: 823 pages, 22,201,074 bytes, 74.27 s against
  32 MiB/120 s limits, with Markdown/output checks passing. A final CI build
  separately checks the published revision.
- Inventory scanning covers the committed evidence media and pinned hashes;
  the eight new binary files are DATA, not executable firmware.

Task 3.3 remains open: the measured tracking p95 is about 38.3 ms against 33.334 ms
for both still/video. The gallery and compatibility matrix satisfy 4.1 after
link validation. Archive 4.2 remains open. Default selection remains the original
still; the operator's landscape choice is preserved. No numerical target,
physical-contact claim, or scope exception was inferred from "continue".

The subsequent [guarded tracking-cadence comparison](tracking-cadence/README.md)
keeps the original still and landscape, compares the 8/12/8 ms render allowance,
and retains the failed gate. It distinguishes actual presentation gaps from
correlated-input gaps without substituting either metric or changing budgets.
The normal 8 ms setting and original runtime state were restored.

The [elapsed-render probe](tracking-elapsed/README.md) then measured three-card
render p95 8.946 ms against that 8 ms allowance, despite passing CPU budgets.
Commit-return and render-start-delay boundaries are recorded separately;
the frozen tracking gate still fails. The temporary diagnostic compositor was
removed and the original installed compositor/system/theme restored.

The [scheduler/render profile](render-profile/README.md) finds runnable wait
during slow renders in a loss-free isolated main-thread trace, bracketed by
untraced arms. Logging contention is a hypothesis for a controlled follow-up;
first-switched-to peer labels do not identify the owner of the whole wait.
Tracking remains above target, and the normal landscape session was restored.

The [journal/file/journal comparison](log-destination/README.md) then reduces
render elapsed p95 from about 9.2 ms to 7.2 ms with file logging, returning to
9.1 ms afterward. Journal-service CPU falls in the file arm, supporting a
benchmark observer cost. Tracking still fails its frozen target; the normal
compositor, journal routing, and landscape session were restored.

With file logging held constant, the [quiet 8/12/8 ms comparison](quiet-cadence/README.md)
passes the frozen three-card tracking target in its 12 ms arm (19.170 ms p95)
while both 8 ms arms still fail. Every numeric metric passes in that arm;
full paired still/video acceptance remains open. The normal 8 ms landscape
session and journal routing were restored.

The [complete quiet12 paired trial](paired12/README.md) then passes all
numeric metrics for still1/3-card and video1-card cases, but video3-card
tracking remains above target. All of its slow correlated intervals include
intermediate actual presentations; the association audit finds no delayed
input-to-render mapping. Reported video counters stay paused at gesture
boundaries. This leaves input/render phase for investigation and the frozen
gate open. Exact preference bytes, normal8ms, still, landscape, and journal
routing were restored.

A [real-finger capture](touch-rate/README.md) shows the Goodix controller
reporting every 8.122 ms while a finger moves. The paired12 injection stepped
every 20 ms, slower than the 19.16 ms refresh, so every drag had to contain one
or two two-refresh intervals. The [touch-rate rerun](touch-rate-trial/README.md)
repeats the same 12 ms trial with 8.14 ms steps, and every numeric metric passes
in all four arms. The pass depends on the temporary 12 ms allowance, and the
portrait-geometry item stays open.
At the installed 8 ms allowance, the same real-finger trial
[fails with three cards](touch-rate-trial-8ms/README.md): render wall p95 of
about 10–11 ms misses the refresh, and frames are genuinely skipped.
The operator then chose 12 ms as the shipped panel allowance. On the
[installed 12 ms system](installed-12ms-trial/README.md) every numeric card
metric passes in all four arms. The operator saw no bottom-band flicker on
glass, and the persistent profile survived an ordinary reboot.
