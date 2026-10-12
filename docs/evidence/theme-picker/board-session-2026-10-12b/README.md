# Board session 2026-10-12 (b): memory, motion curves, warm tap-apply

Tasks 11.3, 18.3 and 6.6 of change `the-shell-swaps-themes-without-a-python-stall`.

The operator asked for this session, without being present: "just test stuff that doesn't need me as far as you
can then lmk what you need". The work follows the first board session of the same day
([../board-session-2026-10-12/README.md](../board-session-2026-10-12/README.md)) and its
tools, workloads and gates.

The source is branch `perf/theme-row-memory-trace`, in worktree
`/home/jadams/tmp/k230-row-memtrace`. Its base is master `6faf4b9b`, and it merges
`perf/theme-tap-apply`. Times are UTC unless marked local (board local time is CDT, UTC-5).

Evidence classes:

- software-injected touch through the virtual `K230 injected touchscreen`;
- the shell's own runtime trace and journal;
- coherent-installer serial checks.

No finger or camera observation is claimed. Raw captures stay private in
`~/tmp/k230-session-b-run/` and are not committed.

## Builds

Four candidates were built, each with
`flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellBootFiles --out-link ~/.local/state/tdisplay-k230/retained-builds/row-memtrace-2026-10-12/<name> --print-out-paths --max-jobs 1 --cores 4`.
Each was swapped in through a `/run` drop-in (wrapper copy with the final `exec` replaced) for its board runs.

All four candidate ELFs have the same runtime reference set as baseline `8cik` (md5 `adb9f783…`).

| Candidate | Commit | Rust ELF | What it added |
| --- | --- | --- | --- |
| 1 | `0cfbb9e6` | `x6hhs64w…` | Rest-size sprite cache only, per-frame `carousel` trace record, tap without a preview, pressed-wash fingerprint |
| 2 | `3e9df8d5` | `zfck2cyv…` | LRU card cache (4 MiB), reused scratch surfaces for in-between cards, release and `malloc_trim` when a scene has no picker |
| 3 | `b01b580d` | `a7aid2j6…` | Diagnostic: logs the pre-render's content parts beside the current ones on a mismatch |
| 4 | `e93b5a23` | `3m65ag9z…` | Fingerprint recomputed on every view update, only collapsed slices cached (2 MiB), trim and `picker-memory` log at gesture rest |

Candidate 4 is the measured and installed build. The tables below are all candidate 4 unless named otherwise.

## Task 11.3: matched pairs against the repaired baseline

Each run used [tools/go.sh](tools/go.sh) and [tools/seq.sh](tools/seq.sh), the same `run.py` / 13.1 workload as the
first session, recorder off.

The order was:

1. `p1` cand, base (16:56);
2. `p2` base, cand;
3. `p3` cand, base.

Every run passed the profile harness gates, and every `compare` reports `comparable: true`
([11.3/compare-of-p1.json](11.3/compare-of-p1.json) and the next two). The reduced reports are in
[11.3/reports/](11.3/reports/), and the pair table is [11.3/pairs-summary.json](11.3/pairs-summary.json).

The baseline is `8cik` (repaired baseline, same as the first session). The candidate is `3m65ag9z`.

| Metric (median of three pairs) | Baseline | Candidate | Per-pair delta |
| --- | ---: | ---: | --- |
| Warm theme commit gap, median ms | 140 | 63 | -81, -79, -65.5 |
| Warm theme commit gap, p95 ms | 173 | 89 | -84, -99, -65 |
| Cold theme commit gap, median ms | 144 | 67 | -78, -63, -67 |
| Background commit gap, median ms | 84 | 38 | -50, -46, -32.5 |
| Warm theme commits | 59 | 97 | +39, +40, +29 |
| Rust CPU %, warm theme swipes | 79.0 | 57.0 | -21.1, -21.7, -22.1 |
| Rust CPU %, background swipes | 46.0 | 9.2 | -36.8, -37.5, -15.8 |
| Rust CPU %, idle | 0.48 | 0.51 | -0.48, +0.01, +0.06 |
| Rust RSS at end of warm idle, MiB | 82.5 | 84.5 | +2.0, -2.3, +11.0 |
| Rust RSS peak, MiB | 82.5 | 87.4 | +4.9, +3.9, +13.2 |
| Helper RSS, MiB | 24.0 | 23.4 | -0.7, +0.2, -0.7 |
| Theme preview requests | 5 | 15 | +9, +7, +12 |
| Overlay pre-renders completed (none with a touch held) | 4 | 8 | +3, +1, +11 |

