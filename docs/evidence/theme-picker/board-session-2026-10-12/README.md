# Board session 2026-10-12: picker overhead, matched pairs, motion trial, tap-apply

One SSH-driven session on the reserved board (single operator, `flock /tmp/k230-board.lock` held for the whole
session). **Evidence class: software-injected touch events through the verified virtual device named
`K230 injected touchscreen` (the physical Goodix node was never written), journal and Rust trace timing, and native
`grim` captures taken outside every timing pass. No finger, no camera, no glass observation.** Tasks 14.4 and 18.4
(real finger) were not attempted.

Worktree `/home/jadams/tmp/k230-theme-board-2026-10-12`, branch `theme/board-session-2026-10-12`, base `e7a47f2f`.
Session window 2026-10-12 05:44 to 07:20 UTC.

## What is installed and what was compared

| Item | Identity |
| --- | --- |
| System (booted = current, never changed) | `/nix/store/zvxmd93gnn6n3vpk1mdxgajqnb8h1gkm-nixos-system-nixos-26.11.20260919.20b1ddd`, kernel `7.3.0-rc5` |
| Installed Rust shell (candidate; source `faae7298`: 18.2 motion, 13.2 counters, 13.3 admission gate, 17.2 row repaint) | `/nix/store/ybpnyqmcn672n7x45nx9ybzprljgdhfg-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0` |
| Repaired baseline for 13.4/11.3/17.3 (`8cik`; 12.1 fix, no 13.3 gate, no 17.2 row repaint) | `/nix/store/8cikjd811d7b7hsdhn7nnb3lnipf3vwp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0` |
| Motion baseline for 18.3 (`si9vd`; pre-18.2, has 13.3 and 17.2) | `/nix/store/si9vd9hhdcb8kzppfsfq9id8kaqhnmwk-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0` |
| Compositor / helper interpreter | `/nix/store/q96sk40q7j5v9f0ygxf2wx3yk7nzixqs-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`, `/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3.14` |
| Catalog | 22 themes, 4 backgrounds (still images), 568x1232 |

`8cik` was garbage-collected on the board. It was shipped with `nix-store --export | xz | ssh ... nix-store --import`
(its closure was otherwise present; only the path itself was missing) and pinned with gcroots
`/nix/var/nix/gcroots/k230-theme-baseline-8cik` and `.../k230-theme-motion-si9vd` (left in place).
**Runtime references:** `nix-store -q --references` of `8cik`, `si9vd` and the installed `ybpn` ELF produce the same
seven-path set (md5 `adb9f78378c5b1747e6d1f7ce94699dc` for all three): glibc, glib, cairo, pango, gcc-lib,
librsvg, libxkbcommon. The ELF swap is therefore a like-for-like comparison of the binary.

**The two builds do not draw the same picker.** The `8cik` captures show perspective-skewed cards with a blue
outline; the installed build draws flat cards with page bars (see `13.4/vis/`). Frame-cost differences below
therefore include the visual-polish change as well as the row-repaint mechanism.

### Starting state: no durable theme pointer (departs from the brief)

The board had been reflashed or reset: `/home/shell/.local/state/omarchy/current` held only `.activation.lock`; the
shell ran the bundled default generation and `k230-theme list` reported `active: {id: null, generation: null}`.
In that state the picker's background row **stays at "Loading backgrounds" indefinitely** (reproduced 12 s and 22 s
after opening; `theme_ui.rs` only loads the background detail when `list.active.id` is set). This is the same symptom
`docs/evidence/theme-picker/working-set/README.md` recorded, and it makes the 13.1 gates (both rows resolved) unmeetable.

To get a comparable board I applied the bundled **catppuccin** theme once through the helper as the `shell` user
(`k230-theme preview` then `activate --expected-generation`; durable pointer to generation `1af520f2...`, selected
background `1-totoro`). That is the fixed generation for every run below. **At the end I removed that state and
restarted `shell.service`** to put the board back to its original pointer-less default (see Final state). Applying as
`root` fails with `appearance peer has wrong UID` / `fanout prepare failed and rollback was not acknowledged`; this
was the expected UID check, not a regression.

## Method (all runs)