**Memory attribution.** Per-phase Rust RSS shows the following
([11.3/reports/](11.3/reports/), `units.shell-ui.service.rss_last_bytes`):

- The candidate ends every run at 80–87 MiB.
- The baseline ends at 82.5, 82.5 and 75.5 MiB. The +11 MiB pair is the baseline's low `p3` run, not a high candidate run.
- When the picker closes (phase `back`), the candidate falls to 79.2–79.3 MiB in all three runs. That is below the
  baseline's 80.5–81.9 in `p1`/`p2`.

While the picker is open, the shell's own `picker-memory` log at gesture rest reports
([6.6/journal-trial-1.txt](6.6/journal-trial-1.txt)):

| Item | Size |
| --- | --- |
| Card sprites | 1.96–2.03 MiB |
| Outline masks | 52 KiB |
| Scratch surfaces | 1.5 MiB |
| Thumbnails (same bounded cache as the baseline) | 7.2–8.1 MiB |
| glibc heap in use | 22–25 MiB |
| Free after trim | 4–6.8 MiB |

The candidate's +2 MiB median is therefore the picker's deliberate 3.5 MiB sprite and scratch working set, released
when the picker closes.

How the build got there:

- **Candidate 1** held +16.0 MiB at the end. Its unbounded rest-size cache kept every visited card
  ([11.3/first-candidate/](11.3/first-candidate/)).
- **Candidate 2** held +15.5 MiB at the end ([11.3/second-candidate/](11.3/second-candidate/)), but fell by about
  12 MiB at `back`, which showed the remainder was picker-scoped.
- **Candidate 4** caches only collapsed slices and trims freed heap at each gesture rest.

The candidate makes three times as many speculative preview requests as the baseline. Helper RSS is unchanged.

## Task 18.3: per-frame carousel position and velocity

The shell now writes one `carousel` trace event per committed frame on the Settings route:

- frame number;
- each row's position (items) and velocity (reference px/s, the coast or spring velocity; 0 under a finger and at rest),
  stored as f64 bits;
- each row's motion phase: rest, finger, coast or settle.

Source: `Carousel::trace_state` in `nix/rust-shell-client/src/theme_carousel.rs` and the commit site in `main.rs`.

Runs `g-theme-1`, `g-bg-1`, `g-theme-2`, `g-bg-2` (16:43 to 16:56) used [tools/gog.sh](tools/gog.sh). That is the first
session's `run.py --workload gestures` with the five injected programs (flick, slow, hold-release, reversal,
interrupt), two repetitions each, a fresh Settings to Themes opening per gesture, and trace mode. Generation and
process identities were checked after every gesture and never changed. No trace dropped an event.

[tools/curves.py](tools/curves.py) plots every committed frame. Nothing is replayed through a host model. It anchors
"release" on the record's own last finger-phase frame, because the shell handles an injected release 6–130 ms after it
is written.

Outputs:

- [18.3/position-curves.png](18.3/position-curves.png);
- [18.3/velocity-curves.png](18.3/velocity-curves.png);
- [18.3/curves-summary.json](18.3/curves-summary.json), with all 40 gestures and their medians.

| Gesture (median of 4) | Row | Final item | Items after release | Overshoot past final | Release to rest, ms | Frames after release |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| flick | theme | 10 (4 of 4) | 8.08 | 0 | 837 | 12 |
| slow | theme | 3 | 1.16 | 0 | 482 | 10.5 |
| hold-release | theme | 1 | 0.06 | 0 | 370 | 8 |
| reversal | theme | 0 | -0.29 | 0 | 418 | 12.5 |
| interrupt | theme | 7 | -0.69 | 0 | 632 | 11 |
| flick | background | 3 (the last item) | 1.62 | 0 | 439 | 14 |
| slow | background | 3 | 0.26 | 0 | 305 | 10 |
| hold-release | background | 1 | -0.39 | 0 | 342 | 10 |
| reversal | background | 0 | -0.29 | 0 | 419 | 13 |
| interrupt | background | 2 | -0.90 | 0 | 617 | 17.5 |

Observations only:

- Every gesture approaches its final item monotonically, with no overshoot.
- The four repetitions of each gesture land on the same item.
- A 300 px / 80 ms theme flick leaves at the -3000 px/s velocity ceiling and coasts about 8 items.
- One theme flick (`g-theme-1`, rep 0) holds near item 2 for about 150 ms early in the coast before catching up. That
  is a slow frame, visible as a gap in the position curve.

Whether the travel, settling and interruption feel right is task 18.4's finger question. These curves do not answer it.

## Task 6.6: warm tap-apply

[tools/apply-swap.sh](tools/apply-swap.sh) ran the first session's apply trial ([tools/apply_trial.sh](tools/apply_trial.sh))
twice on candidate 4 through the `/run` drop-in. Each trial does the following:

1. Cold restart of `theme-helper` and `shell-ui`.
2. Settings to Themes, then wait 15 s.
3. Hold-release to the light neighbour, then an injected centre tap.
4. Swipe back to the dark item, then an injected centre tap.

Trial 1 started 16:41:06 and trial 2 at 16:42 (local 11:41 / 11:42). Sanitized journal excerpts:
[6.6/journal-trial-1.txt](6.6/journal-trial-1.txt) and [6.6/journal-trial-2.txt](6.6/journal-trial-2.txt), via
[tools/sanitize_journal.py](tools/sanitize_journal.py). The markers are in [6.6/marks.txt](6.6/marks.txt).

| | Light (t1 / t2) | Dark (t1 / t2) |
| --- | ---: | ---: |
| `optimistic-apply shown ms` | 181.7 / 189.4 | 153.4 / 150.5 |
| `prerendered` | true / true | true / true |
| stage `adopt / wallpaper / overlay` ms | 16.0 / 4.6 / 54.8; 12.4 / 7.5 / 56.5 | 14.9 / 21.4 / 14.3; 15.3 / 19.3 / 11.0 |
| Tap-up to shown frame (journal Rust clock), ms | 185 / 190 | 154 / 151 |
| `activate_generation` total, ms; `prepare_phase` ms; `warm` | 173.8 / 174.2; 0.2 / 2.8; 2 | 140.1 / 140.8; 2.7 / 2.6; 2 |
| `theme-command activate` round trip, ms | 323 / 326 | 288 / 280 |

The first session's figures were:

- tap-up to shown 510–570 ms;
- every pre-render discarded as `content-changed`;
- overlay stage 55–86 ms;
- a `preview` request and a second `appearance-prepare-accepted` after every tap.

In this session:

- **No second prepare.** No `preview` request and no second `appearance-prepare-accepted` follows a tap. The tap goes
  straight to `activate` with the generation the browse-time warm learned.
- **The pre-render is reused** (`prerendered=true`, 4 of 4).

  Candidate 3's diagnostic line showed identical content parts on both sides of the mismatch. That narrowed the
  cause to the chooser fingerprint: it was only recomputed when the old cache-key check fired. That check compares
  each update with the previous one at a quarter-item tolerance, so a settle moving in small steps left the
  fingerprint on a mid-settle position. Candidate 4 recomputes it on every update.

  Candidate 1 and 2 trials (`content-changed`, 203–245 ms shown) are in the private run directory only.
- **Not yet under 150 ms.** Tap-up to the shown frame is 151–190 ms, and the helper's `activate_generation` is
  140–174 ms. `commit_phase` (72–109 ms) waits for the shell's commit acknowledgement. `swap_pointer` (26–33 ms) is the
  durable directory fsync.

The cold-open neighbour check passed in the first session and was not repeated.

### Follow-up: what the tap waited on

Same trial, same recipe ([tools/apply-swap.sh](tools/apply-swap.sh) with the candidate path changed), two cold-process
trials per candidate, injected taps. Candidates 5–8 add the `entry_ms`/`checks_ms` stage fields; source is the
`perf/theme-row-memory-trace` branch after `89f8b25e`.

1. **Candidate 5 (`7rfw6yc2`, timing only).** `entry_ms`, from the Activate submit to the optimistic check, was
   106–193 ms of the 140–235 ms shown time. The touch-up handler ends with a synchronous picker `draw` (the pending
   and pressed state), which ran before the loop reached the optimistic check. Journals are in the private run
   directory only.
2. **Candidate 6 (`2jgydicg`).** The touch-up handler and the overlay frame callback skip that draw while a fresh
   Activate awaits the optimistic check; the loop draws anything still dirty afterwards. Tap-up to shown frame:
   **27.8–31.1 ms**, `entry_ms` 3.4–6.1, `prerendered=true` 4 of 4
   ([6.6/candidate-6/](6.6/candidate-6/)). The helper's commit then waited longer: the shell spent 336 ms repainting the
   hidden Home layer (`K230_HOME_FRAME ms=336`) before acknowledging. Shell commit exchange 165–232 ms,
   `commit_phase` 215–238 ms, activate round trip 459–476 ms.