`tools/run.py` (board, root, board Python) swaps only the final ELF through a runtime drop-in
`/run/systemd/system/shell-ui.service.d/92-theme-session.conf` (wrapper copy with the last `exec` line replaced),
arms an **independent** `systemd-run --on-active` restoration timer, restarts `theme-helper` and `shell-ui`
(so every run starts from fresh processes and the same active theme index 0 and background index 0), opens
Settings, and then runs `tools/theme-picker-profile.py capture` (the 13.1 workload: 2 s baseline, first open 10 s,
6 + 4 swipes of 240 px / 200 ms with 1.2 s rest, 15 s idle, back, warm open 5 s, 6 warm theme swipes, 15 s idle;
no activation). The finally-block removes the drop-in, reloads and restarts the service; the timer is stopped.
The profile harness gates every run: verified virtual device, exact executable identities, PID/start-tick
identity, active generation unchanged for every 0.5 s sample, rows resolved and reviewed (I reviewed native captures
of both rows before the first run), process-cold first opening (journal shows no earlier touch for that PID),
no activation. All 31 runs passed every gate; each `reduce`d report is in `13.4/reports/`.

`tools/` holds the executed drivers (`run.py`, `gestures.py`) and the host analysers; `host/` holds the shell
wrappers that invoked them. Raw private captures stay in `~/tmp/k230-theme-board-run-2026-10-12/` (46 MB, not
committed); their SHA-256 values are in `raw-sha256.json` and per-run identities in `runs-meta.json`.
Typical invocation (UTC start times in `runs-meta.json`):

```sh
BOARD_PYTHON=/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3
systemd-run --pipe --wait --collect --unit=k230-theme-sess-NAME --property=RuntimeMaxSec=400s \
  --setenv=PATH=/run/current-system/sw/bin:/run/current-system/sw/sbin \
  $BOARD_PYTHON $B/run.py run --label NAME --kind baseline|candidate --exe ELF --mode off|counters|trace --out $B/runs/NAME
python3 tools/theme-picker-profile.py reduce RAW --rust-trace TRACE --output REPORT   # host
python3 tools/theme-picker-profile.py compare BASE_REPORT CAND_REPORT                # host, gates then deltas
```

One harness change was needed and is committed with a test: `reduce` called any journal line whose Rust elapsed
clock was lower than the previous line "a process restart". Lines from different threads reach the journal a few
milliseconds out of order, and this fired on about half the runs (a 7 ms `frame-done` reordering). It now tolerates
250 ms (`CLOCK_JITTER_MS`); a real restart changes the PID and is still caught by the PID gate.
`python3 -m unittest discover -s tests -p test_theme_picker_profile.py`: 51 tests pass.

## Task 13.2 / 13.4: observer cost first

Same installed ELF, same workload, fresh restart before each; three OFF, three counters-only, one trace run
(`ov-*`, 05:48 to 06:05 UTC). Pooled medians (`13.4/overhead-pooled.json`; harness pairwise output in
`13.4/harness-overhead-*.json`):

| Pooled median | OFF (3) | counters (3) | trace (1) |
| --- | ---: | ---: | ---: |
| warm theme commit-gap median, ms (each run) | 112.5 (111-141) | 129 (115.5-143) | 142 |
| warm theme Rust CPU % | 69.1 (54-71) | 57.4 (56-66) | 59.6 |
| background-swipe Rust CPU % | 11.1 (9.9-11.4) | 14.4 (10.6-16.1) | 13.8 |
| background commit-gap median, ms | 39 | 39 | 38 |
| idle Rust CPU % (15 s windows) | 0.51 | 0.59 | 0.94 |
| RSS at end, MiB | 86.0 | 85.1 | 87.9 |

Run-to-run spread with the recorder off is as large as any recorder effect on the theme row (the helper's
speculative preview work lands in different swipes each run: 6 to 14 preview requests). The measurable recorder cost
is about +0.08 percentage points of Rust CPU when idle and about +3 points during the cheapest (background) swipes;
trace mode adds about +0.4 points idle. No difference in background commit-gap median and no memory increase.
**Judgement: small enough to interpret counters, with that caveat; they are indicative, and absolute CPU figures from
instrumented runs are slightly high.** The pairs below were run twice per build: trace mode (event ring on both
builds, so spans compare) and recorder off (clean CPU and cadence).

## Task 13.4 / 11.3 / 17.3: three matched pairs, alternating order

Order of execution (UTC from `runs-meta.json`): trace mode `p1` base, cand (06:07); `p2` cand, base; `p3` base,
cand; then recorder off `p1` cand, base (06:21); `p2` base, cand; `p3` cand, base. Fresh processes each run; the
first opening of every run is journal-verified process-cold (disk and wallpaper caches were not cleared, so
this is **not** disk-cold) and the second is warm. Gates passed for all six pairs (`13.4/compare-*.json`:
`comparable: true`).

### Recorder off (CPU, cadence, memory) — base / candidate per pair, then median

| Metric | pair 1 | pair 2 | pair 3 | median |
| --- | ---: | ---: | ---: | ---: |
| Warm theme commit gap, median ms | 137.5 / 108 | 135 / 117 | 141 / 114 | **137.5 / 114** |
| Warm theme commit gap, p95 ms | 183 / 160 | 173 / 177 | 165 / 141 | 173 / 160 |
| Cold theme commit gap, median ms | 143 / 118 | 143 / 123.5 | 140.5 / 121 | 143 / 121 |
| Cold theme commit gap, p95 ms | 177 / 168 | 175 / 184 | 181 / 182 | 177 / 182 |
| Background commit gap, median ms | 80.5 / 39 | 93 / 39 | 87 / 38.5 | **87 / 39** |
| Background commit gap, p95 ms | 142 / 95 | 154 / 90 | 155 / 89 | 154 / 90 |
| Background commits in 4 swipes | 30 / 59 | 31 / 58 | 31 / 60 | 31 / 59 |
| Rust CPU %, warm theme swipes | 77.8 / 63.0 | 79.4 / 68.9 | 80.5 / 75.2 | 79.4 / 68.9 |
| Rust CPU %, cold theme swipes | 81.0 / 60.8 | 81.0 / 72.8 | 80.2 / 63.7 | 81.0 / 63.7 |
| Rust CPU %, background swipes | 35.1 / 9.8 | 44.4 / 18.1 | 43.9 / 11.0 | 43.9 / 11.0 |
| Rust CPU %, idle windows | 0.49 / 0.49 | 0.56 / 0.52 | 0.59 / 0.55 | 0.56 / 0.52 |
| Helper cgroup CPU %, warm theme swipes | 0.06 / 1.01 | 0.06 / 1.67 | 0.06 / 0.71 | 0.06 / 1.01 |
| Rust RSS at end of warm idle, MiB | 78.8 / 86.0 | 80.7 / 88.1 | 82.5 / 86.7 | **80.7 / 86.7** |
| Rust RSS growth over the run, MiB | 27.6 / 34.9 | 29.8 / 36.8 | 31.6 / 35.3 | **29.8 / 35.3** |
| Helper RSS, MiB | 23.9 / 24.0 | 24.1 / 24.0 | 24.0 / 24.0 | 24.0 / 24.0 |
| Commits in the two 15 s idle windows | 0 / 0 | 0 / 0 | 3 / 0 | 0 / 0 |
| Theme preview requests to the helper | 4 / 14 | 5 / 15 | 5 / 14 | 5 / 14 |
| Overlay pre-renders completed (all while no touch held) | 4 / 6 | 4 / 9 | 4 / 7 | 4 / 7 |

All Rust CPU in the sampled windows is on the main `k230-shell-rust` thread (per-thread sampling with start-tick
identity; short-lived worker threads fall between 0.5 s samples, so worker CPU is only visible through the trace
spans below). Opening: first open 6 commits and about 4.4% Rust CPU for both builds; warm open 3 commits for
both.

### Trace mode (spans, presentation) — base / candidate per pair, then median