3. **Candidate 7 (`bgdk0j87`).** Defers the Home repaint while an optimistic frame awaits its commit (cap 2 s). The
   commit event clears that state on arrival, and the loop still repainted Home before reaching the deferred ack:
   shell commit exchange 214–232 ms, `commit_phase` 281–301 ms. Private run directory only.
4. **Candidate 8 (`hl4bca4g`).** Also acknowledges a reused optimistic commit as soon as the event arrives, before that
   tick's Home repaint ([6.6/candidate-8/](6.6/candidate-8/)):

| Candidate 8 | Light (t1 / t2) | Dark (t1 / t2) |
| --- | ---: | ---: |
| `optimistic-apply shown ms` | 27.5 / 28.8 | 29.2 / 34.2 |
| `prerendered` | true / true | true / true |
| shell commit exchange, ms | 48.1 / 52.6 | 37.2 / 42.9 |
| `activate_generation` total; `commit_phase`, ms | 179.1 / 174.9; 110.5 / 115.9 | 166.5 / 170.6; 105.1 / 105.7 |
| `theme-command activate` round trip, ms | 338 / 339 | 333 / 342 |

Home repaints 350 ms after the ack (`K230_HOME_FRAME ms=347–355`), off the commit path. Every apply changed the active
theme link (`ACTIVE_*` in [6.6/candidate-8/marks.txt](6.6/candidate-8/marks.txt)). Native grim captures of the picker
after each apply (trial 2 of candidates 6 and 8, viewed, not committed) show the applied theme's chrome and
"Current theme" on the applied item.

The visible apply is now well under 150 ms. The durable activation, measured by the helper, is not:
`activate_generation` is 167–179 ms, and `prepare_entry` (82–101 ms) plus `commit_phase` put the round trip at
333–342 ms. The commit exchange with the card process (32–35 ms) and `swap_pointer` (23–39 ms) remain inside
`commit_phase`. Neither the injected taps nor these journals are a finger-on-glass measurement.

## Install

| Identity | Value |
| --- | --- |
| Bundle | `/nix/store/1dkw87zfhgfygnmv9qxdrbcqy2xqzxfg-k230-coherent-shell-boot-files` |
| System | `/nix/store/fm8gk6xica4h7ni3fp6wgya3lmfxfzjr-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Rust shell ELF | `/nix/store/3m65ag9zlzffdd86ajjfq7si96cj46y1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust` |
| Kernel, `Image`, `initrd.uimg` | unchanged from the baseline |
| Baseline | sprite install `rav09qp6…` ([../row-sprites-2026-10-12/](../row-sprites-2026-10-12/README.md)) |

The coherent installer ran with the row-sprites recipes. Only the paths, the baseline and the saved `catppuccin`
appearance differ ([install/expected-runtime.json](install/expected-runtime.json); see `install/*-used.py`). Every step
passed:

1. **Preflight:** boot `49fb3850-…`, 17:07:32 ([install/preflight.json](install/preflight.json)).
2. **Stage:** ([install/stage.log](install/stage.log), [install/transfer.json](install/transfer.json),
   [install/staged-state.json](install/staged-state.json), [install/host-inspection.json](install/host-inspection.json)).
3. **Candidate boot:** ([install/candidate-boot.json](install/candidate-boot.json)). The runtime check ran on boot
   `dd17a5e9-…` at 17:12:19 ([install/candidate-runtime.json](install/candidate-runtime.json)).
4. **Qualification:** ([install/deployment-authorization.json](install/deployment-authorization.json)).
5. **Install and ordinary autoboot:** ([install/ordinary-boot.json](install/ordinary-boot.json)). The runtime check ran on
   boot `34d77814-…` at 17:15:31 ([install/ordinary-runtime.json](install/ordinary-runtime.json)). The current system
   and profile are both `fm8gk6xi…`, the four shell services are active, and the saved appearance is unchanged.

[install/installed-picker-native.png](install/installed-picker-native.png) is a native `grim -s 0.5` capture taken on
that ordinary boot at about 17:16. Settings was opened and Themes was tapped by injection. It shows `catppuccin` as the
current theme, its neighbours as side slices, and the Backgrounds row loaded. No finger observation was made on the
installed boot.

## Board state afterwards

- The virtual touch device unit `k230-theme-session-input` stops by its own `RuntimeMaxSec`.
- The gcroots `k230-session-b-candidate{,2,3,4}` pin the swapped ELFs. `k230-theme-baseline-8cik` and
  `k230-theme-motion-si9vd` remain from the first session.
- The saved theme is the dark `catppuccin` generation applied by the last apply trial. The operator said any theme is
  fine.