| Metric | pair 1 | pair 2 | pair 3 | median |
| --- | ---: | ---: | ---: | ---: |
| Warm theme `presented` gap, median ms | 140.2 / 105.2 | 127.0 / 105.3 | 133.6 / 122.6 | 133.6 / 105.3 |
| Warm theme `presented` gap, p95 ms | 186 / 166 | 160 / 178 | 163 / 165 | 163 / 166 |
| Background `presented` gap, median ms | 84.0 / 38.3 | 65.6 / 38.3 | 65.8 / 38.3 | 65.8 / 38.3 |
| `render_total` per frame, warm theme, median ms | 133.3 / 98.6 | 124.8 / 96.9 | 128.6 / 104.3 | **128.6 / 98.6** |
| `render_total` per frame, background, median ms | 76.9 / 3.2 | 61.8 / 3.1 | 60.4 / 3.2 | 61.8 / 3.2 |
| Full scene rebuilds, warm theme swipes | 59 / 8 | 65 / 16 | 65 / 17 | 65 / 16 |
| Full scene rebuilds, cold theme swipes | 61 / 19 | 60 / 20 | 61 / 19 | 61 / 19 |
| Full scene rebuilds, background swipes | 28 / 0 | 30 / 0 | 30 / 0 | 30 / 0 |
| Scene-rebuild wall in warm theme swipes, ms | 7185 / 1040 | 7877 / 2002 | 7780 / 2215 | 7780 / 2002 |
| Row repaint median per frame (candidate only), theme / background, ms | - / 92.8 / 40.3 | - / 93.2 / 39.6 | - / 88.1 / 38.1 | 92.8 / 39.6 |
| Thumbnail hash CPU in warm theme swipes (all off the main thread), ms | 360 / 105 | 37 / 264 | 112 / 219 | 112 / 219 |
| Rust RSS at end, MiB | 89.3 / 84.1 | 75.6 / 88.9 | 76.4 / 87.0 | 76.4 / 87.0 |

The first baseline run (`tr-p1-base`, 89.3 MiB) is an outlier; the other two baseline trace runs end at 75.6 and
76.4 MiB, so the trace pairs are noisier on memory than the recorder-off pairs, but the candidate is higher in
five of six comparisons (+13 and +11 MiB in two trace pairs).

### Speculative admission and in-flight work (trace pairs)

| | pair 1 | pair 2 | pair 3 |
| --- | ---: | ---: | ---: |
| Baseline admissions in total / inside a carousel drag | 3 / 1 | 2 / 0 | 2 / 0 |
| Candidate admissions in total / by shell gesture phase `held` + `moving` | 13 / 0 | 10 / 0 | 13 / 0 |
| Candidate admissions at rest, inside a swipe window (touch plus the 1.2 s after) | 11 | 8 | 11 |
| Candidate completions (in-flight work finishing) by shell phase `held` / `moving` | 1 / 0 | 1 / 1 | 0 / 0 |
| Candidate completions that land inside a carousel touch window | 7 | 2 | 7 |

**No new speculative admission starts during either row's motion in the candidate (0 of 36 in `held`/`moving`).**
The gate defers them to the 1.2 s rest after each swipe, and the work admitted there (a helper `preview` of about
230 to 400 ms, a neighbour warm) is **still in flight when the next swipe starts**: most completions fall at the next
touch-down. The candidate admits four to six times as many speculative requests as the baseline (13 / 10 / 13 vs 3 / 2 / 2
admissions in trace mode; helper `preview` requests 12 to 15 vs 4 to 5 in trace mode and 14 to 15 vs 4 to 5 in off mode) because of the neighbour queue, and the helper
cgroup sits at 1 to 2% (24% in one cold-swipe window) where the baseline's is 0.06%.

### Candidate counters by shell gesture phase (trace runs; count, wall ms, thread CPU ms)

| Kind | `moving` pair 1 / 2 / 3 | `held` pair 1 / 2 / 3 |
| --- | --- | --- |
| scene_rebuild | 23, 2999, 2203 / 33, 4836, 3013 / 33, 4475, 3325 | 4 / 4 / 3 |
| picker_row_repaint | 53, 4846, 3909 / 32, 3707, 2254 / 40, 3472, 2795 | 36, 2957, 2483 / 30, 3065, 2056 / 34, 2815, 2360 |
| render_total | 121 / 111 / 116 frames | 42 / 36 / 39 frames |
| thumbnail_request (hash and resolve each equally many) | 28 / 48 / 40 | 8 / 12 / 10 |

Full per-phase span tables are in `13.4/trace-phase-summary.json` and `13.4/pairs-summary.json`.

### Native stills and sampled frames (not a timing pass)

`13.4/vis/baseline-open-theme-background.png` and `.../candidate-...png`: open, after one theme swipe, after one
background swipe (injected 240 px / 200 ms), native `grim -s 0.5`. Both rows respond in both builds (theme row
catppuccin to flexoki-light, background row Totoro to Omarchy). `13.4/browse-base.mp4` and `browse-cand.mp4` encode
the sampled frames (about 17 frames in 16 s, `tools/sample-grim-frames.sh` with half-scale `grim`, timestamps in the
JSON). They are sampled screencopy, not smooth video: the baseline clip catches the background row in motion
(Blue eye frame); the candidate clip shows theme-row motion but its background swipes fall between samples (that row's
response is shown by the still). I viewed the stills and sampled frames.

### Outcome for 13.4, 11.3 and 17.3

* The candidate **improves cadence and CPU**: warm theme commit-gap median 137.5 to 114 ms (-17%), background
  87 to 39 ms (-55%), background frames double, render per frame 129 to 99 ms (theme) and 62 to 3 ms (background),
  full scene rebuilds fall by 69 to 100%, Rust CPU in swipes falls by 10 to 33 points, idle CPU is unchanged and
  idle windows stay quiet (candidate: 0 commits in every pair run; baseline: 0 except 2 and 3 stray commits in two runs).
* It **regresses memory**: +6.0 MiB (about +8%) at the end of the warm idle window in all three recorder-off pairs
  (+4.2, +7.2, +7.5); +10.7 MiB median in the noisier trace pairs. Helper RSS is unchanged. The cause is
  **UNVERIFIED**: the candidate does about three times as many speculative prepares and about 1.5x the overlay
  pre-renders, but no retained-byte measurement was taken.
* **Repaint still dominates.** The theme row still costs about 93 ms per frame to repaint (candidate), so warm swipes
  run at about 9 to 10 frames per second (p95 gap 160 to 177 ms, not improved), and the candidate still does 23 to 33 full
  scene rebuilds (3.0 to 4.8 s of main-thread wall at about 130 ms each) while `moving`, coinciding with 28 to 48
  thumbnail requests in that phase (17.2 keeps full invalidation for thumbnail completion).
* **Next measured correction (named, not done here):** (1) turn thumbnail completion into row-local damage rather
  than a full scene rebuild, and (2) cut the theme-row repaint cost (about 93 ms for one row; cache the scaled card
  layer and translate it) before further scheduling work; (3) take an RSS attribution (retained pre-render and
  thumbnail bytes versus the speculative-request count) before changing the neighbour queue.

Because warm-swipe p95 does not improve and memory does not hold, **11.3 stays open.** The comparison tasks 13.4
and 17.3 were performed with the evidence above, so they are ticked in `tasks.md`; the push and site-deployment
check in 17.3 and 14.4 / wider 13 and 15 gates are not covered.

## Task 18.3: guarded motion trial (open)

`18.3/`: eight runs (4 per build, 06:34 to 07:00 UTC, trace mode, alternating order `mo theme, ca theme, ca bg, mo bg,
ca theme, mo theme, mo bg, ca bg`), each with two repetitions of five injected programs (`tools/gestures.py`) on one
row, a fresh Settings to Themes opening before every gesture, 2.5 s settle, then a native `grim -s 0.4`
capture (outside the gesture window). 80 gestures; the generation and process identities were checked after every
one and never changed.

* **flick**: 300 px in 80 ms, release at speed.
* **slow**: 300 px in 1.5 s, release at the last sample.
* **hold-release**: 240 px in 300 ms, hold 700 ms, release.
* **reversal**: 200 px left in 200 ms, then 150 px back in 150 ms, release.
* **interrupt**: flick, then a new touch 300 ms after release drags 30 px against the coast.

**The shell records no per-frame carousel position or velocity, so no position or velocity curve is published.**
`input_motion` carries counters, `commit` and `presented` carry no carousel state, and the journal logs only finger
positions. Deriving a curve by replaying the touches through the host model would be a model, not a board result.
What exists is the injected finger path, the frame commits and the settled item:

* `18.3/gesture-timelines.png`: injected finger x against time with frame-commit ticks for both builds.
* `18.3/gesture-release-to-rest.png`: milliseconds from the final release to the last commit.
* `18.3/gesture-summary.json`: per-gesture counts and gaps (80 rows, medians over four repetitions).
* `18.3/labels-{mo,ca}-{theme,bg}.png`: the label strip of each native capture. I read the final item from them.

| Gesture | Row | Frames after release (base / cand) | Last commit after release, ms | Final item (base / cand), ordinal |
| --- | --- | ---: | ---: | --- |
| flick | theme | 14 / 9.5 | 1684 / 1120 | matte-black 11 / lupine 10 (4 of 4 each) |
| slow | theme | 7 / 7 | 626 / 704 | ethereal 2 / everforest 3 |
| hold-release | theme | 4 / 5 | 321 / 419 | catppuccin-latte 1 / 1 |
| reversal | theme | 8 / 12.5 | 298 / 547 | catppuccin 0 / 0 |
| interrupt | theme | 8 / 8 | 805 / 781 | kanagawa 7 (3 of 4; gruvbox 5 once) / hackerman 6 (4 of 4) |
| flick | background | 7.5 / 13 | 237 / 506 | Omarchy 3 / Omarchy 3 |
| slow | background | 7.5 / 10.5 | 245 / 383 | Omarchy 3 / Omarchy 3 |
| hold-release | background | 4 / 7 | 174 / 360 | Waves 1 / 1 |
| reversal | background | 7.5 / 13 | 263 / 487 | Totoro 0 / 0 |
| interrupt | background | 8.5 / 13.5 | 440 / 745 | Omarchy 3 / Blue eye 2 |

Observations only: both builds are repeatable for identical injected input; commit-gap medians are 38 to 65 ms on the
background row in both builds (reversal 41 versus 57 ms in the candidate's favour) and 100 to 125 ms on the theme row
in both (reversal 39 versus 47 ms), so the theme row is drawn at 8 to 10 frames per second in both builds; the candidate commits more frames
after release on the background row (13 versus 7.5 after a flick); the candidate's slow
drag settles one item farther (3 versus 2) and its interrupt absorbs one item more; the settle tail after release is
longer on the background row in the candidate. Whether that is better direct-tracking, flick distance or settling
is exactly 18.4's finger question, and no curve here supports a claim.

**18.3 stays open.** To publish position and velocity curves the shell needs a bounded per-frame carousel
position/velocity record in the Rust trace (one value per row per `commit`). I did not add instrumentation in this
session.

## Task 10.7 and 6.6: warm tap-apply, dark and light (two trials)

`10.7-6.6/` holds the sanitized journal excerpts (`journal-trial-{1,2}.txt`; board local time CDT = UTC-5, identifiers
replaced by labels), the marker logs, `picker-dark-light-dark.png` (five native captures: open dark, light
selected, light applied, dark selected, dark applied) and `panel-bottom-full-resolution.png`.
Each trial: cold `systemctl restart theme-helper shell-ui`, Settings to Themes, 15 s for the neighbour warm,
`hold-release` to the neighbouring light theme (catppuccin-latte), injected centre tap to apply, a fast swipe back to
catppuccin, injected centre tap to apply. Trial 1 started 07:11:11 UTC, trial 2 07:12:45 UTC. The active generation
path hash was identical before and after both trials (`1d6e6815e6151009`), i.e. the dark generation was restored.

| | Light apply (t1 / t2) | Dark apply (t1 / t2) |
| --- | ---: | ---: |
| `optimistic-apply shown ms` | 201.2 / 204.4 | 156.1 / 163.2 |
| `prerendered`, `reason` | false, content-changed (both) | false, content-changed (both) |
| stage `adopt / wallpaper / overlay / flush` ms | 0.5 / 2.6 / 85.7 / 0.0; 0.4 / 2.8 / 86.2 / 0.9 | 0.4 / 7.5 / 55.1 / 0.8; 0.4 / 11.5 / 58.8 / 0.8 |
| tap-up to shown frame (journal Rust clock), ms | 566 / 568 | 511 / 510 |
| `activate_generation` total, ms; `prepare_phase`; `warm` | 230.6 / 242.0; 3.1 / 0.1 ms; 2 | 192.9 / 195.0; 0.2 / 0.1 ms; 2 |
| `theme-command activate` round trip, ms | 300 / 314 | 253 / 265 |

**10.7.** The `shown ms` figure did not move toward the ~30 ms target and is no better than the 161 ms baseline (dark
156 to 163, light 201 to 204). The reported reason is that the pre-render made while browsing (`optimistic-apply
prerendered generation=...` appears before each tap) was **not reused: `prerendered=false reason=content-changed`**; the
overlay stage (55 to 86 ms) is the dominant part. Measured from touch-up, the frame appears about 510 to 570 ms later
because a `preview` request (255 to 288 ms, with a second `appearance-prepare-accepted`) runs after the tap, before the
optimistic frame. Both themes read correctly in the native captures and the picker fits the 568x1232 panel:
the theme card, background card, labels and the "Theme applied" status line are all inside the frame, the status line
sits about 27 px above the bottom edge at full resolution (`panel-bottom-full-resolution.png`), tight but not clipped.
This is compositor output (`grim`), not a camera view of the glass.

**6.6 (not met).** (a) Apply of an already-prepared generation is **not under 150 ms**: `activate_generation` is
193 to 242 ms and the activate round trip 253 to 314 ms. (b) `activate_generation` did skip the redundant prepare for
both receivers (`prepare_phase` 0.1 to 3.1 ms, `warm=2 targets=2`), and the helper's `activate` request showed `parse` 5 to 7 ms
(trial 1) and `prepare_entry` 28 to 38 ms. (c) A **second `appearance-prepare-accepted` does occur between the neighbour warm and the
Apply**, because the tap sends a `preview` first. (d) The **cold-open neighbour check passes**: after a fresh restart,
the active theme previews in 380 to 383 ms and the neighbouring theme in 231 to 241 ms about 0.3 s later, not the earlier ~4 s
cold figure. The disk caches were warm, so this is a process-cold, not disk-cold, result. **6.6 stays open.**
Next measured correction: skip the tap-time `preview` when the Rust side already holds the prepared generation
(or make `preview` idempotent for a generation the receivers already hold), and reuse the browse-time pre-render
instead of discarding it as `content-changed`.

## Observer cost and limits

* Everything here is injected input over SSH, with Rust-clock and `CLOCK_MONOTONIC` journal timing. Commit gaps are
  intervals between `commit` events, not display FPS; `presented` gaps use the compositor's presentation feedback,
  not photons.
* CPU samples are about 0.5 s apart, so a 1.4 s swipe window is only partly covered; percentages are CPU seconds
  over covered wall seconds.
* The recorder was on for the trace pairs and the 18.3 runs (cost above); recorder-off pairs are the clean CPU
  and cadence numbers. No `grim` ran inside a profile timing pass. In the 18.3 runs the capture follows each settle
  inside the bounded trace window but outside the analysed gesture window.
* Baseline and candidate differ visually (card drawing), so render and CPU differences are not purely the row
  repaint mechanism. Three pairs per mode is a small sample; medians over three, not a distribution.
* Disk-cold behaviour was never tested; user caches were not cleared. `process-cold` is journal- and age-verified only.
* Run order and the fixed workload were identical for both builds, but the helper's dwell-triggered previews land in
  different swipes from run to run, which is the dominant noise.

## Final state of the board (verified 07:17 to 07:20 UTC)

* System unchanged (`zvxmd93g...`, booted = current); no boot selector, profile or flash was written.
* Virtual input unit stopped; only `event0` (power key) and `event1` (Goodix) remain; `/run/systemd/system` empty,
  no drop-ins, no restoration timers, no `k230-theme-sess-*` units.
* `shell`, `shell-ui`, `theme-helper`, `k230-touch-trackpad` and `shell-keyboard` all `active`; `shell-ui` runs the installed
  `ybpn` ELF; compositor and helper executables as listed above.
* Original theme state restored: the durable state I created (pointer, 18 staged generations, selection file,
  app/keyboard appearance) was removed, leaving only `.activation.lock`, and `shell.service` was restarted; the shell user
  sees `active: {id: null, generation: null}` as at the start and the screen shows the same boot-time terminal as
  the first capture.
* Left on the board: gcroots for `8cik` and `si9vd`, the small session scripts under `/root/tmp/k230-theme-board-session-20261012/`
  (raw runs deleted).
